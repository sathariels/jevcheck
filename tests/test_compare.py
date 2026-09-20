from __future__ import annotations

import json

import pytest

from jevcheck.cli import EXIT_USAGE, main
from jevcheck.compare import compare, contract_from_baseline, record_answers
from jevcheck.contract import Contract, load_replay, write_replay
from jevcheck.eval import Outcome
from jevcheck.pinning import ModelIdentityError, UnpinnedModelError
from tests.helpers import FIXTURES, choice, noul, response, score


def test_record_then_eval_baseline_against_fixture(contract: Contract, tmp_path) -> None:
    """Recorded replay is the v0.1 --answers format and can sanity-check the pin."""
    baseline = load_replay(FIXTURES / "replay-baseline.json")
    recorded = record_answers(contract, lambda case: baseline[case.id])
    out = tmp_path / "baseline.json"
    write_replay(out, recorded)

    code = main(
        [
            "eval",
            str(FIXTURES / "support-triage.json"),
            "--candidate-model",
            "jev-1.13",
            "--answers",
            str(out),
        ]
    )
    assert code == 0


def test_record_then_compare_detects_flip_and_regression(contract: Contract) -> None:
    baseline = load_replay(FIXTURES / "replay-baseline.json")
    recorded = record_answers(contract, lambda case: baseline[case.id])
    candidate = load_replay(FIXTURES / "replay-breaking.json")

    report = compare(
        contract,
        recorded,
        lambda case: candidate[case.id],
        candidate_model="jev-1.14",
    )

    assert report.mode == "compare"
    assert report.breaking
    assert report.answer_flips == 1
    assert report.confidence_regressions == 1
    flip = next(diff for diff in report.diffs if diff.case_id == "ticket-002")
    assert flip.outcome is Outcome.ANSWER_FLIP
    assert flip.detail == "general→billing"
    assert any("0.92→0.71" in diff.detail or "0.91→0.71" in diff.detail for diff in report.diffs)
    assert "jevcheck compare:" in report.summary()


def test_compare_compatible_when_candidate_matches_baseline(contract: Contract) -> None:
    baseline = load_replay(FIXTURES / "replay-baseline.json")
    candidate = load_replay(FIXTURES / "replay-unchanged.json")
    report = compare(
        contract,
        baseline,
        lambda case: candidate[case.id],
        candidate_model="jev-1.14",
    )
    assert report.breaking is False
    assert report.unchanged == 3
    assert report.summary().strip().endswith("compatible")


def test_compare_identity_mismatch_on_recorded_baseline(contract: Contract) -> None:
    wrong = {
        case_id: response(
            "unrelated-model",
            **replay.answers,
        )
        for case_id, replay in load_replay(FIXTURES / "replay-baseline.json").items()
    }
    candidate = load_replay(FIXTURES / "replay-unchanged.json")
    with pytest.raises(ModelIdentityError, match="does not match"):
        compare(
            contract,
            wrong,
            lambda case: candidate[case.id],
            candidate_model="jev-1.14",
        )


def test_compare_identity_mismatch_on_candidate(contract: Contract) -> None:
    baseline = load_replay(FIXTURES / "replay-baseline.json")
    with pytest.raises(ModelIdentityError, match="does not match"):
        compare(
            contract,
            baseline,
            lambda case: response("unrelated-model", intent=choice("general", 0.88)),
            candidate_model="jev-1.14",
        )


def test_compare_missing_baseline_case(contract: Contract) -> None:
    baseline = load_replay(FIXTURES / "replay-baseline.json")
    del baseline["ticket-002"]
    candidate = load_replay(FIXTURES / "replay-unchanged.json")
    with pytest.raises(KeyError, match="missing cases"):
        compare(
            contract,
            baseline,
            lambda case: candidate[case.id],
            candidate_model="jev-1.14",
        )


