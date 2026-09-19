from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from jevcheck.answers import (
    ChoiceAnswer,
    ScoreAnswer,
    adapt_answer,
    adapt_response,
    validate_probability_map,
)


def test_score_answer_coerces_integer_keys() -> None:
    answer = ScoreAnswer.model_validate(
        {
            "type": "score",
            "score": 1.7,
            "confidence": 0.88,
            "legend": {0: "can wait", 1: "this week", 2: "today"},
            "probabilities": {0: 0.1, 1: 0.1, 2: 0.8},
        }
    )
    assert answer.legend == {"0": "can wait", "1": "this week", "2": "today"}
    assert answer.probabilities == {"0": 0.1, "1": 0.1, "2": 0.8}


def test_adapt_answer_does_not_invent_empty_choice_probabilities() -> None:
    with pytest.raises(ValidationError):
        adapt_answer({"type": "choice", "choice": "a", "confidence": 0.9})


@pytest.mark.parametrize(
    "probabilities",
    [
        None,
        {},
        {"1": -0.1, "2": 1.1},
        {"1": math.nan, "2": 1.0},
        {"1": 0.2, "2": 0.2},
    ],
)
def test_score_probability_maps_rejected(probabilities) -> None:
    """Recheck P2: null or empty (or otherwise invalid) score probabilities fail."""
    payload = {
        "type": "score",
        "score": 2,
        "confidence": 0.9,
        "legend": {"1": "this week", "2": "today"},
        "probabilities": probabilities,
    }
    with pytest.raises((ValidationError, ValueError, TypeError)):
        adapt_answer(payload)


def test_score_probabilities_omitted_rejected() -> None:
    with pytest.raises((ValidationError, ValueError)):
        adapt_answer(
            {
                "type": "score",
                "score": 2,
                "confidence": 0.9,
                "legend": {"2": "today"},
            }
        )


def test_score_legend_omitted_or_empty_rejected() -> None:
    with pytest.raises((ValidationError, ValueError)):
        adapt_answer(
            {
                "type": "score",
                "score": 2,
                "confidence": 0.9,
                "probabilities": {"2": 1.0},
            }
        )
    with pytest.raises((ValidationError, ValueError)):
        adapt_answer(
            {
                "type": "score",
                "score": 2,
                "confidence": 0.9,
                "legend": {},
                "probabilities": {"2": 1.0},
            }
        )
    with pytest.raises((ValidationError, ValueError, TypeError)):
        adapt_answer(
            {
                "type": "score",
                "score": 2,
                "confidence": 0.9,
                "legend": None,
                "probabilities": {"2": 1.0},
            }
        )


def test_sdk_shaped_score_maps_still_adapt() -> None:
    adapted = adapt_answer(
        {
            "type": "score",
            "score": 1.6,
            "confidence": 0.6,
            "legend": {1: "mid", 2: "hi"},
            "probabilities": {1: 0.4, 2: 0.6},
        }
    )
    assert adapted.legend == {"1": "mid", "2": "hi"}
    assert adapted.probabilities == {"1": 0.4, "2": 0.6}


@pytest.mark.parametrize(
    "probabilities",
    [
        None,
        {},
        {"a": -0.1, "b": 1.1},
        {"a": math.nan, "b": 1.0},
        {"a": 0.2, "b": 0.2},
    ],
)
def test_choice_probability_maps_rejected(probabilities) -> None:
    payload = {"type": "choice", "choice": "a", "confidence": 0.8, "probabilities": probabilities}
    with pytest.raises((ValidationError, ValueError, TypeError)):
        adapt_answer(payload)


def test_null_model_is_rejected_not_stringified() -> None:
    with pytest.raises(ValueError, match="must not be null"):
        adapt_response({"model": None, "answers": {}})
    with pytest.raises(ValidationError):
        adapt_response({"model": "", "answers": {}})
    with pytest.raises(ValueError, match="must be a string"):
        adapt_response({"model": 12, "answers": {}})


def test_non_mapping_answers_raise_type_error() -> None:
    with pytest.raises(TypeError, match="mapping"):
        adapt_response({"model": "jev-1.13.0", "answers": ["nope"]})


def test_probability_sum_tolerance_is_one_e_minus_6() -> None:
    almost = {"a": 0.5, "b": 0.5 + 5e-7}
    validate_probability_map(almost, what="choice")
    with pytest.raises(ValueError, match="sum"):
        validate_probability_map({"a": 0.5, "b": 0.5 + 2e-6}, what="choice")


def test_nan_score_rejected_at_schema() -> None:
    with pytest.raises(ValidationError):
        ScoreAnswer.model_validate(
            {
                "type": "score",
                "score": math.nan,
                "confidence": 0.9,
                "legend": {"0": "can wait"},
                "probabilities": {"0": 1.0},
            }
        )


def test_choice_answer_requires_finite_confidence() -> None:
    with pytest.raises(ValidationError):
        ChoiceAnswer.model_validate(
            {
                "choice": "a",
                "confidence": math.inf,
                "probabilities": {"a": 1.0},
            }
        )
