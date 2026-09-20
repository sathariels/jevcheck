# jevcheck

**pytest for Jev.** Pin what production is allowed to do, eval a candidate model, and fail the upgrade when answers flip or confidence drops.

Probabilities and model versions move. A raw `0.94` is not a release decision. jevcheck records a **production contract** (baseline model + fixtures + expected answers) and evals a candidate against that fixture.

**v0.1** `eval` is fixture-versus-candidate. **v0.2** adds two-model execution: `record` a baseline model's answers, then `compare` a candidate against that snapshot (or fetch both models live). See [`docs/adr-009-two-model-compare.md`](docs/adr-009-two-model-compare.md).

The repo’s `jev-1.13` / `jev-1.14` strings are **unverified example pin labels** used by fixtures. A documented TypeSafe version pin (2026-09-19 model list) is `jev-1.13.0`. Floating aliases `jev-latest` and `jev-preview` are rejected unless you pass `--allow-unpinned`. With that opt-in, a response whose `model` is the concrete resolved ID (for example `jev-1.13.0`) is accepted; the eval report prints that resolved model. Concrete pins still require exact identity.

```
pin contract  →  ship on the pinned model  →  jevcheck eval     →  compatible or breaking
                                          →  record → compare  →  compatible or breaking   (v0.2)
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
2. Call Jev with that **explicit** model. `jev-latest` and `jev-preview` are rejected unless you opt in. Concrete pins require `response.model` to match exactly. An opted-in alias may resolve to a nonempty concrete (non-alias) response model, which is reported.
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

## Upgrade flow (v0.2): record baseline → compare candidate

Two-model execution is a **v0.2** capability. `eval` above stays the v0.1 fixture path and is unchanged.

1. Record answers from the model you ship. The file is the same replay JSON `eval --answers` already accepts:

```bash
# Live (needs TYPESAFE_API_KEY). Pin a catalog version such as jev-1.13.0 in production.
jevcheck record fixtures/support-triage.json --out baseline-answers.json

# CI / no key: copy a previously recorded snapshot through the same command.
jevcheck record fixtures/support-triage.json \
  --answers fixtures/replay-baseline.json \
  --out baseline-answers.json
```

`record` writes only after every answer kind matches the contract question (choice / noul / score). A mismatch is exit 2. Opted-in aliases print the resolved response model in the summary (`jev-preview → jev-1.13.0`).

2. Compare the candidate against that snapshot:

```bash
# Live candidate against recorded baseline
jevcheck compare fixtures/support-triage.json \
  --from baseline-answers.json \
  --to jev-1.14

# CI / no key: recorded baseline + candidate replay
jevcheck compare fixtures/support-triage.json \
  --from fixtures/replay-baseline.json \
  --to jev-1.14 \
  --answers fixtures/replay-breaking.json
```

3. Or fetch both models in one step (live; needs a key):

```bash
jevcheck compare fixtures/support-triage.json \
  --from-model jev-1.13 \
  --to jev-1.14
```

`--from` and `--from-model` are mutually exclusive. Identity rules are the v0.1 pins: concrete names must match `response.model` exactly; `jev-latest` / `jev-preview` still need `--allow-unpinned`. Exit codes stay 0 compatible / 1 breaking / 2 usage-or-identity / 3 ops.

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
python -m jevcheck compare fixtures/support-triage.json \
  --from fixtures/replay-baseline.json \
  --to jev-1.14 \
  --answers fixtures/replay-unchanged.json
```

## For agents / audits

v0.2 two-model lock: [`docs/adr-009-two-model-compare.md`](docs/adr-009-two-model-compare.md).

See [`docs/release-readiness-audit-v0.1.md`](docs/release-readiness-audit-v0.1.md). Recheck: [`docs/release-readiness-audit-v0.1-recheck.md`](docs/release-readiness-audit-v0.1-recheck.md).

MIT.
