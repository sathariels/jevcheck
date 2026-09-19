"""Fail-closed model pinning. Floating *latest* names are not production models."""

from __future__ import annotations


class UnpinnedModelError(ValueError):
    """Raised when a floating model name is used without an explicit opt-in."""


def is_unpinned(model: str) -> bool:
    name = model.strip().lower()
    if not name:
        raise ValueError("model name must be a nonempty string")
    return name == "jev-latest" or "latest" in name


def require_pinned(model: str, *, allow_unpinned: bool = False) -> str:
    pinned = model.strip()
    if not pinned:
        raise ValueError("model name must be a nonempty string")
    if is_unpinned(pinned) and not allow_unpinned:
        raise UnpinnedModelError(
            f"{pinned!r} is an unpinned floating model; pass an explicit "
            "version (for example jev-1.13) or set allow_unpinned=True"
        )
    return pinned
