"""Production contract schema (JSON / JSONL). See docs/contract.md."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from jevcheck.answers import JevResponse, adapt_response
from jevcheck.pinning import require_pinned
from jevcheck.questions import (
    ChoiceQuestion,
    JSONContent,
    NoulQuestion,
    Question,
    ScoreQuestion,
    parse_question,
)

# Keys that only apply to one question kind. Shared confidence keys may
# appear on any field. This is an applicability check — the JSON schema
# of FieldExpect is unchanged.
_CHOICE_ONLY = frozenset({"choice"})
_NOUL_ONLY = frozenset({"noul", "noul_true", "min_noul", "noul_tolerance"})
_SCORE_ONLY = frozenset({"score", "score_tolerance"})


class ContractDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_tolerance: float | None = Field(default=None, ge=0.0, le=1.0)
    noul_true_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    noul_tolerance: float | None = Field(default=None, ge=0.0, le=1.0)
    score_tolerance: float | None = Field(default=0.5, ge=0.0)


class FieldExpect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    choice: str | None = None
    noul: float | None = Field(default=None, ge=0.0, le=1.0)
    noul_true: bool | None = None
    min_noul: float | None = Field(default=None, ge=0.0, le=1.0)
    noul_tolerance: float | None = Field(default=None, ge=0.0, le=1.0)
    score: float | None = None
    score_tolerance: float | None = Field(default=None, ge=0.0)
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    baseline_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_tolerance: float | None = Field(default=None, ge=0.0, le=1.0)


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    state: JSONContent
    questions: dict[str, Question]
    expect: dict[str, FieldExpect]

    @model_validator(mode="before")
    @classmethod
    def _parse_questions(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        raw_q = data.get("questions")
        if not isinstance(raw_q, Mapping):
            return data
        parsed = dict(data)
        parsed["questions"] = {str(name): parse_question(question) for name, question in raw_q.items()}
        return parsed

    @model_validator(mode="after")
    def _expect_matches_questions(self) -> Case:
        if not self.questions:
            raise ValueError(f"case {self.id!r} must declare at least one question")
        if not self.expect:
            raise ValueError(f"case {self.id!r} must declare at least one expectation")
        unknown = sorted(set(self.expect) - set(self.questions))
        if unknown:
            raise ValueError(f"case {self.id!r} expects unknown questions: {unknown}")
        for name, expect in self.expect.items():
            _require_applicable_expect(self.id, name, self.questions[name], expect)
        return self


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "0.1"
    name: str | None = None
    baseline_model: str
    allow_unpinned: bool = False
    defaults: ContractDefaults = Field(default_factory=ContractDefaults)
    cases: list[Case]

    @model_validator(mode="after")
    def _version_and_ids(self) -> Contract:
        if self.version != "0.1":
            raise ValueError(f"unsupported contract version {self.version!r}; v0.1 only")
        if not self.cases:
            raise ValueError("contract must contain at least one case")
        ids = [case.id for case in self.cases]
        dupes = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
        if dupes:
            raise ValueError(f"duplicate case ids: {dupes}")
        require_pinned(self.baseline_model, allow_unpinned=self.allow_unpinned)
        return self

    def case_by_id(self) -> dict[str, Case]:
        return {case.id: case for case in self.cases}


def load_contract(
    path: str | Path,
    *,
    baseline_model: str | None = None,
    allow_unpinned: bool | None = None,
) -> Contract:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    if source.suffix == ".jsonl":
        return _load_jsonl(
            text, source, baseline_model=baseline_model, allow_unpinned=allow_unpinned
        )
    payload = json.loads(text)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{source} must contain a JSON object")
    data = dict(payload)
    if baseline_model:
        data["baseline_model"] = baseline_model
    if allow_unpinned:
        data["allow_unpinned"] = True
    return Contract.model_validate(data)


def load_replay(path: str | Path) -> dict[str, JevResponse]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("replay file must be a JSON object keyed by case id")
    return {str(case_id): adapt_response(raw) for case_id, raw in payload.items()}


def dump_replay(responses: Mapping[str, JevResponse]) -> dict[str, Any]:
    return {
        case_id: {
            "model": response.model,
            "usage": response.usage.model_dump(),
            "answers": {
                name: answer.model_dump() for name, answer in response.answers.items()
            },
        }
        for case_id, response in responses.items()
    }


def resolve_expect(expect: FieldExpect, defaults: ContractDefaults) -> FieldExpect:
    return expect.model_copy(
        update={
            "min_confidence": (
                expect.min_confidence
                if expect.min_confidence is not None
                else defaults.min_confidence
            ),
            "confidence_tolerance": (
                expect.confidence_tolerance
                if expect.confidence_tolerance is not None
                else defaults.confidence_tolerance
            ),
            "noul_tolerance": (
                expect.noul_tolerance
                if expect.noul_tolerance is not None
                else defaults.noul_tolerance
            ),
            "score_tolerance": (
                expect.score_tolerance
                if expect.score_tolerance is not None
                else defaults.score_tolerance
            ),
        }
    )


def _require_applicable_expect(
    case_id: str, field: str, question: Question, expect: FieldExpect
) -> None:
    """Reject empty and wrong-kind expects without changing the fixture schema."""
    present = expect.model_dump(exclude_none=True)
    if not present:
        raise ValueError(
            f"case {case_id!r} field {field!r}: expect must state at least one constraint"
        )
    if isinstance(question, ChoiceQuestion):
        kind = "choice"
        foreign = _NOUL_ONLY | _SCORE_ONLY
        effective = expect.choice is not None
    elif isinstance(question, NoulQuestion):
        kind = "noul"
        foreign = _CHOICE_ONLY | _SCORE_ONLY
        effective = (
            expect.noul is not None
            or expect.noul_true is not None
            or expect.min_noul is not None
        )
    elif isinstance(question, ScoreQuestion):
        kind = "score"
        foreign = _CHOICE_ONLY | _NOUL_ONLY
        effective = expect.score is not None
    else:
        raise ValueError(f"case {case_id!r} field {field!r}: unsupported question type")

    wrong = sorted(set(present) & foreign)
    if wrong:
        raise ValueError(
            f"case {case_id!r} field {field!r}: {wrong} do not apply to a {kind} question"
        )
    if (
        not effective
        and expect.min_confidence is None
        and expect.baseline_confidence is None
    ):
        raise ValueError(
            f"case {case_id!r} field {field!r}: expect has no effective {kind} constraint"
        )


def _load_jsonl(
    text: str,
    source: Path,
    *,
    baseline_model: str | None,
    allow_unpinned: bool | None = None,
) -> Contract:
    meta: dict[str, Any] = {}
    cases: list[Any] = []
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{source}:{lineno}: invalid JSON") from exc
        if not isinstance(item, Mapping):
            raise ValueError(f"{source}:{lineno}: each line must be a JSON object")
        if item.get("_meta") is True:
            if cases:
                raise ValueError(f"{source}:{lineno}: _meta line must come before cases")
            meta = {k: v for k, v in item.items() if k != "_meta"}
            continue
        cases.append(item)
    if baseline_model:
        meta["baseline_model"] = baseline_model
    if allow_unpinned:
        meta["allow_unpinned"] = True
    if "baseline_model" not in meta:
        raise ValueError(
            f"{source}: JSONL contract needs a _meta.baseline_model or --baseline-model"
        )
    meta.setdefault("version", "0.1")
    meta["cases"] = cases
    return Contract.model_validate(meta)
