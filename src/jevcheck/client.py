"""Typed System One boundary. Auth is TYPESAFE_API_KEY only."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from jevcheck.answers import JevResponse, adapt_response
from jevcheck.pinning import require_pinned
from jevcheck.questions import parse_question, question_wire

AUTH_ENV = "TYPESAFE_API_KEY"


class JevClient:
    """Production wrapper around `typesafe_sdk.TypeSafeClient`."""

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        allow_unpinned: bool = False,
        base_url: str | None = None,
        sdk_client: Any | None = None,
    ) -> None:
        self.model = require_pinned(model, allow_unpinned=allow_unpinned)
        self.allow_unpinned = allow_unpinned
        self.api_key = api_key if api_key is not None else os.environ.get(AUTH_ENV)
        self.base_url = base_url
        self._sdk_client = sdk_client

    def __enter__(self) -> JevClient:
        return self

    def __exit__(self, *exc: object) -> None:
        close = getattr(self._sdk_client, "close", None)
        if callable(close):
            close()

    def system_one(
        self,
        state: Any,
        questions: Mapping[str, Any],
        *,
        model: str | None = None,
    ) -> JevResponse:
        pinned = require_pinned(model or self.model, allow_unpinned=self.allow_unpinned)
        wire = {name: question_wire(parse_question(question)) for name, question in questions.items()}
        sdk = self._sdk_client if self._sdk_client is not None else self._open_sdk(pinned)
        owns = self._sdk_client is None
        try:
            raw = sdk.system_one(state=state, questions=wire, model=pinned)
            return adapt_response(raw)
        finally:
            if owns and hasattr(sdk, "close"):
                sdk.close()

    def _open_sdk(self, model: str) -> Any:
        if not self.api_key:
            raise RuntimeError(
                f"{AUTH_ENV} is not set and no api_key= was passed to JevClient"
            )
        from typesafe_sdk import TypeSafeClient

        kwargs: dict[str, Any] = {"api_key": self.api_key, "model": model}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return TypeSafeClient(**kwargs)
