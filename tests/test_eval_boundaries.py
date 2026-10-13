from __future__ import annotations

import pytest

from jevcheck.answers import JevResponse, ScoreAnswer
from jevcheck.contract import Case, Contract, ContractDefaults, FieldExpect
from jevcheck.eval import (
    Outcome,
    evaluate,
    evaluate_case,
    evaluate_field,
    exceeds_tolerance,
    nearest_level,
)
from jevcheck.pinning import ModelIdentityError, UnpinnedModelError
from tests.helpers import choice, noul, response, score


def _choice_contract(*, baseline_confidence: float = 0.8, confidence_tolerance: float = 0.1) -> Contract:
    return Contract.model_validate(
        {
            "baseline_model": "jev-1.13",
            "cases": [
                {
                    "id": "c1",
                    "state": "s",
                    "questions": {
                        "q": {"type": "choice", "criteria": {"a": None, "b": None}}
                    },
                    "expect": {
                        "q": {
                            "choice": "a",
                            "baseline_confidence": baseline_confidence,
                            "confidence_tolerance": confidence_tolerance,
                        }
                    },
                }
            ],
        }
    )


def _noul_contract() -> Contract:
    return Contract.model_validate(
        {
            "baseline_model": "jev-1.13",
            "defaults": {"noul_true_threshold": 0.5, "noul_tolerance": 0.1},
            "cases": [
                {
                    "id": "c1",
                    "state": "s",
                    "questions": {"q": {"type": "noul", "instructions": "yes?"}},
                    "expect": {"q": {"noul_true": True, "noul": 0.8, "noul_tolerance": 0.1}},
                }
            ],
        }
    )


def _score_contract(*, expected: float, tolerance: float) -> Contract:
    return Contract.model_validate(
        {
            "baseline_model": "jev-1.13",
            "defaults": {"score_tolerance": tolerance},
            "cases": [
                {
                    "id": "c1",
                    "state": "s",
                    "questions": {"q": {"type": "score", "criteria": ["lo", "mid", "hi"]}},
                    "expect": {"q": {"score": expected, "score_tolerance": tolerance, "min_confidence": 0.0}},
                }
            ],
        }
    )


def test_drop_exact_decimal_boundary_passes() -> None:
    """0.8 → 0.7 with tolerance 0.1 must pass despite binary 0.10000000000000009."""
    contract = _choice_contract()
    report = evaluate(
        contract,
        lambda case: response("jev-1.14", q=choice("a", 0.7)),
        candidate_model="jev-1.14",
    )
    assert report.breaking is False
    assert report.results[0].outcome is Outcome.UNCHANGED


def test_drop_just_over_decimal_boundary_fails() -> None:
    contract = _choice_contract()
    report = evaluate(
        contract,
        lambda case: response("jev-1.14", q=choice("a", 0.699999)),
        candidate_model="jev-1.14",
    )
    assert report.results[0].outcome is Outcome.CONFIDENCE_REGRESSION


def test_noul_drift_exact_decimal_boundary_passes() -> None:
    contract = _noul_contract()
    report = evaluate(
        contract,
        lambda case: response("jev-1.14", q=noul(0.7)),
        candidate_model="jev-1.14",
    )
    assert report.breaking is False
    assert report.results[0].outcome is Outcome.UNCHANGED


def test_score_decimal_boundary_within_tolerance_is_unchanged() -> None:
    """1.4 vs 1.6 at score_tolerance 0.2 must pass despite binary 0.20000000000000018."""
    contract = _score_contract(expected=1.4, tolerance=0.2)
    actual = ScoreAnswer(
        score=1.6,
        confidence=0.6,
        legend={"1": "mid", "2": "hi"},
        probabilities={"1": 0.4, "2": 0.6},
    )
    report = evaluate(
        contract,
        lambda case: response("jev-1.14", q=actual),
        candidate_model="jev-1.14",
    )
    assert abs(1.6 - 1.4) > 0.2
    assert nearest_level(1.4) != nearest_level(1.6)
    assert report.breaking is False
    assert report.results[0].outcome is Outcome.UNCHANGED


def test_score_decimal_boundary_just_beyond_tolerance_is_flip() -> None:
    contract = _score_contract(expected=1.4, tolerance=0.2)
    actual = ScoreAnswer(
        score=1.600001,
        confidence=0.6,
        legend={"1": "mid", "2": "hi"},
        probabilities={"1": 0.4, "2": 0.6},
    )
    report = evaluate(
        contract,
        lambda case: response("jev-1.14", q=actual),
        candidate_model="jev-1.14",
    )
    assert report.results[0].outcome is Outcome.ANSWER_FLIP


