"""Fail-closed model pinning and response identity.

Alias resolution (explicit; jevcheck never rewrites a name):

- Empty / whitespace-only names are invalid. They are not pins.
- Floating aliases, rejected unless ``allow_unpinned=True`` / ``--allow-unpinned``:
  ``jev-latest`` and ``jev-preview`` (case-insensitive), plus any name that
  contains ``latest`` or ``preview``. Official TypeSafe docs treat both as
  moving aliases; the response ``model`` field names the resolved version.
- Version-shaped names (for example ``jev-1.13.0``) are accepted as pins.
  jevcheck does **not** equate a shorthand with a dotted version:
  ``jev-1.13`` is not ``jev-1.13.0``.
- Response identity is exact string equality with the requested candidate.
  A missing or null response model is a failure, never the string ``"None"``.

Repo fixtures use example labels such as ``jev-1.13`` / ``jev-1.14``. Those
are unverified against the live catalog. A documented TypeSafe version pin
as of the 2026-09-19 model list is ``jev-1.13.0``.
"""

from __future__ import annotations

from typing import Any

FLOATING_ALIASES = frozenset({"jev-latest", "jev-preview"})


class UnpinnedModelError(ValueError):
    """Raised when a floating model name is used without an explicit opt-in."""


class ModelIdentityError(ValueError):
    """Raised when a response model does not match the requested candidate."""


def is_unpinned(model: str) -> bool:
    """Return True when *model* is a moving alias rather than a pin."""
    name = model.strip().lower()
    if not name:
        raise ValueError("model name must be a nonempty string")
    if name in FLOATING_ALIASES:
        return True
    return "latest" in name or "preview" in name


def require_pinned(model: str, *, allow_unpinned: bool = False) -> str:
    pinned = model.strip()
    if not pinned:
        raise ValueError("model name must be a nonempty string")
    if is_unpinned(pinned) and not allow_unpinned:
        raise UnpinnedModelError(
            f"{pinned!r} is an unpinned floating model; pass an explicit "
            "version (for example jev-1.13.0) or set allow_unpinned=True"
        )
    return pinned


def require_response_identity(response_model: Any, requested: str) -> str:
    """Fail closed when the response did not come from *requested*."""
    if response_model is None:
        raise ModelIdentityError(
            f"response model is null; expected requested candidate {requested!r}"
        )
    if not isinstance(response_model, str) or not response_model.strip():
        raise ModelIdentityError(
            f"response model {response_model!r} is not a nonempty string; "
            f"expected requested candidate {requested!r}"
        )
    actual = response_model.strip()
    if actual != requested:
        raise ModelIdentityError(
            f"response model {actual!r} does not match requested candidate {requested!r}"
        )
    return actual
