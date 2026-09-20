from __future__ import annotations

import pytest

from jevcheck.contract import Contract
from jevcheck.eval import evaluate
from jevcheck.pinning import (
    ModelIdentityError,
    UnpinnedModelError,
    format_resolved_model,
    is_unpinned,
    require_pinned,
    require_response_identity,
)
from tests.helpers import choice, response


@pytest.mark.parametrize(
    "name,floating",
    [
        ("jev-1.13", False),
        ("jev-1.14", False),
        ("jev-1.13.0", False),
        ("jev-latest", True),
        ("JEV-LATEST", True),
        ("jev-preview", True),
        ("JEV-PREVIEW", True),
        ("jev-1.14-latest-preview", True),
    ],
)
def test_is_unpinned(name: str, floating: bool) -> None:
    assert is_unpinned(name) is floating


def test_require_pinned_fail_closed() -> None:
    with pytest.raises(UnpinnedModelError, match="unpinned"):
        require_pinned("jev-latest")
    with pytest.raises(UnpinnedModelError, match="unpinned"):
        require_pinned("jev-preview")
    with pytest.raises(ValueError, match="nonempty"):
        require_pinned("")
    with pytest.raises(ValueError, match="nonempty"):
        is_unpinned("   ")
    assert require_pinned("jev-latest", allow_unpinned=True) == "jev-latest"
    assert require_pinned("jev-preview", allow_unpinned=True) == "jev-preview"
    assert require_pinned("jev-1.13") == "jev-1.13"
    assert require_pinned("jev-1.13.0") == "jev-1.13.0"


def test_alias_opt_in_accepts_concrete_resolved_response_model() -> None:
    """Recheck P2: --allow-unpinned jev-preview may resolve to jev-1.13.0."""
    tiny = Contract.model_validate(
        {
            "baseline_model": "jev-1.13",
            "allow_unpinned": True,
            "cases": [
                {
                    "id": "c1",
                    "state": "s",
                    "questions": {
                        "q": {"type": "choice", "criteria": {"a": None, "b": None}}
                    },
                    "expect": {"q": {"choice": "b", "min_confidence": 0.0}},
                }
            ],
        }
    )
    report = evaluate(
        tiny,
        lambda case: response(
            "jev-1.13.0",
            q=choice("b", 0.51, other="a"),
        ),
        candidate_model="jev-preview",
        allow_unpinned=True,
    )
    assert report.breaking is False
    assert report.candidate_model == "jev-1.13.0"
    assert report.results[0].candidate_model == "jev-1.13.0"
    assert "jev-1.13.0" in report.summary()


def test_alias_opt_in_rejects_floating_response_model() -> None:
    with pytest.raises(ModelIdentityError, match="floating alias"):
        require_response_identity("jev-latest", "jev-preview", allow_unpinned=True)
    with pytest.raises(ModelIdentityError, match="floating alias"):
        require_response_identity("jev-preview", "jev-preview", allow_unpinned=True)


def test_format_resolved_model_shows_alias_arrow() -> None:
    assert format_resolved_model("jev-preview", "jev-1.13.0") == "jev-preview → jev-1.13.0"
    assert format_resolved_model("jev-1.13", "jev-1.13") == "jev-1.13"


def test_concrete_pin_still_requires_exact_identity() -> None:
    with pytest.raises(ModelIdentityError, match="does not match"):
        require_response_identity("jev-1.13.0", "jev-1.14", allow_unpinned=True)
    assert require_response_identity("jev-1.14", "jev-1.14") == "jev-1.14"


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
    with pytest.raises(UnpinnedModelError):
        evaluate(contract, lambda case: replay[case.id], candidate_model="jev-preview")
