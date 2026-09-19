"""jevcheck CLI — eval a candidate model against a pinned contract."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path

from typesafe_sdk import (
    TypeSafeAPIError,
    TypeSafeAPIResponseValidationError,
    TypeSafeAuthenticationError,
    TypeSafeError,
    TypeSafeInternalServerError,
    TypeSafeRateLimitError,
)

from jevcheck.answers import JevResponse
from jevcheck.client import AUTH_ENV, JevClient
from jevcheck.contract import Case, Contract, load_contract, load_replay
from jevcheck.eval import evaluate
from jevcheck.pinning import ModelIdentityError, UnpinnedModelError, require_pinned

# Exit 0: compatible. Exit 1: behavioral contract failure.
# Exit 2: usage / input / identity. Exit 3: operational (HTTP / invalid API body).
EXIT_OK = 0
EXIT_BREAKING = 1
EXIT_USAGE = 2
EXIT_OPS = 3


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="jevcheck",
        description="Pin Jev production contracts and eval candidate model upgrades.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    eval_cmd = sub.add_parser("eval", help="compare a candidate model to a contract")
    eval_cmd.add_argument("contract", type=Path, help="JSON contract or JSONL fixtures")
    eval_cmd.add_argument(
        "--candidate-model",
        required=True,
        help="explicit candidate model (upgrades must be intentional)",
    )
    eval_cmd.add_argument(
        "--baseline-model",
        default=None,
        help="override contract baseline_model (required for JSONL without _meta)",
    )
    eval_cmd.add_argument(
        "--answers",
        type=Path,
        default=None,
        help="replay file of mocked System One responses keyed by case id",
    )
    eval_cmd.add_argument(
        "--allow-unpinned",
        action="store_true",
        help="opt in to floating names such as jev-latest and jev-preview",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command != "eval":
        parser.error("unknown command")

    try:
        return _run_eval(args)
    except UnpinnedModelError as exc:
        _print_error(exc)
        return EXIT_USAGE
    except ModelIdentityError as exc:
        _print_error(exc)
        return EXIT_USAGE
    except TypeSafeAuthenticationError as exc:
        _print_error(f"authentication failed ({exc.status}): {exc}")
        return EXIT_OPS
    except TypeSafeRateLimitError as exc:
        _print_error(f"rate limited ({exc.status}): {exc}")
        return EXIT_OPS
    except TypeSafeInternalServerError as exc:
        _print_error(f"server error ({exc.status}): {exc}")
        return EXIT_OPS
    except TypeSafeAPIResponseValidationError as exc:
        _print_error(f"invalid API response: {exc}")
        return EXIT_OPS
    except TypeSafeAPIError as exc:
        _print_error(f"API error ({exc.status}): {exc}")
        return EXIT_OPS
    except TypeSafeError as exc:
        _print_error(exc)
        return EXIT_USAGE
    except (OSError, TypeError, ValueError, KeyError, RuntimeError) as exc:
        _print_error(exc)
        return EXIT_USAGE


def _run_eval(args: argparse.Namespace) -> int:
    allow = bool(args.allow_unpinned)
    candidate = require_pinned(args.candidate_model, allow_unpinned=allow)
    contract: Contract = load_contract(
        args.contract,
        baseline_model=args.baseline_model,
        allow_unpinned=allow,
    )
    if args.answers is not None:
        replay = load_replay(args.answers)
        missing = [case.id for case in contract.cases if case.id not in replay]
        if missing:
            raise KeyError(f"replay file missing cases: {missing}")

        def fetch(case: Case) -> JevResponse:
            return replay[case.id]
    else:
        client = JevClient(model=candidate, allow_unpinned=allow)

        def fetch(case: Case) -> JevResponse:
            return client.system_one(state=case.state, questions=case.questions, model=candidate)

        if not client.api_key:
            raise RuntimeError(
                f"live eval needs {AUTH_ENV} or a --answers replay file"
            )

    report = evaluate(
        contract,
        fetch,
        candidate_model=candidate,
        allow_unpinned=allow,
    )
    sys.stdout.write(report.summary())
    return EXIT_BREAKING if report.breaking else EXIT_OK


def redact_secrets(text: str, *secrets: str | None) -> str:
    """Remove known credentials from user-visible error text."""
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "***")
    env_key = os.environ.get(AUTH_ENV)
    if env_key:
        redacted = redacted.replace(env_key, "***")
    redacted = re.sub(r"(?i)(bearer\s+)\S+", r"\1***", redacted)
    redacted = re.sub(
        r"(?i)(authorization\s*[:=]\s*)(\S+)",
        r"\1***",
        redacted,
    )
    return redacted


def _print_error(exc: object) -> None:
    print(f"jevcheck: {redact_secrets(str(exc))}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
