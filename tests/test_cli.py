from __future__ import annotations

import json
import subprocess
import sys

from jevcheck.cli import EXIT_USAGE, main
from tests.helpers import FIXTURES


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
