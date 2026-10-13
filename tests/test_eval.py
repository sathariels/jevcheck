from __future__ import annotations

from jevcheck.answers import JevResponse
from jevcheck.contract import Contract, load_replay
from jevcheck.eval import Outcome, evaluate
from tests.helpers import FIXTURES, choice, noul, response, score


def test_detects_choice_flip_and_confidence_drop(contract: Contract) -> None:
    replay = {
        "ticket-001": response(
            "jev-1.14",
            intent=choice("billing", 0.93),
            billing=noul(0.95),
            urgency=score(1.9, 0.9),
        ),
        "ticket-002": response("jev-1.14", intent=choice("billing", 0.81)),
        "ticket-003": response(
            "jev-1.14",
            intent=choice("billing", 0.71),
            urgency=score(2.0, 0.71),
        ),
    }

    report = evaluate(contract, lambda case: replay[case.id], candidate_model="jev-1.14")

    assert report.cases_checked == 3
    assert report.unchanged == 1
    assert report.answer_flips == 1
    assert report.confidence_regressions == 1
    assert report.breaking

    flip = next(diff for diff in report.diffs if diff.case_id == "ticket-002")
    assert flip.outcome is Outcome.ANSWER_FLIP
    assert flip.detail == "general→billing"

    regressions = [
        diff
        for diff in report.diffs
        if diff.case_id == "ticket-003" and diff.outcome is Outcome.CONFIDENCE_REGRESSION
    ]
    assert any("0.94→0.71" in diff.detail for diff in regressions)
    assert "general→billing" in report.summary()
    assert "0.94→0.71" in report.summary()


def test_unchanged_when_candidate_matches(contract: Contract) -> None:
    replay = load_replay(FIXTURES / "replay-unchanged.json")
    report = evaluate(contract, lambda case: replay[case.id], candidate_model="jev-1.14")
    assert report.breaking is False
    assert report.unchanged == 3
    assert report.answer_flips == 0
    assert report.confidence_regressions == 0
    assert "compatible" in report.summary()


def test_noul_polarity_flip(contract: Contract) -> None:
    replay = {
        "ticket-001": response(
            "jev-1.14",
            intent=choice("billing", 0.93),
            billing=noul(0.12),
            urgency=score(1.9, 0.9),
        ),
        "ticket-002": response("jev-1.14", intent=choice("general", 0.88)),
        "ticket-003": response(
            "jev-1.14",
            intent=choice("billing", 0.92),
            urgency=score(2.0, 0.91),
        ),
    }
    report = evaluate(contract, lambda case: replay[case.id], candidate_model="jev-1.14")
    billing = next(diff for diff in report.diffs if diff.field == "billing")
    assert billing.outcome is Outcome.ANSWER_FLIP
    assert "yes→no" in billing.detail


def test_noul_uses_noul_as_confidence_scalar(contract: Contract) -> None:
    replay = {
        "ticket-001": response(
            "jev-1.14",
            intent=choice("billing", 0.93),
            billing=noul(0.61),
            urgency=score(1.9, 0.9),
        ),
        "ticket-002": response("jev-1.14", intent=choice("general", 0.88)),
        "ticket-003": response(
            "jev-1.14",
            intent=choice("billing", 0.92),
            urgency=score(2.0, 0.91),
        ),
    }
    report = evaluate(contract, lambda case: replay[case.id], candidate_model="jev-1.14")
    billing = next(diff for diff in report.diffs if diff.field == "billing")
    assert billing.outcome is Outcome.CONFIDENCE_REGRESSION
    assert report.results[0].outcome is Outcome.CONFIDENCE_REGRESSION


def test_score_level_flip(contract: Contract) -> None:
    replay = {
        "ticket-001": response(
            "jev-1.14",
            intent=choice("billing", 0.93),
            billing=noul(0.95),
            urgency=score(0.2, 0.9),
        ),
        "ticket-002": response("jev-1.14", intent=choice("general", 0.88)),
        "ticket-003": response(
            "jev-1.14",
            intent=choice("billing", 0.92),
            urgency=score(2.0, 0.91),
        ),
    }
    report = evaluate(contract, lambda case: replay[case.id], candidate_model="jev-1.14")
    urgency = next(
        diff for diff in report.diffs if diff.case_id == "ticket-001" and diff.field == "urgency"
    )
    assert urgency.outcome is Outcome.ANSWER_FLIP
    assert urgency.detail == "2.00→0.20"