def test_score_same_level_outside_float_tolerance_is_unchanged() -> None:
    """score_tolerance is level-flip suppression, not max |delta|."""
    contract = _score_contract(expected=1.8, tolerance=0.1)
    report = evaluate(
        contract,
        lambda case: response("jev-1.14", q=score(2.2, 0.9)),
        candidate_model="jev-1.14",
    )
    assert nearest_level(1.8) == nearest_level(2.2) == 2
    assert abs(2.2 - 1.8) > 0.1
    assert report.breaking is False
    assert report.results[0].outcome is Outcome.UNCHANGED


def test_evaluate_case_rejects_baseline_only_after_defaults() -> None:
    case = Case.model_validate(
        {
            "id": "c1",
            "state": "s",
            "questions": {"q": {"type": "choice", "criteria": {"a": None, "b": None}}},
            "expect": {"q": {"baseline_confidence": 0.95}},
        }
    )
    with pytest.raises(ValueError, match="baseline_confidence is not an effective"):
        evaluate_case(
            case,
            response("jev-1.14", q=choice("b", 0.51, other="a")),
            defaults=ContractDefaults(),
        )


def test_python_round_ties_toward_even() -> None:
    assert nearest_level(1.5) == 2
    assert nearest_level(2.5) == 2
    assert nearest_level(0.5) == 0
    assert nearest_level(3.5) == 4


def test_wrong_response_model_is_identity_error() -> None:
    contract = _choice_contract()
    with pytest.raises(ModelIdentityError, match="unrelated-model"):
        evaluate(
            contract,
            lambda case: response("unrelated-model", q=choice("a", 0.9)),
            candidate_model="jev-1.14",
        )


def test_evaluate_does_not_report_requested_model_when_response_differs() -> None:
    contract = _choice_contract()
    with pytest.raises(ModelIdentityError):
        evaluate(
            contract,
            lambda case: JevResponse(model="other", answers={"q": choice("a", 0.9)}),
            candidate_model="jev-1.14",
        )


class _BareResponse:
    def __init__(self, model: object, answers: dict) -> None:
        self.model = model
        self.answers = answers


def _floor_contract(*, min_confidence: float) -> Contract:
    return Contract.model_validate(
        {
            "baseline_model": "jev-1.13",
            "cases": [
                {
                    "id": "c1",
                    "state": "s",
                    "questions": {
                        "q": {"type": "choice", "criteria": {"a": None, "b": None}}
                    },
                    "expect": {
                        "q": {
                            "choice": "a",
                            "baseline_confidence": min_confidence,
                            "confidence_tolerance": 0.5,
                            "min_confidence": min_confidence,
                        }
                    },
                }
            ],
        }
    )


def test_exceeds_tolerance_keeps_exact_and_epsilon_boundaries() -> None:
    """Inclusive tolerance: binary overshoot of a decimal tenth stays inside; past 1e-9 does not."""
    assert (0.8 - 0.7) > 0.1
    assert exceeds_tolerance(0.8 - 0.7, 0.1) is False
    assert exceeds_tolerance(0.1, 0.1) is False
    assert exceeds_tolerance(0.1 + 1e-9, 0.1) is False
    assert exceeds_tolerance(0.1 + 2e-9, 0.1) is True
    assert exceeds_tolerance(0.0, 0.0) is False
    assert exceeds_tolerance(-0.4, 0.1) is False


def test_confidence_increase_is_not_a_drop() -> None:
    contract = _choice_contract(baseline_confidence=0.5, confidence_tolerance=0.1)
    report = evaluate(
        contract,
        lambda case: response("jev-1.14", q=choice("a", 0.95)),
        candidate_model="jev-1.14",
    )
    assert report.results[0].outcome is Outcome.UNCHANGED


def test_zero_tolerance_accepts_exact_confidence_and_rejects_a_drop() -> None:
    exact = _choice_contract(baseline_confidence=0.8, confidence_tolerance=0.0)
    passed = evaluate(
        exact,
        lambda case: response("jev-1.14", q=choice("a", 0.8)),
        candidate_model="jev-1.14",
    )
    assert passed.results[0].outcome is Outcome.UNCHANGED
    dropped = evaluate(
        exact,
        lambda case: response("jev-1.14", q=choice("a", 0.799)),
        candidate_model="jev-1.14",
    )
    assert dropped.results[0].outcome is Outcome.CONFIDENCE_REGRESSION


