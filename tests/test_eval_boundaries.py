from __future__ import annotations

import pytest

from jevcheck.answers import JevResponse
from jevcheck.contract import Contract
from jevcheck.eval import Outcome, evaluate, nearest_level
from jevcheck.pinning import ModelIdentityError
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
