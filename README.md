# jevcheck

**pytest for Jev.** Pin what production is allowed to do, eval a candidate model, and fail the upgrade when answers flip or confidence drops.

Probabilities and model versions move. A raw `0.94` is not a release decision. jevcheck records a **production contract** (baseline model + fixtures + expected answers) and evals a candidate against that fixture. This is fixture-versus-model evaluation, not two-model execution.

The repo’s `jev-1.13` / `jev-1.14` strings are **unverified example pin labels** used by fixtures. A documented TypeSafe version pin (2026-09-19 model list) is `jev-1.13.0`. Floating aliases `jev-latest` and `jev-preview` are rejected unless you pass `--allow-unpinned`.

```
pin contract  →  ship on the pinned model  →  jevcheck eval  →  compatible or breaking
```

Reports: **unchanged** / **confidence regressions** / **answer flips**, with exact diffs (`billing→general`, `0.94→0.71`) and a nonzero exit on failure.

## Install

```bash
pip install -e ".[dev]"
export TYPESAFE_API_KEY=...   # live Jev only; never commit this
```

Auth is `TYPESAFE_API_KEY` only. Unit tests mock the network.

## Pin → eval → upgrade

1. Write a contract (see [`docs/contract.md`](docs/contract.md)) against the model you ship.
2. Call Jev with that **explicit** model. `jev-latest` and `jev-preview` are rejected unless you opt in. The response `model` must match the requested candidate.
3. Before upgrading, eval the candidate (example fixture label — not a verified live ID):

```bash
# Live call. Pin a catalog version such as jev-1.13.0 in production.
# The example below matches this repo's replay fixtures only.
jevcheck eval fixtures/support-triage.json --candidate-model jev-1.14
```

Replay recorded answers (CI / no key):

```bash
jevcheck eval fixtures/support-triage.json \
  --candidate-model jev-1.14 \
  --answers fixtures/replay-breaking.json
```

4. Compatible (exit 0) → change the pin. Breaking (exit 1) → read the diffs; do not upgrade.

Verified System One fields: [`docs/jev-api.md`](docs/jev-api.md).

## Example

```python
from jevcheck import JevClient, evaluate, load_contract

contract = load_contract("fixtures/support-triage.json")
client = JevClient(model="jev-1.14")  # example fixture label; pin a catalog version in production

report = evaluate(
    contract,
    lambda case: client.system_one(
        state=case.state,
        questions=case.questions,
        model="jev-1.14",
    ),
    candidate_model="jev-1.14",
)
print(report.summary())
if report.breaking:
    raise SystemExit(1)
```

A `Gate` helper exists for auto / ask-human / reject thresholds. It is optional and is not the product.

## Develop

```bash
pip install -e ".[dev]"
pytest
python -m jevcheck eval fixtures/support-triage.json \
  --candidate-model jev-1.14 \
  --answers fixtures/replay-unchanged.json
```

## For agents / audits

See [`docs/release-readiness-audit-v0.1.md`](docs/release-readiness-audit-v0.1.md). Recheck: [`docs/release-readiness-audit-v0.1-recheck.md`](docs/release-readiness-audit-v0.1-recheck.md).

MIT.