def test_min_confidence_boundary_is_inclusive() -> None:
    contract = Contract.model_validate(
        {
            "baseline_model": "jev-1.13",
            "cases": [
                {
                    "id": "c1",
                    "state": "s",
                    "questions": {
                        "q": {"type": "choice", "criteria": {"a": None, "b": None}}
                    },
                    "expect": {"q": {"choice": "a", "min_confidence": 0.8}},
                }
            ],
        }
    )
    at_floor = evaluate(
        contract,
        lambda case: response("jev-1.14", q=choice("a", 0.8)),
        candidate_model="jev-1.14",
    )
    assert at_floor.results[0].outcome is Outcome.UNCHANGED
    below = evaluate(
        contract,
        lambda case: response("jev-1.14", q=choice("a", 0.7)),
        candidate_model="jev-1.14",
    )
    assert below.results[0].outcome is Outcome.CONFIDENCE_REGRESSION
    assert below.results[0].diffs[0].detail == "0.70 < min 0.80"


def test_choice_constraints_short_circuit_on_flip() -> None:
    """A label change is a flip even when confidence would also miss the floor."""
    contract = _floor_contract(min_confidence=0.9)
    report = evaluate(
        contract,
        lambda case: response("jev-1.14", q=choice("b", 0.4, other="a")),
        candidate_model="jev-1.14",
    )
    diff = report.results[0].diffs[0]
    assert diff.outcome is Outcome.ANSWER_FLIP
    assert diff.detail == "a→b"
    assert report.confidence_regressions == 0


def test_noul_drift_just_past_decimal_boundary_fails() -> None:
    contract = _noul_contract()
    report = evaluate(
        contract,
        lambda case: response("jev-1.14", q=noul(0.699999)),
        candidate_model="jev-1.14",
    )
    assert report.results[0].outcome is Outcome.CONFIDENCE_REGRESSION


def test_noul_upward_drift_past_tolerance_is_regression() -> None:
    contract = Contract.model_validate(
        {
            "baseline_model": "jev-1.13",
            "defaults": {"noul_true_threshold": 0.5},
            "cases": [
                {
                    "id": "c1",
                    "state": "s",
                    "questions": {"q": {"type": "noul", "instructions": "yes?"}},
                    "expect": {"q": {"noul_true": True, "noul": 0.5, "noul_tolerance": 0.1}},
                }
            ],
        }
    )
    report = evaluate(
        contract,
        lambda case: response("jev-1.14", q=noul(0.7)),
        candidate_model="jev-1.14",
    )
    assert report.results[0].outcome is Outcome.CONFIDENCE_REGRESSION
    assert report.results[0].diffs[0].detail == "0.50→0.70"


def test_noul_threshold_boundary_and_min_noul_floor() -> None:
    contract = Contract.model_validate(
        {
            "baseline_model": "jev-1.13",
            "defaults": {"noul_true_threshold": 0.5},
            "cases": [
                {
                    "id": "c1",
                    "state": "s",
                    "questions": {"q": {"type": "noul", "instructions": "yes?"}},
                    "expect": {
                        "q": {
                            "noul_true": True,
                            "noul": 0.8,
                            "noul_tolerance": 0.2,
                            "min_noul": 0.8,
                        }
                    },
                }
            ],
        }
    )
    at_floor = evaluate(
        contract,
        lambda case: response("jev-1.14", q=noul(0.8)),
        candidate_model="jev-1.14",
    )
    assert at_floor.results[0].outcome is Outcome.UNCHANGED
    below_floor = evaluate(
        contract,
        lambda case: response("jev-1.14", q=noul(0.7)),
        candidate_model="jev-1.14",
    )
    assert below_floor.results[0].outcome is Outcome.CONFIDENCE_REGRESSION
    assert "min_noul" in below_floor.results[0].diffs[0].detail

    polarity = Contract.model_validate(
        {
            "baseline_model": "jev-1.13",
            "defaults": {"noul_true_threshold": 0.5},
            "cases": [
                {
                    "id": "c1",
                    "state": "s",
                    "questions": {"q": {"type": "noul", "instructions": "yes?"}},
                    "expect": {"q": {"noul_true": True, "noul": 0.5, "noul_tolerance": 0.1}},
                }
            ],
        }
    )
    on_threshold = evaluate(
        polarity,
        lambda case: response("jev-1.14", q=noul(0.5)),
        candidate_model="jev-1.14",
    )
    assert on_threshold.results[0].outcome is Outcome.UNCHANGED
    under_threshold = evaluate(
        polarity,
        lambda case: response("jev-1.14", q=noul(0.499999)),
        candidate_model="jev-1.14",
    )
    assert under_threshold.results[0].outcome is Outcome.ANSWER_FLIP
    assert "yes→no" in under_threshold.results[0].diffs[0].detail


