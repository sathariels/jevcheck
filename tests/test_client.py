from __future__ import annotations

from types import SimpleNamespace

import pytest

from jevcheck.answers import NoulAnswer, adapt_response
from jevcheck.client import JevClient
from jevcheck.pinning import UnpinnedModelError


class FakeSDK:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.closed = False

    def system_one(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            model=kwargs["model"],
            usage=SimpleNamespace(input_tokens=3, output_tokens=1),
            answers={
                "billing": SimpleNamespace(type="noul", noul=0.96),
                "tone": SimpleNamespace(
                    type="choice",
                    choice="angry",
                    confidence=0.9,
                    probabilities={"calm": 0.05, "angry": 0.9, "frustrated": 0.05},
                ),
                "urgency": SimpleNamespace(
                    type="score",
                    score=1.7,
                    confidence=0.88,
                    legend={"0": "can wait"},
                    probabilities={"0": 0.1, "1": 0.1, "2": 0.8},
                ),
            },
        )

    def close(self) -> None:
        self.closed = True


def test_client_adapts_mocked_sdk_and_pins_model() -> None:
    sdk = FakeSDK()
    client = JevClient(model="jev-1.13", sdk_client=sdk)
    result = client.system_one(
        state="I was charged twice.",
        questions={
            "billing": {"type": "noul", "instructions": "Is this about billing?"},
            "tone": {
                "type": "choice",
                "instructions": "Tone?",
                "criteria": {"calm": None, "angry": None, "frustrated": None},
            },
            "urgency": {
                "type": "score",
                "instructions": "Urgency?",
                "criteria": ["can wait", "this week", "today"],
            },
        },
        model="jev-1.13",
    )
    assert result.model == "jev-1.13"
    assert isinstance(result.answers["billing"], NoulAnswer)
    assert result.answers["billing"].noul == 0.96
    assert result.answers["tone"].choice == "angry"
    assert result.answers["tone"].confidence == 0.9
    assert result.answers["urgency"].score == 1.7
    assert sdk.calls[0]["model"] == "jev-1.13"
    assert sdk.calls[0]["questions"]["billing"]["type"] == "noul"
    assert "api_key" not in sdk.calls[0]


def test_client_rejects_unpinned_model() -> None:
    with pytest.raises(UnpinnedModelError):
        JevClient(model="jev-latest")
    client = JevClient(model="jev-1.13", sdk_client=FakeSDK())
    with pytest.raises(UnpinnedModelError):
        client.system_one(
            state="x",
            questions={"n": {"type": "noul"}},
            model="jev-latest",
        )


def test_client_requires_typesafe_key(monkeypatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    client = JevClient(model="jev-1.13")
    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY"):
        client.system_one(state="x", questions={"n": {"type": "noul"}})


def test_adapt_response_from_mapping() -> None:
    adapted = adapt_response(
        {
            "model": "jev-1.13",
            "usage": {"input_tokens": 1},
            "answers": {"billing": {"type": "noul", "noul": 0.5}},
        }
    )
    assert adapted.answers["billing"].noul == 0.5
