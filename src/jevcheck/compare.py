"""Record baseline answers and compare a candidate against them (v0.2)."""

from __future__ import annotations

from collections.abc import Mapping

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
    resolve_expect,
)
from jevcheck.eval import EvalReport, Fetch, evaluate
from jevcheck.pinning import require_pinned, require_response_identity
from jevcheck.questions import ChoiceQuestion, NoulQuestion, ScoreQuestion


def require_answer_kind(
    *,
    case_id: str,
    field: str,
    question: object,
    actual: ChoiceAnswer | NoulAnswer | ScoreAnswer,
) -> None:
    """Fail closed when a recorded answer type does not match the question kind."""
    if isinstance(question, ChoiceQuestion):
        expected_type, expected_kind = ChoiceAnswer, "choice"
    elif isinstance(question, NoulQuestion):
        expected_type, expected_kind = NoulAnswer, "noul"
    elif isinstance(question, ScoreQuestion):
        expected_type, expected_kind = ScoreAnswer, "score"
    else:
        raise TypeError(
            f"baseline {case_id}.{field}: unsupported question type {type(question).__name__}"
        )
    if not isinstance(actual, expected_type):
        raise TypeError(
            f"baseline {case_id}.{field} is {actual.type}, expected {expected_kind}"
        )


def require_response_answer_kinds(case: Case, response: JevResponse) -> None:
    """Validate every expected field exists and matches the contract question kind."""
    missing = [name for name in case.expect if name not in response.answers]
    if missing:
        raise KeyError(f"baseline answers missing {case.id} fields: {missing}")
    for name, question in case.questions.items():
        actual = response.answers.get(name)
        if actual is None:
            continue
        require_answer_kind(
            case_id=case.id,
            field=name,
            question=question,
            actual=actual,
        )


def record_answers(
    contract: Contract,
    fetch: Fetch,
    *,
    baseline_model: str | None = None,
    allow_unpinned: bool | None = None,
) -> dict[str, JevResponse]:
    """Fetch one System One response per case and identity-check the baseline."""
    opt_in = contract.allow_unpinned if allow_unpinned is None else allow_unpinned
    requested = require_pinned(
        baseline_model or contract.baseline_model, allow_unpinned=opt_in
    )
    recorded: dict[str, JevResponse] = {}
    for case in contract.cases:
        response = fetch(case)
        require_response_identity(response.model, requested, allow_unpinned=opt_in)
        require_response_answer_kinds(case, response)
        recorded[case.id] = response
    return recorded


def contract_from_baseline(
    contract: Contract,
    baseline: Mapping[str, JevResponse],
) -> Contract:
    """Derive expect values from recorded baseline answers; keep floors/tolerances."""
    cases: list[Case] = []
    for case in contract.cases:
        if case.id not in baseline:
            raise KeyError(f"baseline answers missing cases: {[case.id]}")
        response = baseline[case.id]
        new_expect = {
            name: expect_from_baseline_answer(
                case_id=case.id,
                field=name,
                question=case.questions[name],
                original=expect,
                actual=response.answers.get(name),
                defaults=contract.defaults,
            )
            for name, expect in case.expect.items()
        }
        cases.append(case.model_copy(update={"expect": new_expect}))
    return contract.model_copy(update={"cases": cases})


def expect_from_baseline_answer(
    *,
    case_id: str,
    field: str,
    question: object,
    original: FieldExpect,
    actual: ChoiceAnswer | NoulAnswer | ScoreAnswer | None,
    defaults: ContractDefaults,
) -> FieldExpect:
    if actual is None:
        raise KeyError(f"baseline answers missing {case_id}.{field}")
    require_answer_kind(
        case_id=case_id,
        field=field,
        question=question,
        actual=actual,
    )
    resolved = resolve_expect(original, defaults)
    if isinstance(question, ChoiceQuestion) and isinstance(actual, ChoiceAnswer):
        return resolved.model_copy(
            update={
                "choice": actual.choice,
                "baseline_confidence": mapped_confidence(actual),
            }
        )
    if isinstance(question, NoulQuestion) and isinstance(actual, NoulAnswer):
        return resolved.model_copy(
            update={
                "noul": actual.noul,
                "noul_true": actual.noul >= defaults.noul_true_threshold,
                "baseline_confidence": mapped_confidence(actual),
            }
        )
    if isinstance(question, ScoreQuestion) and isinstance(actual, ScoreAnswer):
        return resolved.model_copy(
            update={
                "score": actual.score,
                "baseline_confidence": mapped_confidence(actual),
            }
        )
    raise TypeError(
        f"baseline {case_id}.{field}: unsupported question type {type(question).__name__}"
    )


def compare(
    contract: Contract,
    baseline: Mapping[str, JevResponse],
    fetch: Fetch,
    *,
    candidate_model: str,
    allow_unpinned: bool | None = None,
) -> EvalReport:
    """Evaluate a candidate against recorded baseline answers using v0.1 evaluate()."""
    opt_in = contract.allow_unpinned if allow_unpinned is None else allow_unpinned
    requested_baseline = require_pinned(contract.baseline_model, allow_unpinned=opt_in)
    missing = [case.id for case in contract.cases if case.id not in baseline]
    if missing:
        raise KeyError(f"baseline answers missing cases: {missing}")

    resolved_baselines: list[str] = []
    for case in contract.cases:
        response = baseline[case.id]
        resolved_baselines.append(
            require_response_identity(
                response.model, requested_baseline, allow_unpinned=opt_in
            )
        )
        require_response_answer_kinds(case, response)

    derived = contract_from_baseline(contract, baseline)
    report = evaluate(
        derived,
        fetch,
        candidate_model=candidate_model,
        allow_unpinned=opt_in,
    )
    unique = list(dict.fromkeys(resolved_baselines))
    reported_baseline = unique[0] if len(unique) == 1 else requested_baseline
    return report.model_copy(
        update={
            "mode": "compare",
            "baseline_model": reported_baseline,
            "requested_baseline_model": requested_baseline,
            "requested_candidate_model": candidate_model,
        }
    )