def test_score_inside_tolerance_still_checks_confidence() -> None:
    """Level-flip suppression does not skip the confidence floor."""
    contract = _score_contract(expected=1.4, tolerance=0.2)
    # _score_contract pins min_confidence at 0.0; override with a real floor.
    contract = contract.model_copy(
        update={
            "cases": [
                contract.cases[0].model_copy(
                    update={
                        "expect": {
                            "q": contract.cases[0].expect["q"].model_copy(
                                update={"min_confidence": 0.9}
                            )
                        }
                    }
                )
            ]
        }
    )
    actual = ScoreAnswer(
        score=1.6,
        confidence=0.4,
        legend={"1": "mid", "2": "hi"},
        probabilities={"1": 0.4, "2": 0.6},
    )
    report = evaluate(
        contract,
        lambda case: response("jev-1.14", q=actual),
        candidate_model="jev-1.14",
    )
    assert nearest_level(1.4) != nearest_level(1.6)
    assert report.results[0].outcome is Outcome.CONFIDENCE_REGRESSION


def test_score_tolerance_zero_exact_match_and_level_boundary() -> None:
    contract = _score_contract(expected=1.5, tolerance=0.0)
    exact = evaluate(
        contract,
        lambda case: response("jev-1.14", q=score(1.5, 0.9)),
        candidate_model="jev-1.14",
    )
    assert exact.results[0].outcome is Outcome.UNCHANGED
    low = 1.5 - 1e-6
    assert nearest_level(1.5) != nearest_level(low)
    flipped = evaluate(
        contract,
        lambda case: response("jev-1.14", q=score(low, 0.9)),
        candidate_model="jev-1.14",
    )
    assert flipped.results[0].outcome is Outcome.ANSWER_FLIP


def test_wrong_answer_type_is_flip_for_each_kind() -> None:
    choice_report = evaluate(
        _choice_contract(),
        lambda case: response("jev-1.14", q=noul(0.9)),
        candidate_model="jev-1.14",
    )
    assert choice_report.results[0].diffs[0].detail == "choice→noul"
    noul_report = evaluate(
        _noul_contract(),
        lambda case: response("jev-1.14", q=choice("a", 0.9)),
        candidate_model="jev-1.14",
    )
    assert noul_report.results[0].diffs[0].detail == "noul→choice"
    score_report = evaluate(
        _score_contract(expected=1.4, tolerance=0.2),
        lambda case: response("jev-1.14", q=choice("a", 0.9)),
        candidate_model="jev-1.14",
    )
    assert score_report.results[0].diffs[0].detail == "score→choice"
    assert score_report.answer_flips == 1


def test_unsupported_question_type_is_flip() -> None:
    diff = evaluate_field(
        case_id="c1",
        field="q",
        question=object(),
        expect=FieldExpect(min_confidence=0.0),
        defaults=ContractDefaults(),
        actual=choice("a", 0.9),
    )
    assert diff.outcome is Outcome.ANSWER_FLIP
    assert diff.detail.startswith("unsupported question type ")


def test_null_and_blank_response_models_are_identity_errors() -> None:
    contract = _choice_contract()
    answers = {"q": choice("a", 0.9)}
    with pytest.raises(ModelIdentityError, match="null"):
        evaluate(
            contract,
            lambda case: _BareResponse(None, answers),
            candidate_model="jev-1.14",
        )
    with pytest.raises(ModelIdentityError, match="nonempty"):
        evaluate(
            contract,
            lambda case: _BareResponse("   ", answers),
            candidate_model="jev-1.14",
        )
    with pytest.raises(ModelIdentityError, match="nonempty"):
        evaluate(
            contract,
            lambda case: _BareResponse("", answers),
            candidate_model="jev-1.14",
        )


def test_padded_concrete_candidate_matches_stripped_pin() -> None:
    contract = _choice_contract()
    report = evaluate(
        contract,
        lambda case: response("jev-1.14", q=choice("a", 0.9)),
        candidate_model="  jev-1.14  ",
    )
    assert report.breaking is False
    assert report.candidate_model == "jev-1.14"


def test_unpinned_candidate_and_fetch_errors() -> None:
    contract = _choice_contract()
    with pytest.raises(UnpinnedModelError):
        evaluate(
            contract,
            lambda case: response("jev-latest", q=choice("a", 0.9)),
            candidate_model="jev-preview",
        )

    def fetch(case: object) -> JevResponse:
        raise RuntimeError("transport down")

    with pytest.raises(RuntimeError, match="transport down"):
        evaluate(contract, fetch, candidate_model="jev-1.14")


