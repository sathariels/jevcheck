# jevcheck

**pytest for Jev.** Pin what production is allowed to do, eval a candidate model, and fail the upgrade when answers flip or confidence drops.

Probabilities and model versions move. A raw `0.94` is not a release decision. jevcheck records a **production contract** (baseline model + fixtures + expected answers) and proves a candidate still satisfies it before you switch `jev-1.13` → `jev-1.14`.

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
2. Call Jev with that **explicit** model. `jev-latest` is rejected unless you opt in.
3. Before upgrading, eval the candidate:

```bash
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
client = JevClient(model="jev-1.14")  # candidate; pin a real version

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

MIT.
