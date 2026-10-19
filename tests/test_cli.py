from __future__ import annotations

import json
import subprocess
import sys

import pytest

import jevcheck
from jevcheck.cli import EXIT_USAGE, main
from tests.helpers import FIXTURES


def _visible_text_details(summary: str) -> list[str]:
    """Details from text lines such as ``ticket-002 intent: general→billing  [flip]``."""
    details = []
    for line in summary.splitlines():
        if not line.endswith("]") or "  [" not in line or ": " not in line:
            continue
        left, _label = line.rsplit("  [", 1)
        _prefix, detail = left.split(": ", 1)
        details.append(detail)
    return details


def _json_visible_details(payload: dict) -> list[str]:
    return [
        field["detail"]
        for case in payload["cases"]
        for field in case["fields"]
        if field["outcome"] != "unchanged"
    ]


def test_package_version_is_0_3_0() -> None:
    assert jevcheck.__version__ == "0.3.0"


def test_cli_compatible_exit_zero() -> None:
    code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(FIXTURES / "replay-unchanged.json"),
        ]
    )
    assert code == 0


def test_cli_breaking_exit_one(capsys) -> None:
    code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(FIXTURES / "replay-breaking.json"),
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "behavioral flips: 1" in captured.out
    assert "confidence regressions: 1" in captured.out
    assert "general→billing" in captured.out
    assert "0.94→0.71" in captured.out
    assert captured.out.strip().endswith("breaking")


def test_cli_rejects_unpinned_candidate(capsys) -> None:
    code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-latest",
            "--answers",
            str(FIXTURES / "replay-unchanged.json"),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "unpinned" in captured.err


def test_cli_live_without_key_is_usage_error(monkeypatch, capsys) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-1.14",
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "TYPESAFE_API_KEY" in captured.err