def test_missing_answer_is_flip(contract: Contract) -> None:
    replay = {
        "ticket-001": JevResponse(model="jev-1.14", answers={}),
        "ticket-002": response("jev-1.14", intent=choice("general", 0.88)),
        "ticket-003": response(
            "jev-1.14",
            intent=choice("billing", 0.92),
            urgency=score(2.0, 0.91),
        ),
    }
    report = evaluate(contract, lambda case: replay[case.id], candidate_model="jev-1.14")
    assert report.results[0].outcome is Outcome.ANSWER_FLIP
    assert any(diff.detail == "missing answer" for diff in report.results[0].diffs)


def test_flip_outranks_regression_across_expectations(contract: Contract) -> None:
    """One case can carry a flip, a regression, and an unchanged field. The case counts once, as a flip."""
    replay = {
        "ticket-001": response(
            "jev-1.14",
            intent=choice("general", 0.93),
            billing=noul(0.61),
            urgency=score(2.0, 0.91),
        ),
        "ticket-002": response("jev-1.14", intent=choice("general", 0.88)),
        "ticket-003": response(
            "jev-1.14",
            intent=choice("billing", 0.92),
            urgency=score(2.0, 0.91),
        ),
    }
    report = evaluate(contract, lambda case: replay[case.id], candidate_model="jev-1.14")
    by_field = {diff.field: diff.outcome for diff in report.results[0].diffs}
    assert by_field == {
        "intent": Outcome.ANSWER_FLIP,
        "billing": Outcome.CONFIDENCE_REGRESSION,
        "urgency": Outcome.UNCHANGED,
    }
    assert report.results[0].outcome is Outcome.ANSWER_FLIP
    assert report.answer_flips == 1
    assert report.confidence_regressions == 0
    assert report.unchanged == 2
    assert "billing→general" in report.summary()
    assert "unchanged" not in report.summary().split("behavioral flips:")[1].split("breaking")[0]


def test_regression_when_only_one_expectation_drops(contract: Contract) -> None:
    replay = {
        "ticket-001": response(
            "jev-1.14",
            intent=choice("billing", 0.80),
            billing=noul(0.95),
            urgency=score(1.9, 0.9),
        ),
        "ticket-002": response("jev-1.14", intent=choice("general", 0.88)),
        "ticket-003": response(
            "jev-1.14",
            intent=choice("billing", 0.92),
            urgency=score(2.0, 0.91),
        ),
    }
    report = evaluate(contract, lambda case: replay[case.id], candidate_model="jev-1.14")
    by_field = {diff.field: diff.outcome for diff in report.results[0].diffs}
    assert by_field["intent"] is Outcome.CONFIDENCE_REGRESSION
    assert by_field["billing"] is Outcome.UNCHANGED
    assert by_field["urgency"] is Outcome.UNCHANGED
    assert report.results[0].outcome is Outcome.CONFIDENCE_REGRESSION
    assert report.confidence_regressions == 1
    assert report.answer_flips == 0


def test_missing_one_of_several_answers_is_flip(contract: Contract) -> None:
    replay = {
        "ticket-001": response(
            "jev-1.14",
            intent=choice("billing", 0.93),
            urgency=score(1.9, 0.9),
        ),
        "ticket-002": response("jev-1.14", intent=choice("general", 0.88)),
        "ticket-003": response(
            "jev-1.14",
            intent=choice("billing", 0.92),
            urgency=score(2.0, 0.91),
        ),
    }
    report = evaluate(contract, lambda case: replay[case.id], candidate_model="jev-1.14")
    missing = next(diff for diff in report.results[0].diffs if diff.field == "billing")
    assert missing.outcome is Outcome.ANSWER_FLIP
    assert missing.detail == "missing answer"
    assert missing.expected == "yes"
    assert report.results[0].outcome is Outcome.ANSWER_FLIP
