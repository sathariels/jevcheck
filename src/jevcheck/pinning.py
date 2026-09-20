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
- Concrete pins: response identity is exact string equality with the
  requested candidate. A missing or null response model is a failure,
  never the string ``"None"``.
- Opted-in floating aliases (``jev-latest``, ``jev-preview``, or names
  containing those tokens) under ``allow_unpinned=True`` / ``--allow-unpinned``:
  accept a nonempty concrete response ``model`` that is **not** itself a
  floating alias (the official API returns the resolved versioned ID).
  The eval report / CLI summary report that resolved response model.
  Without the opt-in, floating aliases stay rejected.

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


def require_response_identity(
    response_model: Any, requested: str, *, allow_unpinned: bool = False
) -> str:
    """Fail closed when the response did not come from *requested*.

    Concrete pins stay exact identity. An opted-in floating alias may
    resolve to a nonempty concrete (non-alias) response model.
    """
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
    if allow_unpinned and is_unpinned(requested):
        if not is_unpinned(actual):
            return actual
        raise ModelIdentityError(
            f"response model {actual!r} is a floating alias; expected a concrete "
            f"resolved model for requested candidate {requested!r}"
        )
    if actual != requested:
        raise ModelIdentityError(
            f"response model {actual!r} does not match requested candidate {requested!r}"
        )
    return actual


def format_resolved_model(requested: str, resolved: str) -> str:
    """Console label: show ``alias → concrete`` when they differ."""
    if resolved != requested:
        return f"{requested} → {resolved}"
    return resolved
