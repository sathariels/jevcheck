"""Offline checks for the adopter examples pack (no TYPESAFE_API_KEY)."""

from __future__ import annotations

from jevcheck.cli import main
from tests.helpers import ROOT

EXAMPLES = ROOT / "examples"
CONTRACT = EXAMPLES / "support.json"
BASELINE = EXAMPLES / "replay-baseline.json"
UNCHANGED = EXAMPLES / "replay-unchanged.json"
BREAKING = EXAMPLES / "replay-breaking.json"


def test_example_eval_unchanged_exits_zero() -> None:
    code = main(
        [
            "eval",
            str(CONTRACT),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(UNCHANGED),
        ]
    )
    assert code == 0


def test_example_eval_breaking_exits_one(capsys) -> None:
    code = main(
        [
            "eval",
            str(CONTRACT),
            "--candidate-model",
            "jev-1.14",
            "--answers",
            str(BREAKING),
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "behavioral flips: 1" in captured.out
    assert "confidence regressions: 1" in captured.out
    assert "email-settings intent: general→billing" in captured.out
    assert "billing-charge intent: 0.94→0.71" in captured.out
    assert captured.out.strip().endswith("breaking")


def test_example_compare_unchanged_exits_zero() -> None:
    code = main(
        [
            "compare",
            str(CONTRACT),
            "--from",
            str(BASELINE),
            "--to",
            "jev-1.14",
            "--answers",
            str(UNCHANGED),
        ]
    )
    assert code == 0


def test_example_compare_breaking_exits_one(capsys) -> None:
    code = main(
        [
            "compare",
            str(CONTRACT),
            "--from",
            str(BASELINE),
            "--to",
            "jev-1.14",
            "--answers",
            str(BREAKING),
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "behavioral flips: 1" in captured.out
    assert "confidence regressions: 1" in captured.out
    assert "email-settings intent: general→billing" in captured.out
    assert "billing-charge intent: 0.94→0.71" in captured.out
    assert captured.out.strip().endswith("breaking")


def test_example_record_then_compare_unchanged(tmp_path) -> None:
    recorded = tmp_path / "baseline-answers.json"
    record_code = main(
        [
            "record",
            str(CONTRACT),
            "--answers",
            str(BASELINE),
            "--out",
            str(recorded),
        ]
    )
    assert record_code == 0
    assert recorded.is_file()

    compare_code = main(
        [
            "compare",
            str(CONTRACT),
            "--from",
            str(recorded),
            "--to",
            "jev-1.14",
            "--answers",
            str(UNCHANGED),
        ]
    )
    assert compare_code == 0
