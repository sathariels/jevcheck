"""jevcheck — pytest for Jev behavior."""

from jevcheck.answers import (
    ChoiceAnswer,
    JevResponse,
    NoulAnswer,
    ScoreAnswer,
    Usage,
    mapped_confidence,
)
from jevcheck.client import AUTH_ENV, JevClient
from jevcheck.compare import compare, record_answers
from jevcheck.contract import Case, Contract, FieldExpect, load_contract, load_replay, write_replay
from jevcheck.eval import CaseResult, EvalReport, Outcome, evaluate, evaluate_case
from jevcheck.gate import Action, Decision, Gate
from jevcheck.pinning import (
    ModelIdentityError,
    UnpinnedModelError,
    is_unpinned,
    require_pinned,
    require_response_identity,
)

__version__ = "0.1.0"

__all__ = [
    "AUTH_ENV",
    "Action",
    "Case",
    "CaseResult",
    "ChoiceAnswer",
    "Contract",
    "Decision",
    "EvalReport",
    "compare",
    "FieldExpect",
    "Gate",
    "JevClient",
    "JevResponse",
    "ModelIdentityError",
    "NoulAnswer",
    "Outcome",
    "ScoreAnswer",
    "UnpinnedModelError",
    "Usage",
    "evaluate",
    "evaluate_case",
    "is_unpinned",
    "load_contract",
    "load_replay",
    "record_answers",
    "write_replay",
    "mapped_confidence",
    "require_pinned",
    "require_response_identity",
    "__version__",
]
