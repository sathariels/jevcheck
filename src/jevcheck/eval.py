"""Compare candidate System One answers against a pinned contract."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from jevcheck.answers import (
    ChoiceAnswer,
    JevResponse,
    NoulAnswer,
    ScoreAnswer,
    mapped_confidence,
)
from jevcheck.contract import (
    Case,
    Contract,
    ContractDefaults,
    FieldExpect,
    require_actionable_resolved_expect,
    resolve_expect,
)
from jevcheck.pinning import require_pinned, require_response_identity
from jevcheck.questions import ChoiceQuestion, NoulQuestion, ScoreQuestion


class Outcome(str, Enum):
    UNCHANGED = "unchanged"
    CONFIDENCE_REGRESSION = "confidence_regression"
    ANSWER_FLIP = "answer_flip"

    def worse_than(self, other: Outcome) -> bool:
        rank = {
            Outcome.UNCHANGED: 0,
            Outcome.CONFIDENCE_REGRESSION: 1,
            Outcome.ANSWER_FLIP: 2,
        }
        return rank[self] > rank[other]


class FieldDiff(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    field: str
    outcome: Outcome
    detail: str
    expected: str | None = None
    actual: str | None = None


class CaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    outcome: Outcome
    diffs: list[FieldDiff] = Field(default_factory=list)
    candidate_model: str | None = None


class EvalReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str | None
    baseline_model: str
    candidate_model: str | None
    mode: Literal["eval", "compare"] = "eval"
    cases_checked: int
    unchanged: int
    confidence_regressions: int
    answer_flips: int
    results: list[CaseResult]
    diffs: list[FieldDiff]

    @property
    def breaking(self) -> bool:
        return self.confidence_regressions > 0 or self.answer_flips > 0

    def summary(self) -> str:
        title = self.name or "contract"
        candidate = self.candidate_model or "(replay)"
        lines = [
            f"jevcheck {self.mode}: {title}",
            f"baseline: {self.baseline_model}",
            f"candidate: {candidate}",
            f"cases: {self.cases_checked}",
            "",
            f"unchanged: {self.unchanged}",
            f"confidence regressions: {self.confidence_regressions}",
            f"behavioral flips: {self.answer_flips}",
        ]
        visible = [diff for diff in self.diffs if diff.outcome is not Outcome.UNCHANGED]
        if visible:
            lines.append("")
            for diff in visible:
                lines.append(f"{diff.case_id} {diff.field}: {diff.detail}  [{_label(diff.outcome)}]")
        lines.append("")
        lines.append("breaking" if self.breaking else "compatible")
        return "\n".join(lines) + "\n"


Fetch = Callable[[Case], JevResponse]

# Inclusive float boundaries for confidence drop, noul absolute drift,
# and score-tolerance abs-diff. Decimal tenths are not binary-exact:
# ``0.8 - 0.7`` is ``0.10000000000000009``, and ``1.6 - 1.4`` is
# ``0.20000000000000018``. A delta is out of tolerance only when it
# exceeds ``tolerance`` by more than this epsilon. Score product rule
# (same-rounded-level / level-flip suppression) is unchanged.
FLOAT_TOLERANCE_EPS = 1e-9


def evaluate(
    contract: Contract,
    fetch: Fetch,
    *,
    candidate_model: str | None = None,
    allow_unpinned: bool | None = None,
) -> EvalReport:
    opt_in = contract.allow_unpinned if allow_unpinned is None else allow_unpinned
    require_pinned(contract.baseline_model, allow_unpinned=opt_in)
    if candidate_model is not None:
        require_pinned(candidate_model, allow_unpinned=opt_in)

    results: list[CaseResult] = []
    diffs: list[FieldDiff] = []
    resolved_models: list[str] = []
    for case in contract.cases:
        response = fetch(case)
        if candidate_model is not None:
            resolved_models.append(
                require_response_identity(
                    response.model, candidate_model, allow_unpinned=opt_in
                )
            )
        result = evaluate_case(case, response, defaults=contract.defaults)
        results.append(result)
        diffs.extend(result.diffs)

    counts = {
        Outcome.UNCHANGED: 0,
        Outcome.CONFIDENCE_REGRESSION: 0,
        Outcome.ANSWER_FLIP: 0,
    }
    for result in results:
        counts[result.outcome] += 1

    return EvalReport(
        name=contract.name,
        baseline_model=contract.baseline_model,
        candidate_model=_reported_candidate(candidate_model, resolved_models),
        cases_checked=len(results),
        unchanged=counts[Outcome.UNCHANGED],
        confidence_regressions=counts[Outcome.CONFIDENCE_REGRESSION],
        answer_flips=counts[Outcome.ANSWER_FLIP],
        results=results,
        diffs=diffs,
    )


def evaluate_case(
    case: Case,
    response: JevResponse,
    *,
    defaults: ContractDefaults | None = None,
) -> CaseResult:
    defaults = defaults or ContractDefaults()
    diffs = []
    for name, expect in case.expect.items():
        resolved = resolve_expect(expect, defaults)
        require_actionable_resolved_expect(resolved, case_id=case.id, field=name)
        diffs.append(
            evaluate_field(
                case_id=case.id,
                field=name,
                question=case.questions[name],
                expect=resolved,
                defaults=defaults,
                actual=response.answers.get(name),
            )
        )
    outcome = Outcome.UNCHANGED
    for diff in diffs:
        if diff.outcome.worse_than(outcome):
            outcome = diff.outcome
    return CaseResult(
        case_id=case.id,
        outcome=outcome,
        diffs=diffs,
        candidate_model=response.model,
    )


def evaluate_field(
    *,
    case_id: str,
    field: str,
    question: Any,
    expect: FieldExpect,
    defaults: ContractDefaults,
    actual: ChoiceAnswer | NoulAnswer | ScoreAnswer | None,
) -> FieldDiff:
    if actual is None:
        return FieldDiff(
            case_id=case_id,
            field=field,
            outcome=Outcome.ANSWER_FLIP,
            detail="missing answer",
            expected=_expected_label(question, expect, defaults),
            actual=None,
        )
    if isinstance(question, ChoiceQuestion):
        return _eval_choice(case_id, field, expect, actual)
    if isinstance(question, NoulQuestion):
        return _eval_noul(case_id, field, expect, defaults, actual)
    if isinstance(question, ScoreQuestion):
        return _eval_score(case_id, field, expect, actual)
    return FieldDiff(
        case_id=case_id,
        field=field,
        outcome=Outcome.ANSWER_FLIP,
        detail=f"unsupported question type {type(question).__name__}",
    )


def _eval_choice(
    case_id: str,
    field: str,
    expect: FieldExpect,
    actual: ChoiceAnswer | NoulAnswer | ScoreAnswer,
) -> FieldDiff:
    if not isinstance(actual, ChoiceAnswer):
        return _type_flip(case_id, field, "choice", actual.type)
    if expect.choice is not None and actual.choice != expect.choice:
        return FieldDiff(
            case_id=case_id,
            field=field,
            outcome=Outcome.ANSWER_FLIP,
            detail=f"{expect.choice}→{actual.choice}",
            expected=expect.choice,
            actual=actual.choice,
        )
    return _confidence_diff(case_id, field, expect, mapped_confidence(actual), actual.choice)


def _eval_noul(
    case_id: str,
    field: str,
    expect: FieldExpect,
    defaults: ContractDefaults,
    actual: ChoiceAnswer | NoulAnswer | ScoreAnswer,
) -> FieldDiff:
    if not isinstance(actual, NoulAnswer):
        return _type_flip(case_id, field, "noul", actual.type)

    expected_yes = expect.noul_true
    if expected_yes is None and expect.noul is not None:
        expected_yes = expect.noul >= defaults.noul_true_threshold
    actual_yes = actual.noul >= defaults.noul_true_threshold
    if expected_yes is not None and actual_yes != expected_yes:
        left = "yes" if expected_yes else "no"
        right = "yes" if actual_yes else "no"
        return FieldDiff(
            case_id=case_id,
            field=field,
            outcome=Outcome.ANSWER_FLIP,
            detail=f"{left}→{right} ({_fmt(actual.noul)})",
            expected=left,
            actual=f"{right} {_fmt(actual.noul)}",
        )

    if expect.noul is not None and expect.noul_tolerance is not None:
        delta = abs(actual.noul - expect.noul)
        if exceeds_tolerance(delta, expect.noul_tolerance):
            return FieldDiff(
                case_id=case_id,
                field=field,
                outcome=Outcome.CONFIDENCE_REGRESSION,
                detail=f"{_fmt(expect.noul)}→{_fmt(actual.noul)}",
                expected=_fmt(expect.noul),
                actual=_fmt(actual.noul),
            )

    if expect.min_noul is not None and actual.noul < expect.min_noul:
        return FieldDiff(
            case_id=case_id,
            field=field,
            outcome=Outcome.CONFIDENCE_REGRESSION,
            detail=f"{_fmt(actual.noul)} < min_noul {_fmt(expect.min_noul)}",
            expected=f">={_fmt(expect.min_noul)}",
            actual=_fmt(actual.noul),
        )

    label = "yes" if actual_yes else "no"
    return _confidence_diff(case_id, field, expect, mapped_confidence(actual), f"{label} {_fmt(actual.noul)}")


def _eval_score(
    case_id: str,
    field: str,
    expect: FieldExpect,
    actual: ChoiceAnswer | NoulAnswer | ScoreAnswer,
) -> FieldDiff:
    if not isinstance(actual, ScoreAnswer):
        return _type_flip(case_id, field, "score", actual.type)
    if expect.score is not None:
        # score_tolerance suppresses a *level flip* when the absolute
        # distance is within tolerance. It is not a maximum float
        # distance: expected 1.8 vs actual 2.2 with tolerance 0.1 stays
        # unchanged because both nearest_level() values are 2.
        within = (
            expect.score_tolerance is not None
            and not exceeds_tolerance(
                abs(actual.score - expect.score), expect.score_tolerance
            )
        )
        if not within and nearest_level(actual.score) != nearest_level(expect.score):
            return FieldDiff(
                case_id=case_id,
                field=field,
                outcome=Outcome.ANSWER_FLIP,
                detail=f"{_fmt(expect.score)}→{_fmt(actual.score)}",
                expected=_fmt(expect.score),
                actual=_fmt(actual.score),
            )
    return _confidence_diff(case_id, field, expect, mapped_confidence(actual), _fmt(actual.score))


def _confidence_diff(
    case_id: str,
    field: str,
    expect: FieldExpect,
    actual_scalar: float,
    actual_label: str | None,
) -> FieldDiff:
    below_min = (
        expect.min_confidence is not None and actual_scalar < expect.min_confidence
    )
    dropped = (
        expect.baseline_confidence is not None
        and expect.confidence_tolerance is not None
        and exceeds_tolerance(
            expect.baseline_confidence - actual_scalar, expect.confidence_tolerance
        )
    )
    if below_min or dropped:
        if expect.baseline_confidence is not None:
            detail = f"{_fmt(expect.baseline_confidence)}→{_fmt(actual_scalar)}"
            expected = _fmt(expect.baseline_confidence)
        else:
            detail = f"{_fmt(actual_scalar)} < min {_fmt(expect.min_confidence)}"
            expected = f">={_fmt(expect.min_confidence)}"
        return FieldDiff(
            case_id=case_id,
            field=field,
            outcome=Outcome.CONFIDENCE_REGRESSION,
            detail=detail,
            expected=expected,
            actual=_fmt(actual_scalar),
        )
    return FieldDiff(
        case_id=case_id,
        field=field,
        outcome=Outcome.UNCHANGED,
        detail="unchanged",
        actual=actual_label,
    )


def exceeds_tolerance(delta: float, tolerance: float) -> bool:
    """Return True when *delta* is greater than an inclusive *tolerance*.

    Exact decimal boundaries (for example drop 0.1 against tolerance 0.1)
    pass even when binary subtraction overshoots by a few ULPs.
    """
    return delta > tolerance + FLOAT_TOLERANCE_EPS


def nearest_level(score: float) -> int:
    """Nearest integer score level via Python ``round`` (ties toward even).

    ``round(1.5) == 2`` and ``round(2.5) == 2``. This is IEEE half-to-even,
    not schoolbook half-away-from-zero. Callers that need a different
    tie rule must change this helper; do not assume half-up.
    """
    return int(round(score))


def _type_flip(case_id: str, field: str, expected: str, actual: str) -> FieldDiff:
    return FieldDiff(
        case_id=case_id,
        field=field,
        outcome=Outcome.ANSWER_FLIP,
        detail=f"{expected}→{actual}",
        expected=expected,
        actual=actual,
    )


def _expected_label(question: Any, expect: FieldExpect, defaults: ContractDefaults) -> str | None:
    if expect.choice is not None:
        return expect.choice
    if expect.noul_true is not None:
        return "yes" if expect.noul_true else "no"
    if expect.noul is not None:
        return "yes" if expect.noul >= defaults.noul_true_threshold else "no"
    if expect.score is not None:
        return _fmt(expect.score)
    return None


def _fmt(value: float) -> str:
    return f"{value:.2f}"


def _reported_candidate(requested: str | None, resolved_models: list[str]) -> str | None:
    """Prefer the concrete response model when an opted-in alias resolved."""
    if requested is None:
        return None
    unique = list(dict.fromkeys(resolved_models))
    if not unique:
        return requested
    if unique == [requested]:
        return requested
    if len(unique) == 1:
        return unique[0]
    return ", ".join(unique)


def _label(outcome: Outcome) -> str:
    if outcome is Outcome.ANSWER_FLIP:
        return "flip"
    if outcome is Outcome.CONFIDENCE_REGRESSION:
        return "regression"
    return "unchanged"
