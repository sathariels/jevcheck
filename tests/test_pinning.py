from __future__ import annotations

import pytest

from jevcheck.contract import Contract
from jevcheck.eval import evaluate
from jevcheck.pinning import UnpinnedModelError, is_unpinned, require_pinned
from tests.helpers import choice, response


@pytest.mark.parametrize(
    "name,floating",
    [
        ("jev-1.13", False),
        ("jev-1.14", False),
        ("jev-latest", True),
        ("JEV-LATEST", True),
        ("jev-1.14-latest-preview", True),
    ],
)
def test_is_unpinned(name: str, floating: bool) -> None:
    assert is_unpinned(name) is floating


def test_require_pinned_fail_closed() -> None:
    with pytest.raises(UnpinnedModelError, match="unpinned"):
        require_pinned("jev-latest")
    assert require_pinned("jev-latest", allow_unpinned=True) == "jev-latest"
    assert require_pinned("jev-1.13") == "jev-1.13"


def test_evaluate_rejects_unpinned_candidate(contract: Contract) -> None:
    replay = {
        "ticket-001": response(
            "jev-latest",
            intent=choice("billing", 0.93),
            billing=choice("billing", 0.9),
        )
    }
    with pytest.raises(UnpinnedModelError):
        evaluate(contract, lambda case: replay[case.id], candidate_model="jev-latest")
