"""Regression tests against the real typesafe-sdk 0.7.0 with a mocked HTTP transport."""

from __future__ import annotations

import json

import httpx2
import pytest
from typesafe_sdk import RetryPolicy, TypeSafeClient

from jevcheck.answers import adapt_response
from jevcheck.cli import EXIT_OPS, main, redact_secrets
from jevcheck.client import JevClient
from tests.helpers import FIXTURES

SENTINEL_KEY = "ts_fake_key_sentinel_not_real"
DOCUMENTED_PIN = "jev-1.13.0"

SCORE_BODY = {
    "model": DOCUMENTED_PIN,
    "usage": {"input_tokens": 2, "output_tokens": 1},
    "answers": {
        "urgency": {
            "type": "score",
            "score": 1.7,
            "confidence": 0.88,
            "legend": {"0": "can wait", "1": "this week", "2": "today"},
            "probabilities": {"0": 0.1, "1": 0.1, "2": 0.8},
        }
    },
}

CHOICE_BODY = {
    "model": DOCUMENTED_PIN,
    "usage": {"input_tokens": 2, "output_tokens": 1},
    "answers": {
        "intent": {
            "type": "choice",
            "choice": "billing",
            "confidence": 0.91,
            "probabilities": {"billing": 0.91, "general": 0.09},
        }
    },
}


def _client(handler, *, model: str = DOCUMENTED_PIN) -> TypeSafeClient:
    return TypeSafeClient(
        api_key=SENTINEL_KEY,
        model=model,
        retry=RetryPolicy(max_retries=0),
        transport=httpx2.MockTransport(handler),
    )


def test_real_sdk_score_uses_integer_keys_and_jevcheck_adapts() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=SCORE_BODY)

    sdk = _client(handler)
    raw = sdk.system_one(
        state="I was charged twice.",
        questions={
            "urgency": {
                "type": "score",
                "instructions": "Urgency?",
                "criteria": ["can wait", "this week", "today"],
            }
        },
        model=DOCUMENTED_PIN,
    )
    dumped = raw.answers["urgency"].model_dump()
    assert dumped["legend"]
    assert all(isinstance(key, int) for key in dumped["legend"])
    assert all(isinstance(key, int) for key in dumped["probabilities"])

    adapted = adapt_response(raw)
    assert adapted.model == DOCUMENTED_PIN
    assert adapted.answers["urgency"].legend == {
        "0": "can wait",
        "1": "this week",
        "2": "today",
    }
    assert adapted.answers["urgency"].probabilities == {"0": 0.1, "1": 0.1, "2": 0.8}

    wrapped = JevClient(model=DOCUMENTED_PIN, api_key=SENTINEL_KEY, sdk_client=_client(handler))
    via_client = wrapped.system_one(
        state="I was charged twice.",
        questions={
            "urgency": {
                "type": "score",
                "criteria": ["can wait", "this week", "today"],
            }
        },
        model=DOCUMENTED_PIN,
    )
    assert via_client.answers["urgency"].score == 1.7
    body = json.loads(seen[0].content)
    assert body["model"] == DOCUMENTED_PIN


def test_real_sdk_choice_round_trip() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=CHOICE_BODY)

    client = JevClient(model=DOCUMENTED_PIN, api_key=SENTINEL_KEY, sdk_client=_client(handler))
    result = client.system_one(
        state="charged twice",
        questions={
            "intent": {
                "type": "choice",
                "criteria": {"billing": None, "general": None},
            }
        },
    )
    assert result.answers["intent"].choice == "billing"
    assert result.answers["intent"].probabilities["billing"] == 0.91


@pytest.mark.parametrize("status,fragment", [(401, "authentication"), (429, "rate limited"), (500, "server error")])
def test_cli_sdk_http_errors_are_ops_exits(monkeypatch, capsys, status, fragment) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status, json={"error": f"boom {SENTINEL_KEY}"})

    def fake_open(self, model: str):
        return _client(handler, model=model)

    monkeypatch.setenv("TYPESAFE_API_KEY", SENTINEL_KEY)
    monkeypatch.setattr("jevcheck.client.JevClient._open_sdk", fake_open)
    code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-1.14",
        ]
    )
    captured = capsys.readouterr()
    assert code == EXIT_OPS
    assert fragment in captured.err.lower()
    assert SENTINEL_KEY not in captured.err
    assert "Traceback" not in captured.err


