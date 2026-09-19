"""Verified System One answer models. Fields match docs/jev-api.md only."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from jevcheck.questions import JSONContent


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


class NoulAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: Literal["noul"] = "noul"
    noul: float = Field(ge=0.0, le=1.0)


class ScoreAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: Literal["score"] = "score"
    score: float
    confidence: float = Field(ge=0.0, le=1.0)
    legend: dict[str, JSONContent] = Field(default_factory=dict)
    probabilities: dict[str, float] = Field(default_factory=dict)


Answer = Annotated[
    NoulAnswer | ChoiceAnswer | ScoreAnswer,
    Field(discriminator="type"),
]


class JevResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    model: StrictStr
    usage: Usage = Field(default_factory=Usage)
    answers: dict[str, Answer] = Field(default_factory=dict)


def mapped_confidence(answer: NoulAnswer | ChoiceAnswer | ScoreAnswer) -> float:
    """Scalar used for floors, regressions, and the optional Gate helper."""
    if isinstance(answer, NoulAnswer):
        return answer.noul
    return answer.confidence


def adapt_answer(raw: Any) -> NoulAnswer | ChoiceAnswer | ScoreAnswer:
    """Accept SDK models, namespaces, or verified dicts."""
    if isinstance(raw, (NoulAnswer, ChoiceAnswer, ScoreAnswer)):
        return raw
    data = _to_mapping(raw)
    kind = data.get("type")
    if kind == "noul" or ("noul" in data and "choice" not in data and "score" not in data):
        return NoulAnswer.model_validate({"type": "noul", "noul": data["noul"]})
    if kind == "choice" or "choice" in data:
        return ChoiceAnswer.model_validate(
            {
                "type": "choice",
                "choice": data["choice"],
                "confidence": data["confidence"],
                "probabilities": data.get("probabilities") or {},
            }
        )
    if kind == "score" or "score" in data:
        return ScoreAnswer.model_validate(
            {
                "type": "score",
                "score": data["score"],
                "confidence": data["confidence"],
                "legend": data.get("legend") or {},
                "probabilities": data.get("probabilities") or {},
            }
        )
    raise ValueError(f"unsupported answer object: {raw!r}")


def adapt_response(raw: Any) -> JevResponse:
    if isinstance(raw, JevResponse):
        return raw
    data = _to_mapping(raw)
    answers_raw = data.get("answers") or {}
    if not isinstance(answers_raw, Mapping):
        raise TypeError("response.answers must be a mapping")
    usage_raw = data.get("usage") or {}
    return JevResponse(
        model=str(data["model"]),
        usage=Usage.model_validate(_to_mapping(usage_raw) if usage_raw is not None else {}),
        answers={str(name): adapt_answer(answer) for name, answer in answers_raw.items()},
    )


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
