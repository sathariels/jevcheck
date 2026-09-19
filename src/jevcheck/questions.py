"""Verified System One question models. Fields match docs/jev-api.md only."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

JSONValue = str | int | float | bool | list[Any] | dict[str, Any]
JSONContent = str | dict[str, JSONValue | None] | list[JSONValue | None]


class NoulCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    true: JSONContent | None = None
    false: JSONContent | None = None


class NoulQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["noul"] = "noul"
    instructions: JSONContent | None = None
    criteria: NoulCriteria | None = None


class ChoiceQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["choice"] = "choice"
    instructions: JSONContent | None = None
    criteria: dict[str, JSONContent | None]

    @field_validator("criteria")
    @classmethod
    def _nonempty_criteria(cls, value: dict[str, JSONContent | None]) -> dict[str, JSONContent | None]:
        if not value:
            raise ValueError("choice criteria must be a nonempty mapping")
        return value


class ScoreQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["score"] = "score"
    instructions: JSONContent | None = None
    criteria: list[JSONContent]

    @field_validator("criteria")
    @classmethod
    def _nonempty_criteria(cls, value: list[JSONContent]) -> list[JSONContent]:
        if not value:
            raise ValueError("score criteria must be a nonempty sequence")
        return value


Question = Annotated[
    NoulQuestion | ChoiceQuestion | ScoreQuestion,
    Field(discriminator="type"),
]


def parse_question(raw: Any) -> NoulQuestion | ChoiceQuestion | ScoreQuestion:
    if isinstance(raw, (NoulQuestion, ChoiceQuestion, ScoreQuestion)):
        return raw
    if isinstance(raw, Mapping):
        kind = raw.get("type")
        if kind == "noul":
            return NoulQuestion.model_validate(raw)
        if kind == "choice":
            return ChoiceQuestion.model_validate(raw)
        if kind == "score":
            return ScoreQuestion.model_validate(raw)
        raise ValueError(f"question type must be noul, choice, or score; got {kind!r}")
    type_name = type(raw).__name__
    if type_name == "Noul" or getattr(raw, "type", None) == "noul":
        return NoulQuestion.model_validate(_question_dump(raw, "noul"))
    if type_name == "Choice" or getattr(raw, "type", None) == "choice":
        return ChoiceQuestion.model_validate(_question_dump(raw, "choice"))
    if type_name == "Score" or getattr(raw, "type", None) == "score":
        return ScoreQuestion.model_validate(_question_dump(raw, "score"))
    raise TypeError(f"unsupported question: {raw!r}")


def question_wire(question: NoulQuestion | ChoiceQuestion | ScoreQuestion) -> dict[str, Any]:
    """SDK-accepted question dictionary."""
    return question.model_dump(exclude_none=True)


def _question_dump(raw: Any, kind: str) -> dict[str, Any]:
    if hasattr(raw, "model_dump"):
        data = dict(raw.model_dump())
    else:
        data = {
            "instructions": getattr(raw, "instructions", None),
            "criteria": getattr(raw, "criteria", None),
        }
    data["type"] = kind
    return data