def test_cli_invalid_sdk_response_is_ops_exit(monkeypatch, capsys) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"not": "system-one"})

    def fake_open(self, model: str):
        return _client(handler, model=model)

    monkeypatch.setenv("TYPESAFE_API_KEY", SENTINEL_KEY)
    monkeypatch.setattr("jevcheck.client.JevClient._open_sdk", fake_open)
    code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-1.14",
        ]
    )
    captured = capsys.readouterr()
    assert code == EXIT_OPS
    assert "invalid API response" in captured.err
    assert SENTINEL_KEY not in captured.err


def test_redact_secrets_strips_env_and_bearer() -> None:
    text = f"Authorization: Bearer {SENTINEL_KEY} echoed {SENTINEL_KEY}"
    assert SENTINEL_KEY not in redact_secrets(text, SENTINEL_KEY)
    assert "***" in redact_secrets(text, SENTINEL_KEY)


def _triage_body(model: str, state: str) -> dict:
    """Minimal System One bodies for live two-model compare (no real key)."""
    if "notification email" in state:
        intent = ("general", 0.88) if model == "jev-1.13" else ("billing", 0.81)
        return {
            "model": model,
            "usage": {"input_tokens": 2, "output_tokens": 1},
            "answers": {
                "intent": {
                    "type": "choice",
                    "choice": intent[0],
                    "confidence": intent[1],
                    "probabilities": {
                        intent[0]: intent[1],
                        "billing" if intent[0] == "general" else "general": round(1.0 - intent[1], 2),
                    },
                }
            },
        }
    if "third time" in state:
        confidence = 0.91 if model == "jev-1.13" else 0.71
        return {
            "model": model,
            "usage": {"input_tokens": 2, "output_tokens": 1},
            "answers": {
                "intent": {
                    "type": "choice",
                    "choice": "billing",
                    "confidence": confidence,
                    "probabilities": {"billing": confidence, "general": round(1.0 - confidence, 2)},
                },
                "urgency": {
                    "type": "score",
                    "score": 2.0,
                    "confidence": confidence,
                    "legend": {"0": "can wait", "1": "this week", "2": "today"},
                    "probabilities": {"0": 0.04, "1": round(1.0 - confidence - 0.04, 2), "2": confidence},
                },
            },
        }
    return {
        "model": model,
        "usage": {"input_tokens": 2, "output_tokens": 1},
        "answers": {
            "intent": {
                "type": "choice",
                "choice": "billing",
                "confidence": 0.93,
                "probabilities": {"billing": 0.93, "general": 0.07},
            },
            "billing": {"type": "noul", "noul": 0.95},
            "urgency": {
                "type": "score",
                "score": 1.9,
                "confidence": 0.9,
                "legend": {"0": "can wait", "1": "this week", "2": "today"},
                "probabilities": {"0": 0.02, "1": 0.08, "2": 0.9},
            },
        },
    }


def test_cli_live_two_model_compare_with_mocked_sdk(monkeypatch, capsys) -> None:
    seen_models: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        seen_models.append(body["model"])
        return httpx2.Response(200, json=_triage_body(body["model"], str(body["state"])))

    def fake_open(self, model: str):
        return _client(handler, model=model)

    monkeypatch.setenv("TYPESAFE_API_KEY", SENTINEL_KEY)
    monkeypatch.setattr("jevcheck.client.JevClient._open_sdk", fake_open)
    code = main(
        [
            "compare",
            str(FIXTURES / "support-triage.json"),
            "--from-model",
            "jev-1.13",
            "--to",
            "jev-1.14",
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "jevcheck compare:" in captured.out
    assert "general→billing" in captured.out
    assert SENTINEL_KEY not in captured.err
    assert seen_models.count("jev-1.13") == 3
    assert seen_models.count("jev-1.14") == 3


def test_cli_record_with_mocked_sdk(monkeypatch, tmp_path, capsys) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        return httpx2.Response(200, json=_triage_body("jev-1.13", str(body["state"])))

    def fake_open(self, model: str):
        return _client(handler, model=model)

    monkeypatch.setenv("TYPESAFE_API_KEY", SENTINEL_KEY)
    monkeypatch.setattr("jevcheck.client.JevClient._open_sdk", fake_open)
    out = tmp_path / "live-baseline.json"
    code = main(
        [
            "record",
            str(FIXTURES / "support-triage.json"),
            "--out",
            str(out),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert out.is_file()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ticket-002"]["answers"]["intent"]["choice"] == "general"
    assert SENTINEL_KEY not in captured.out
    assert SENTINEL_KEY not in captured.err