def test_noul_polarity_is_inferred_from_expected_float() -> None:
    """noul_true may be omitted; the expected float is compared with the threshold."""
    def contract(expected: float) -> Contract:
        return Contract.model_validate(
            {
                "baseline_model": "jev-1.13",
                "defaults": {"noul_true_threshold": 0.5},
                "cases": [
                    {
                        "id": "c1",
                        "state": "s",
                        "questions": {"q": {"type": "noul", "instructions": "yes?"}},
                        "expect": {"q": {"noul": expected, "noul_tolerance": 0.0}},
                    }
                ],
            }
        )

    on_threshold = evaluate(
        contract(0.5),
        lambda case: response("jev-1.14", q=noul(0.5)),
        candidate_model="jev-1.14",
    )
    assert on_threshold.results[0].outcome is Outcome.UNCHANGED
    below = evaluate(
        contract(0.5),
        lambda case: response("jev-1.14", q=noul(0.2)),
        candidate_model="jev-1.14",
    )
    assert below.results[0].outcome is Outcome.ANSWER_FLIP
    assert "yes→no" in below.results[0].diffs[0].detail
    no_side = evaluate(
        contract(0.49),
        lambda case: response("jev-1.14", q=noul(0.8)),
        candidate_model="jev-1.14",
    )
    assert no_side.results[0].outcome is Outcome.ANSWER_FLIP
    assert "no→yes" in no_side.results[0].diffs[0].detail


def test_missing_answer_labels_noul_and_score() -> None:
    noul_contract = Contract.model_validate(
        {
            "baseline_model": "jev-1.13",
            "defaults": {"noul_true_threshold": 0.5},
            "cases": [
                {
                    "id": "c1",
                    "state": "s",
                    "questions": {"q": {"type": "noul", "instructions": "yes?"}},
                    "expect": {"q": {"noul": 0.2, "noul_tolerance": 0.1}},
                }
            ],
        }
    )
    missing_noul = evaluate(
        noul_contract,
        lambda case: JevResponse(model="jev-1.14", answers={}),
        candidate_model="jev-1.14",
    )
    assert missing_noul.results[0].diffs[0].detail == "missing answer"
    assert missing_noul.results[0].diffs[0].expected == "no"

    missing_score = evaluate(
        _score_contract(expected=1.4, tolerance=0.2),
        lambda case: JevResponse(model="jev-1.14", answers={}),
        candidate_model="jev-1.14",
    )
    assert missing_score.results[0].diffs[0].expected == "1.40"
    assert missing_score.results[0].outcome is Outcome.ANSWER_FLIP


def test_missing_answer_without_a_kind_label() -> None:
    contract = Contract.model_validate(
        {
            "baseline_model": "jev-1.13",
            "cases": [
                {
                    "id": "c1",
                    "state": "s",
                    "questions": {
                        "q": {"type": "choice", "criteria": {"a": None, "b": None}}
                    },
                    "expect": {"q": {"min_confidence": 0.5}},
                }
            ],
        }
    )
    report = evaluate(
        contract,
        lambda case: JevResponse(model="jev-1.14", answers={}),
        candidate_model="jev-1.14",
    )
    assert report.results[0].diffs[0].detail == "missing answer"
    assert report.results[0].diffs[0].expected is None
    assert report.results[0].outcome is Outcome.ANSWER_FLIP


def test_alias_cases_that_resolve_to_different_models_are_listed() -> None:
    contract = Contract.model_validate(
        {
            "baseline_model": "jev-1.13",
            "allow_unpinned": True,
            "cases": [
                {
                    "id": "c1",
                    "state": "s",
                    "questions": {
                        "q": {"type": "choice", "criteria": {"a": None, "b": None}}
                    },
                    "expect": {"q": {"choice": "a", "min_confidence": 0.0}},
                },
                {
                    "id": "c2",
                    "state": "s",
                    "questions": {
                        "q": {"type": "choice", "criteria": {"a": None, "b": None}}
                    },
                    "expect": {"q": {"choice": "a", "min_confidence": 0.0}},
                },
            ],
        }
    )
    models = {"c1": "jev-1.13.0", "c2": "jev-1.14.0"}
    report = evaluate(
        contract,
        lambda case: response(models[case.id], q=choice("a", 0.9)),
        candidate_model="jev-preview",
        allow_unpinned=True,
    )
    assert report.breaking is False
    assert report.candidate_model == "jev-1.13.0, jev-1.14.0"


def test_replay_without_candidate_skips_identity() -> None:
    contract = _choice_contract()
    report = evaluate(
        contract,
        lambda case: response("other-model", q=choice("a", 0.9)),
    )
    assert report.candidate_model is None
    assert report.breaking is False
    assert "(replay)" in report.summary()
