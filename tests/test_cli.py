from __future__ import annotations

import subprocess
import sys

from jevcheck.cli import main
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
