"""Verified System One answer models. Fields match docs/jev-api.md only."""

from __future__ import annotations

import math
from typing import Annotated, Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator

from jevcheck.questions import JSONContent

# Probability maps must be finite, nonnegative, and sum to 1 within this
# absolute tolerance. JSON/IEEE floats will not hit 1.0 exactly for many
# hand-written distributions; 1e-6 is the agreed check, not a fixture-format
# change. Maps that miss this are rejected rather than silently renormalized.
PROBABILITY_SUM_TOLERANCE = 1e-6


class Usage(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    input_tokens: StrictInt | None = None
    output_tokens: StrictInt | None = None


class ChoiceAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: Literal["choice"] = "choice"
    choice: StrictStr
    confidence: float = Field(ge=0.0, le=1.0)
    probabilities: dict[str, float]

    @field_validator("confidence")
    @classmethod
    def _finite_confidence(cls, value: float) -> float:
        return _require_finite(value, "choice confidence")

    @field_validator("probabilities")
    @classmethod
    def _valid_probabilities(cls, value: dict[str, float]) -> dict[str, float]:
        return validate_probability_map(value, what="choice")


class NoulAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: Literal["noul"] = "noul"
    noul: float = Field(ge=0.0, le=1.0)

    @field_validator("noul")
    @classmethod
    def _finite_noul(cls, value: float) -> float:
        return _require_finite(value, "noul")


class ScoreAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: Literal["score"] = "score"
    score: float
    confidence: float = Field(ge=0.0, le=1.0)
    legend: dict[str, JSONContent]
    probabilities: dict[str, float]

    @field_validator("score", "confidence")
    @classmethod
    def _finite_score_fields(cls, value: float) -> float:
        return _require_finite(value, "score field")

    @field_validator("legend", "probabilities", mode="before")
    @classmethod
    def _stringify_int_keys(cls, value: Any) -> Any:
        """SDK 0.7.0 score maps use integer keys; coerce to str without inventing fields."""
        if isinstance(value, Mapping):
            return {str(key): item for key, item in value.items()}
        return value

    @field_validator("legend")
    @classmethod
    def _valid_legend(cls, value: dict[str, JSONContent]) -> dict[str, JSONContent]:
        if not value:
            raise ValueError("score legend must be a nonempty mapping")
        return value

    @field_validator("probabilities")
    @classmethod
    def _valid_probabilities(cls, value: dict[str, float]) -> dict[str, float]:
        return validate_probability_map(value, what="score")


Answer = Annotated[
    NoulAnswer | ChoiceAnswer | ScoreAnswer,
    Field(discriminator="type"),
]


class JevResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    model: StrictStr
    usage: Usage = Field(default_factory=Usage)
    answers: dict[str, Answer] = Field(default_factory=dict)

    @field_validator("model")
    @classmethod
    def _nonempty_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("response.model must be a nonempty string")
        return value


def mapped_confidence(answer: NoulAnswer | ChoiceAnswer | ScoreAnswer) -> float:
    """Scalar used for floors, regressions, and the optional Gate helper."""
    if isinstance(answer, NoulAnswer):
        return answer.noul
    return answer.confidence


def adapt_answer(raw: Any) -> NoulAnswer | ChoiceAnswer | ScoreAnswer:
    """Accept SDK models, namespaces, or verified dicts.

    Missing choice or score probabilities are rejected (not replaced with ``{}``).
    Score ``legend`` is required and nonempty, matching SDK-shaped responses.
    Score ``legend`` / ``probabilities`` integer keys from typesafe-sdk 0.7.0
    are stringified so they match this schema.
    """
    if isinstance(raw, (NoulAnswer, ChoiceAnswer, ScoreAnswer)):
        return raw
    data = _to_mapping(raw)
    kind = data.get("type")
    if kind == "noul" or ("noul" in data and "choice" not in data and "score" not in data):
        return NoulAnswer.model_validate({"type": "noul", "noul": data["noul"]})
    if kind == "choice" or "choice" in data:
        payload: dict[str, Any] = {
            "type": "choice",
            "choice": data["choice"],
            "confidence": data["confidence"],
        }
        if "probabilities" in data:
            payload["probabilities"] = data["probabilities"]
        return ChoiceAnswer.model_validate(payload)
    if kind == "score" or "score" in data:
        payload = {
            "type": "score",
            "score": data["score"],
            "confidence": data["confidence"],
        }
        if "legend" in data:
            payload["legend"] = data["legend"]
        if "probabilities" in data:
            payload["probabilities"] = data["probabilities"]
        return ScoreAnswer.model_validate(payload)
    raise ValueError(f"unsupported answer object: {raw!r}")


def adapt_response(raw: Any) -> JevResponse:
    if isinstance(raw, JevResponse):
        return raw
    data = _to_mapping(raw)
    model = data.get("model", _MISSING)
    if model is _MISSING:
        raise ValueError("response.model is required")
    if model is None:
        raise ValueError("response.model must not be null")
    if not isinstance(model, str):
        raise ValueError(f"response.model must be a string, not {type(model).__name__}")
    answers_raw = data.get("answers") or {}
    if not isinstance(answers_raw, Mapping):
        raise TypeError("response.answers must be a mapping")
    usage_raw = data.get("usage") or {}
    return JevResponse(
        model=model,
        usage=Usage.model_validate(_to_mapping(usage_raw) if usage_raw is not None else {}),
        answers={str(name): adapt_answer(answer) for name, answer in answers_raw.items()},
    )


def validate_probability_map(value: Any, *, what: str) -> dict[str, float]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"{what} probabilities must be a nonempty mapping")
    cleaned: dict[str, float] = {}
    for key, raw in value.items():
        name = str(key)
        try:
            number = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{what} probability {name!r} must be a finite number") from exc
        if not math.isfinite(number):
            raise ValueError(f"{what} probability {name!r} must be finite")
        if number < 0.0:
            raise ValueError(f"{what} probability {name!r} must be >= 0")
        cleaned[name] = number
    total = math.fsum(cleaned.values())
    if abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE:
        raise ValueError(
            f"{what} probabilities must sum to 1 ± {PROBABILITY_SUM_TOLERANCE}; got {total}"
        )
    return cleaned


def _require_finite(value: float, what: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{what} must be a finite number")
    return value


def _to_mapping(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if hasattr(raw, "model_dump"):
        dumped = raw.model_dump()
        if isinstance(dumped, Mapping):
            return dict(dumped)
    skip = {"model_config", "model_fields", "model_computed_fields"}
    if hasattr(raw, "__dict__"):
        return {k: v for k, v in vars(raw).items() if not k.startswith("_") and k not in skip}
    public = {
        name: getattr(raw, name)
        for name in dir(raw)
        if not name.startswith("_") and not callable(getattr(raw, name, None))
    }
    if public:
        return public
    raise TypeError(f"cannot adapt {type(raw).__name__} to a mapping")


_MISSING = object()