def test_cli_jsonl_and_module_entry() -> None:
    code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.jsonl"),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(FIXTURES / "replay-unchanged.json"),
        ]
    )
    assert code == 0

    module = subprocess.run(
        [
            sys.executable,
            "-m",
            "jevcheck",
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(FIXTURES / "replay-unchanged.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert module.returncode == 0
    assert "compatible" in module.stdout


def test_cli_wrong_response_model_is_usage_error(tmp_path, capsys) -> None:
    replay = tmp_path / "wrong-model.json"
    replay.write_text(
        json.dumps(
            {
                "ticket-001": {
                    "model": "unrelated-model",
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
                            "legend": {"0": "a", "1": "b", "2": "c"},
                            "probabilities": {"0": 0.02, "1": 0.08, "2": 0.9},
                        },
                    },
                },
                "ticket-002": {
                    "model": "unrelated-model",
                    "answers": {
                        "intent": {
                            "type": "choice",
                            "choice": "general",
                            "confidence": 0.88,
                            "probabilities": {"billing": 0.12, "general": 0.88},
                        }
                    },
                },
                "ticket-003": {
                    "model": "unrelated-model",
                    "answers": {
                        "intent": {
                            "type": "choice",
                            "choice": "billing",
                            "confidence": 0.92,
                            "probabilities": {"billing": 0.92, "general": 0.08},
                        },
                        "urgency": {
                            "type": "score",
                            "score": 2.0,
                            "confidence": 0.91,
                            "legend": {"0": "a", "1": "b", "2": "c"},
                            "probabilities": {"0": 0.01, "1": 0.08, "2": 0.91},
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(replay),
        ]
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "does not match" in captured.err
    assert "unrelated-model" in captured.err


def test_cli_null_model_is_usage_error(tmp_path, capsys) -> None:
    replay = tmp_path / "null-model.json"
    replay.write_text(
        json.dumps(
            {
                "ticket-002": {
                    "model": None,
                    "answers": {
                        "intent": {
                            "type": "choice",
                            "choice": "general",
                            "confidence": 0.88,
                            "probabilities": {"billing": 0.12, "general": 0.88},
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    contract = tmp_path / "one.json"
    contract.write_text(
        json.dumps(
            {
                "baseline_model": "jev-1.13",
                "cases": [
                    {
                        "id": "ticket-002",
                        "state": "hi",
                        "questions": {
                            "intent": {
                                "type": "choice",
                                "criteria": {"billing": None, "general": None},
                            }
                        },
                        "expect": {"intent": {"choice": "general"}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    code = main(
        [
            "eval",
            str(contract),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(replay),
        ]
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "None" not in captured.out
    assert "must not be null" in captured.err


def test_cli_rejects_preview_candidate(capsys) -> None:
    code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-preview",
            "--answers",
            str(FIXTURES / "replay-unchanged.json"),
        ]
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "unpinned" in captured.err


def test_cli_rejects_empty_baseline_override(tmp_path, capsys) -> None:
    contract = tmp_path / "empty-base.json"
    contract.write_text(
        json.dumps(
            {
                "baseline_model": "",
                "cases": [
                    {
                        "id": "x",
                        "state": "s",
                        "questions": {"n": {"type": "noul"}},
                        "expect": {"n": {"noul_true": True}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    replay = tmp_path / "r.json"
    replay.write_text(
        json.dumps({"x": {"model": "jev-1.14", "answers": {"n": {"type": "noul", "noul": 0.9}}}}),
        encoding="utf-8",
    )
    code = main(
        [
            "eval",
            str(contract),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(replay),
        ]
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "nonempty" in captured.err


def test_cli_empty_expect_is_usage_error(tmp_path, capsys) -> None:
    contract = tmp_path / "empty-expect.json"
    contract.write_text(
        json.dumps(
            {
                "baseline_model": "jev-1.13",
                "cases": [
                    {
                        "id": "x",
                        "state": "s",
                        "questions": {
                            "q": {"type": "choice", "criteria": {"a": None, "b": None}}
                        },
                        "expect": {"q": {}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    code = main(
        [
            "eval",
            str(contract),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(FIXTURES / "replay-unchanged.json"),
        ]
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "constraint" in captured.err


def test_cli_baseline_confidence_only_is_usage_error(tmp_path, capsys) -> None:
    """Recheck P1: baseline_confidence 0.95 with actual 0.51 must not exit 0."""
    contract = tmp_path / "baseline-only.json"
    contract.write_text(
        json.dumps(
            {
                "baseline_model": "jev-1.13",
                "cases": [
                    {
                        "id": "c1",
                        "state": "s",
                        "questions": {
                            "q": {"type": "choice", "criteria": {"a": None, "b": None}}
                        },
                        "expect": {"q": {"baseline_confidence": 0.95}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    replay = tmp_path / "baseline-only-replay.json"
    replay.write_text(
        json.dumps(
            {
                "c1": {
                    "model": "jev-1.14",
                    "answers": {
                        "q": {
                            "type": "choice",
                            "choice": "b",
                            "confidence": 0.51,
                            "probabilities": {"a": 0.49, "b": 0.51},
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    code = main(
        [
            "eval",
            str(contract),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(replay),
        ]
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "baseline_confidence" in captured.err
    assert "compatible" not in captured.out


def test_cli_alias_opt_in_accepts_resolved_version(tmp_path, capsys) -> None:
    """Recheck P2: --candidate-model jev-preview --allow-unpinned + jev-1.13.0."""
    contract = tmp_path / "alias.json"
    contract.write_text(
        json.dumps(
            {
                "baseline_model": "jev-1.13",
                "cases": [
                    {
                        "id": "c1",
                        "state": "s",
                        "questions": {
                            "q": {"type": "choice", "criteria": {"a": None, "b": None}}
                        },
                        "expect": {"q": {"choice": "b", "min_confidence": 0.0}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    replay = tmp_path / "alias-replay.json"
    replay.write_text(
        json.dumps(
            {
                "c1": {
                    "model": "jev-1.13.0",
                    "answers": {
                        "q": {
                            "type": "choice",
                            "choice": "b",
                            "confidence": 0.51,
                            "probabilities": {"a": 0.49, "b": 0.51},
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    code = main(
        [
            "eval",
            str(contract),
            "--candidate-model",
            "jev-preview",
            "--allow-unpinned",
            "--answers",
            str(replay),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "jev-1.13.0" in captured.out
    assert captured.out.strip().endswith("compatible")


def test_cli_score_decimal_boundary_is_compatible(tmp_path, capsys) -> None:
    """Recheck P2: expected 1.4, actual 1.6, score_tolerance 0.2 must exit 0."""
    contract = tmp_path / "score-boundary.json"
    contract.write_text(
        json.dumps(
            {
                "baseline_model": "jev-1.13",
                "cases": [
                    {
                        "id": "c1",
                        "state": "s",
                        "questions": {
                            "q": {"type": "score", "criteria": ["lo", "mid", "hi"]}
                        },
                        "expect": {
                            "q": {
                                "score": 1.4,
                                "score_tolerance": 0.2,
                                "min_confidence": 0.0,
                            }
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    replay = tmp_path / "score-boundary-replay.json"
    replay.write_text(
        json.dumps(
            {
                "c1": {
                    "model": "jev-1.14",
                    "answers": {
                        "q": {
                            "type": "score",
                            "score": 1.6,
                            "confidence": 0.6,
                            "legend": {"1": "mid", "2": "hi"},
                            "probabilities": {"1": 0.4, "2": 0.6},
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    code = main(
        [
            "eval",
            str(contract),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(replay),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.strip().endswith("compatible")


def test_cli_score_probabilities_missing_null_empty_are_usage_errors(tmp_path, capsys) -> None:
    """Recheck P2: omitted / null / empty score probabilities must exit 2."""
    contract = tmp_path / "score.json"
    contract.write_text(
        json.dumps(
            {
                "baseline_model": "jev-1.13",
                "cases": [
                    {
                        "id": "c1",
                        "state": "s",
                        "questions": {
                            "q": {"type": "score", "criteria": ["lo", "mid", "hi"]}
                        },
                        "expect": {"q": {"score": 2, "min_confidence": 0.0}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    for label, probabilities in (
        ("missing", "__omit__"),
        ("null", None),
        ("empty", {}),
    ):
        answers: dict = {
            "type": "score",
            "score": 2,
            "confidence": 0.9,
            "legend": {"0": "lo", "1": "mid", "2": "hi"},
        }
        if probabilities != "__omit__":
            answers["probabilities"] = probabilities
        replay = tmp_path / f"score-prob-{label}.json"
        replay.write_text(
            json.dumps({"c1": {"model": "jev-1.14", "answers": {"q": answers}}}),
            encoding="utf-8",
        )
        code = main(
            [
                "eval",
                str(contract),
                "--candidate-model",
                "jev-1.14",
                "--answers",
                str(replay),
            ]
        )
        captured = capsys.readouterr()
        assert code == EXIT_USAGE, label
        assert "compatible" not in captured.out


def test_cli_bad_choice_probabilities_is_usage_error(tmp_path, capsys) -> None:
    contract = tmp_path / "c.json"
    contract.write_text(
        json.dumps(
            {
                "baseline_model": "jev-1.13",
                "cases": [
                    {
                        "id": "x",
                        "state": "s",
                        "questions": {
                            "q": {"type": "choice", "criteria": {"a": None, "b": None}}
                        },
                        "expect": {"q": {"choice": "a"}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    replay = tmp_path / "bad-prob.json"
    replay.write_text(
        json.dumps(
            {
                "x": {
                    "model": "jev-1.14",
                    "answers": {
                        "q": {
                            "type": "choice",
                            "choice": "a",
                            "confidence": 0.9,
                            "probabilities": {"a": 0.2, "b": 0.2},
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    code = main(
        [
            "eval",
            str(contract),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(replay),
        ]
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "probabilities" in captured.err


def test_cli_eval_format_json_unchanged(capsys) -> None:
    code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(FIXTURES / "replay-unchanged.json"),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert captured.out == json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    assert payload["schema"] == "1"
    assert payload["command"] == "eval"
    assert payload["verdict"] == "compatible"
    assert payload["models"]["baseline"] == "jev-1.13"
    assert payload["models"]["candidate"] == "jev-1.14"
    assert payload["counts"]["cases"] == 3
    assert payload["counts"]["unchanged"] == 3
    assert payload["counts"]["answer_flips"] == 0
    assert payload["counts"]["confidence_regressions"] == 0
    assert _json_visible_details(payload) == []
    assert "jevcheck eval:" not in captured.out


def test_cli_eval_format_json_breaking_matches_text(capsys) -> None:
    text_code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(FIXTURES / "replay-breaking.json"),
        ]
    )
    text = capsys.readouterr().out
    assert text_code == 1
    assert "general→billing" in text
    assert "0.94→0.71" in text

    code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(FIXTURES / "replay-breaking.json"),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["schema"] == "1"
    assert payload["command"] == "eval"
    assert payload["verdict"] == "breaking"
    assert payload["models"]["candidate"] == "jev-1.14"
    assert _json_visible_details(payload) == _visible_text_details(text)
    assert "general→billing" in _json_visible_details(payload)
    assert "0.94→0.71" in _json_visible_details(payload)
    flip = next(
        field
        for case in payload["cases"]
        if case["id"] == "ticket-002"
        for field in case["fields"]
        if field["field"] == "intent"
    )
    assert flip["outcome"] == "answer_flip"
    assert flip["expected"] == "general"
    assert flip["actual"] == "billing"
    assert flip["detail"] == "general→billing"
    regression = next(
        field
        for case in payload["cases"]
        for field in case["fields"]
        if field["detail"] == "0.94→0.71"
    )
    assert regression["outcome"] == "confidence_regression"
    assert regression["expected"] == "0.94"
    assert regression["actual"] == "0.71"
    assert "behavioral flips:" not in captured.out


def test_cli_eval_report_file_keeps_text_stdout(tmp_path, capsys) -> None:
    path = tmp_path / "report.json"
    code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(FIXTURES / "replay-breaking.json"),
            "--report",
            str(path),
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "jevcheck eval:" in captured.out
    assert captured.out.strip().endswith("breaking")
    assert "general→billing" in captured.out
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == "1"
    assert payload["verdict"] == "breaking"
    assert payload["command"] == "eval"
    assert _json_visible_details(payload) == _visible_text_details(captured.out)


def test_cli_eval_format_json_report_matches_stdout(tmp_path, capsys, monkeypatch) -> None:
    # Same non-credential sentinel as tests/test_sdk_transport.py. An sk- prefix
    # is a hardcoded-secret finding for the plugin scanner.
    sentinel = "ts_fake_key_sentinel_not_real"
    monkeypatch.setenv("TYPESAFE_API_KEY", sentinel)
    path = tmp_path / "report.json"
    code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(FIXTURES / "replay-unchanged.json"),
            "--format",
            "json",
            "--report",
            str(path),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    written = path.read_text(encoding="utf-8")
    assert written == captured.out
    payload = json.loads(written)
    assert payload["verdict"] == "compatible"
    assert sentinel not in captured.out
    assert sentinel not in written
    assert "TYPESAFE_API_KEY" not in written


def test_cli_format_json_usage_error_leaves_stdout_empty(capsys) -> None:
    code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-latest",
            "--answers",
            str(FIXTURES / "replay-unchanged.json"),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert captured.out == ""
    assert "unpinned" in captured.err


def test_cli_rejects_unknown_format() -> None:
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "eval",
                str(FIXTURES / "support-triage.json"),
                "--candidate-model",
                "jev-1.14",
                "--answers",
                str(FIXTURES / "replay-unchanged.json"),
                "--format",
                "yaml",
            ]
        )
    assert exc.value.code == EXIT_USAGE


def test_cli_report_missing_parent_is_usage_error(tmp_path, capsys) -> None:
    missing = tmp_path / "no-such-dir" / "report.json"
    code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(FIXTURES / "replay-unchanged.json"),
            "--format",
            "json",
            "--report",
            str(missing),
        ]
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert captured.out == ""
    assert not missing.exists()


def test_cli_compare_format_json_unchanged(capsys) -> None:
    code = main(
        [
            "compare",
            str(FIXTURES / "support-triage.json"),
            "--from",
            str(FIXTURES / "replay-baseline.json"),
            "--to",
            "jev-1.14",
            "--answers",
            str(FIXTURES / "replay-unchanged.json"),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["schema"] == "1"
    assert payload["command"] == "compare"
    assert payload["verdict"] == "compatible"
    assert payload["models"]["baseline"] == "jev-1.13"
    assert payload["models"]["candidate"] == "jev-1.14"
    assert payload["models"]["requested_baseline"] == "jev-1.13"
    assert payload["models"]["requested_candidate"] == "jev-1.14"
    assert payload["counts"]["unchanged"] == payload["counts"]["cases"]
    assert "jevcheck compare:" not in captured.out


def test_cli_compare_format_json_breaking_matches_text(tmp_path, capsys) -> None:
    text_code = main(
        [
            "compare",
            str(FIXTURES / "support-triage.json"),
            "--from",
            str(FIXTURES / "replay-baseline.json"),
            "--to",
            "jev-1.14",
            "--answers",
            str(FIXTURES / "replay-breaking.json"),
        ]
    )
    text = capsys.readouterr().out
    assert text_code == 1

    path = tmp_path / "compare-report.json"
    code = main(
        [
            "compare",
            str(FIXTURES / "support-triage.json"),
            "--from",
            str(FIXTURES / "replay-baseline.json"),
            "--to",
            "jev-1.14",
            "--answers",
            str(FIXTURES / "replay-breaking.json"),
            "--format",
            "json",
            "--report",
            str(path),
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    payload = json.loads(captured.out)
    assert path.read_text(encoding="utf-8") == captured.out
    assert payload["command"] == "compare"
    assert payload["verdict"] == "breaking"
    assert _json_visible_details(payload) == _visible_text_details(text)
    assert "general→billing" in _json_visible_details(payload)
    flip = next(
        field
        for case in payload["cases"]
        if case["id"] == "ticket-002"
        for field in case["fields"]
        if field["outcome"] == "answer_flip"
    )
    assert flip["expected"] == "general"
    assert flip["actual"] == "billing"
