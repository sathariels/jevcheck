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
from jevcheck.compare import compare, record_answers
from jevcheck.contract import Case, Contract, load_contract, load_replay, write_replay
from jevcheck.eval import Fetch, evaluate
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
        help=(
            "opt in to floating names such as jev-latest and jev-preview; "
            "accept a concrete resolved response model (not another alias)"
        ),
    )

    record_cmd = sub.add_parser(
        "record",
        help="fetch baseline answers and write a replay JSON (v0.2)",
    )
    record_cmd.add_argument("contract", type=Path, help="JSON contract or JSONL fixtures")
    record_cmd.add_argument(
        "--out",
        type=Path,
        required=True,
        help="path to write a replay file usable by eval --answers / compare --from",
    )
    record_cmd.add_argument(
        "--baseline-model",
        default=None,
        help="override contract baseline_model (required for JSONL without _meta)",
    )
    record_cmd.add_argument(
        "--answers",
        type=Path,
        default=None,
        help="replay file of mocked baseline responses (CI / tests; no live key)",
    )
    record_cmd.add_argument(
        "--allow-unpinned",
        action="store_true",
        help=(
            "opt in to floating names such as jev-latest and jev-preview; "
            "accept a concrete resolved response model (not another alias)"
        ),
    )

    compare_cmd = sub.add_parser(
        "compare",
        help="evaluate a candidate against recorded or live baseline answers (v0.2)",
    )
    compare_cmd.add_argument("contract", type=Path, help="JSON contract or JSONL fixtures")
    source = compare_cmd.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--from",
        dest="from_replay",
        type=Path,
        default=None,
        help="recorded baseline replay JSON (output of jevcheck record)",
    )
    source.add_argument(
        "--from-model",
        dest="from_model",
        default=None,
        help="live baseline model (fetches both models when --answers is omitted)",
    )
    compare_cmd.add_argument(
        "--to",
        dest="to_model",
        required=True,
        help="explicit candidate model (same pinning rules as eval --candidate-model)",
    )
    compare_cmd.add_argument(
        "--baseline-model",
        default=None,
        help="override contract baseline_model (required for JSONL without _meta)",
    )
    compare_cmd.add_argument(
        "--answers",
        type=Path,
        default=None,
        help="replay file of mocked candidate responses keyed by case id",
    )
    compare_cmd.add_argument(
        "--allow-unpinned",
        action="store_true",
        help=(
            "opt in to floating names such as jev-latest and jev-preview; "
            "accept a concrete resolved response model (not another alias)"
        ),
    )

    args = parser.parse_args(list(argv) if argv is not None else None)
    handlers = {
        "eval": _run_eval,
        "record": _run_record,
        "compare": _run_compare,
    }
    if args.command not in handlers:
        parser.error("unknown command")

    try:
        return handlers[args.command](args)
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
    fetch = _answers_or_live_fetch(
        contract,
        args.answers,
        model=candidate,
        allow=allow,
        live_need="live eval",
    )
    report = evaluate(
        contract,
        fetch,
        candidate_model=candidate,
        allow_unpinned=allow,
    )
    sys.stdout.write(report.summary())
    return EXIT_BREAKING if report.breaking else EXIT_OK


def _run_record(args: argparse.Namespace) -> int:
    allow = bool(args.allow_unpinned)
    contract = load_contract(
        args.contract,
        baseline_model=args.baseline_model,
        allow_unpinned=allow,
    )
    baseline = require_pinned(contract.baseline_model, allow_unpinned=allow)
    fetch = _answers_or_live_fetch(
        contract,
        args.answers,
        model=baseline,
        allow=allow,
        live_need="live record",
    )
    recorded = record_answers(
        contract,
        fetch,
        baseline_model=baseline,
        allow_unpinned=allow,
    )
    write_replay(args.out, recorded)
    title = contract.name or "contract"
    sys.stdout.write(
        f"jevcheck record: {title}\n"
        f"baseline: {baseline}\n"
        f"cases: {len(recorded)}\n"
        f"wrote: {args.out}\n"
    )
    return EXIT_OK


def _run_compare(args: argparse.Namespace) -> int:
    allow = bool(args.allow_unpinned)
    if args.from_model and args.baseline_model:
        from_pin = require_pinned(args.from_model, allow_unpinned=allow)
        base_pin = require_pinned(args.baseline_model, allow_unpinned=allow)
        if from_pin != base_pin:
            raise ValueError("--from-model and --baseline-model disagree")
    baseline_override = args.from_model or args.baseline_model
    contract = load_contract(
        args.contract,
        baseline_model=baseline_override,
        allow_unpinned=allow,
    )
    candidate = require_pinned(args.to_model, allow_unpinned=allow)
    if args.from_replay is not None:
        baseline = load_replay(args.from_replay)
    else:
        live_baseline = require_pinned(contract.baseline_model, allow_unpinned=allow)
        baseline_fetch = _answers_or_live_fetch(
            contract,
            None,
            model=live_baseline,
            allow=allow,
            live_need="live compare",
        )
        baseline = record_answers(
            contract,
            baseline_fetch,
            baseline_model=live_baseline,
            allow_unpinned=allow,
        )
    fetch = _answers_or_live_fetch(
        contract,
        args.answers,
        model=candidate,
        allow=allow,
        live_need="live compare",
    )
    report = compare(
        contract,
        baseline,
        fetch,
        candidate_model=candidate,
        allow_unpinned=allow,
    )
    sys.stdout.write(report.summary())
    return EXIT_BREAKING if report.breaking else EXIT_OK


def _answers_or_live_fetch(
    contract: Contract,
    answers: Path | None,
    *,
    model: str,
    allow: bool,
    live_need: str,
) -> Fetch:
    if answers is not None:
        replay = load_replay(answers)
        missing = [case.id for case in contract.cases if case.id not in replay]
        if missing:
            raise KeyError(f"replay file missing cases: {missing}")

        def fetch(case: Case) -> JevResponse:
            return replay[case.id]

        return fetch

    client = JevClient(model=model, allow_unpinned=allow)

    def fetch(case: Case) -> JevResponse:
        return client.system_one(state=case.state, questions=case.questions, model=model)

    if not client.api_key:
        raise RuntimeError(f"{live_need} needs {AUTH_ENV} or a --answers replay file")
    return fetch


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