def test_compare_missing_baseline_field(contract: Contract) -> None:
    baseline = load_replay(FIXTURES / "replay-baseline.json")
    thin = dict(baseline)
    thin["ticket-001"] = response("jev-1.13", intent=choice("billing", 0.93))
    candidate = load_replay(FIXTURES / "replay-unchanged.json")
    with pytest.raises(KeyError, match="ticket-001"):
        compare(
            contract,
            thin,
            lambda case: candidate[case.id],
            candidate_model="jev-1.14",
        )


def test_record_rejects_unpinned_baseline(contract: Contract) -> None:
    with pytest.raises(UnpinnedModelError):
        record_answers(
            contract,
            lambda case: response("jev-latest", intent=choice("billing", 0.9)),
            baseline_model="jev-latest",
        )


def test_record_identity_mismatch(contract: Contract) -> None:
    with pytest.raises(ModelIdentityError, match="does not match"):
        record_answers(
            contract,
            lambda case: response("jev-1.14", intent=choice("billing", 0.9)),
        )


def test_record_missing_field(contract: Contract) -> None:
    with pytest.raises(KeyError, match="fields"):
        record_answers(
            contract,
            lambda case: response("jev-1.13", intent=choice("billing", 0.93)),
        )


def test_wrong_kind_baseline_is_usage_error(contract: Contract) -> None:
    baseline = load_replay(FIXTURES / "replay-baseline.json")
    broken = dict(baseline)
    broken["ticket-001"] = response(
        "jev-1.13",
        intent=noul(0.9),
        billing=noul(0.95),
        urgency=score(1.9, 0.9),
    )
    with pytest.raises(TypeError, match="expected choice"):
        contract_from_baseline(contract, broken)


def test_cli_record_then_compare_breaking(tmp_path, capsys) -> None:
    out = tmp_path / "recorded.json"
    record_code = main(
        [
            "record",
            str(FIXTURES / "support-triage.json"),
            "--out",
            str(out),
            "--answers",
            str(FIXTURES / "replay-baseline.json"),
        ]
    )
    captured = capsys.readouterr()
    assert record_code == 0
    assert "wrote:" in captured.out
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ticket-001"]["model"] == "jev-1.13"
    assert "intent" in payload["ticket-001"]["answers"]

    code = main(
        [
            "compare",
            str(FIXTURES / "support-triage.json"),
            "--from",
            str(out),
            "--to",
            "jev-1.14",
            "--answers",
            str(FIXTURES / "replay-breaking.json"),
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "jevcheck compare:" in captured.out
    assert "general→billing" in captured.out
    assert captured.out.strip().endswith("breaking")


def test_cli_compare_missing_candidate_answers(tmp_path, capsys) -> None:
    replay = tmp_path / "one-case.json"
    replay.write_text(
        json.dumps(
            {
                "ticket-001": {
                    "model": "jev-1.14",
                    "answers": {
                        "intent": {
                            "type": "choice",
                            "choice": "billing",
                            "confidence": 0.93,
                            "probabilities": {"billing": 0.93, "general": 0.07},
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    code = main(
        [
            "compare",
            str(FIXTURES / "support-triage.json"),
            "--from",
            str(FIXTURES / "replay-baseline.json"),
            "--to",
            "jev-1.14",
            "--answers",
            str(replay),
        ]
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "missing cases" in captured.err


def test_cli_compare_identity_mismatch(capsys) -> None:
    code = main(
        [
            "compare",
            str(FIXTURES / "support-triage.json"),
            "--from",
            str(FIXTURES / "replay-unchanged.json"),
            "--to",
            "jev-1.14",
            "--answers",
            str(FIXTURES / "replay-unchanged.json"),
        ]
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "does not match" in captured.err
    assert "jev-1.14" in captured.err


def test_cli_record_live_without_key(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    code = main(
        [
            "record",
            str(FIXTURES / "support-triage.json"),
            "--out",
            str(tmp_path / "out.json"),
        ]
    )
    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "TYPESAFE_API_KEY" in captured.err


def test_cli_eval_fixture_path_unchanged(capsys) -> None:
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
    captured = capsys.readouterr()
    assert code == 0
    assert "jevcheck eval:" in captured.out
    assert captured.out.strip().endswith("compatible")
