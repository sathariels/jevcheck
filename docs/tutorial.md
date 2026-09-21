# First-run tutorial

About 10 minutes. Sections 3, 4, and 6 run on replay files only. A TypeSafe API key is optional; the short live section at the end is the only place that needs one.

Model strings `jev-1.13` and `jev-1.14` in this tutorial are **unverified example pin labels** used by the fixtures. jevcheck does not rewrite them: `jev-1.13` is not `jev-1.13.0`. A documented TypeSafe version pin (2026-09-19 model list) is `jev-1.13.0`.

## 1. Install

From a checkout of this repo:

```bash
git clone https://github.com/sathariels/jevcheck.git
cd jevcheck
pip install -e ".[dev]"
```

Or install the published package and copy the [examples pack](../examples/README.md) into your own repo:

```bash
pip install "jevcheck==0.2.0"
```

`jevcheck` and `python -m jevcheck` run the same CLI. Use the module form when the `jevcheck` script is not on your `PATH`.

## 2. What a contract is

A **contract** is the production baseline: pinned model, fixture cases, and the answers those cases must keep. `jevcheck eval` compares a candidate against that contract. Full schema: [contract.md](contract.md).

This tutorial uses [`examples/support.json`](../examples/support.json), a slimmed copy of [`fixtures/support-triage.json`](../fixtures/support-triage.json) with two `choice` cases:

| Case | Expected choice | Floor |
| --- | --- | --- |
| `billing-charge` | `billing` | `min_confidence` 0.85, `baseline_confidence` 0.94 |
| `email-settings` | `general` | `min_confidence` 0.8, `baseline_confidence` 0.9 |

`baseline_model` is the example label `jev-1.13`. The full fixture in `fixtures/` also has `noul` and `score` questions; the example pack stays on `choice` so the first run is short. Question kinds and replay shape are in [contract.md](contract.md).

## 3. Offline eval (CI path)

Pass `--answers` with a replay JSON keyed by case id. Each response `model` must equal `--candidate-model` exactly.

Compatible candidate (`examples/replay-unchanged.json`). Exit **0**:

```bash
jevcheck eval examples/support.json \
  --candidate-model jev-1.14 \
  --answers examples/replay-unchanged.json
```

```text
jevcheck eval: support-example
baseline: jev-1.13
candidate: jev-1.14
cases: 2

unchanged: 2
confidence regressions: 0
behavioral flips: 0

compatible
```

Breaking candidate (`examples/replay-breaking.json`). Exit **1**:

```bash
jevcheck eval examples/support.json \
  --candidate-model jev-1.14 \
  --answers examples/replay-breaking.json
```

```text
jevcheck eval: support-example
baseline: jev-1.13
candidate: jev-1.14
cases: 2

unchanged: 0
confidence regressions: 1
behavioral flips: 1

billing-charge intent: 0.94→0.71  [regression]
email-settings intent: general→billing  [flip]

breaking
```

`email-settings` flipped `general` to `billing`. `billing-charge` kept the label and dropped confidence from `0.94` to `0.71` (below the 0.85 floor and the 0.1 tolerance). Exit 1 means do not upgrade. Exit 0 means the candidate matched this contract.

Exit codes: **0** compatible, **1** breaking, **2** usage or identity, **3** operational (live HTTP / invalid API body).

## 4. Record, then compare (v0.2)

`eval` checks the authored `expect` block. `record` and `compare` check a candidate against a baseline model's answers. Lock: [adr-009-two-model-compare.md](adr-009-two-model-compare.md).

Record the baseline snapshot. With `--answers`, this copies a replay through the same writer CI can use. The baseline replay's `model` must be the contract pin (`jev-1.13`). Exit **0**:

```bash
jevcheck record examples/support.json \
  --answers examples/replay-baseline.json \
  --out /tmp/baseline-answers.json
```

```text
jevcheck record: support-example
baseline: jev-1.13
cases: 2
wrote: /tmp/baseline-answers.json
```

Compare the unchanged candidate to that snapshot (or to `examples/replay-baseline.json` directly). Exit **0**:

```bash
jevcheck compare examples/support.json \
  --from /tmp/baseline-answers.json \
  --to jev-1.14 \
  --answers examples/replay-unchanged.json
```

The same compare against the breaking replay exits **1**, with the same flip and regression lines as eval:

```bash
jevcheck compare examples/support.json \
  --from examples/replay-baseline.json \
  --to jev-1.14 \
  --answers examples/replay-breaking.json
```

`--from` is a recorded replay. `--from-model` would fetch the baseline live. They are mutually exclusive. On `compare`, `--answers` is the **candidate** replay.

## 5. Optional live calls

Skip this section unless `TYPESAFE_API_KEY` is already set. The tutorial is complete without it. Never commit the key. See [`.env.example`](../.env.example).

```bash
export TYPESAFE_API_KEY=...
```

Omit `--answers` to call System One. Pin a catalog version you have verified, such as `jev-1.13.0`. Do not send the fixture labels `jev-1.13` or `jev-1.14` as live model ids.

```bash
jevcheck record path/to/your-contract.json --out baseline-answers.json
jevcheck eval path/to/your-contract.json --candidate-model jev-1.13.0
jevcheck compare path/to/your-contract.json --from-model jev-1.13.0 --to jev-1.13.0
```

Live answers depend on the model, so those commands sit outside the green path of this tutorial. Verified request fields: [jev-api.md](jev-api.md).

## 6. GitHub Action

Other repos can call the [composite action](../.github/actions/jevcheck/action.yml). It installs `jevcheck` from PyPI and runs `eval`, `compare`, or `record`. A nonzero CLI exit fails the job.

Copy [`examples/jevcheck.yml`](../examples/jevcheck.yml) to `.github/workflows/jevcheck.yml`. It runs fixture-only `eval` and `compare` and does not set `TYPESAFE_API_KEY`. The breaking replay stays local so the workflow can remain a green check.

```yaml
- uses: sathariels/jevcheck/.github/actions/jevcheck@main
  with:
    contract: examples/support.json
    command: compare
    from: examples/replay-baseline.json
    to: jev-1.14
    answers: examples/replay-unchanged.json
```

Use `@main` until a tag that contains `.github/actions/jevcheck` exists. The PyPI tag `v0.2.0` does not include the action. This repo's in-tree proof is [`.github/workflows/jevcheck-example.yml`](../.github/workflows/jevcheck-example.yml), which points `uses:` at `./.github/actions/jevcheck` and the fuller `fixtures/` set.

## 7. Optional PR gate (jevtriage)

[jevtriage](https://github.com/sathariels/jevtriage) is a separate PR triage gate (`ready` / `needs_review` / `risky`). This repo's [pr-triage workflow](../.github/workflows/pr-triage.yml) runs it only when the `TYPESAFE_API_KEY` repository secret is set, so default CI stays green on replay alone. The tutorial succeeds without that workflow.
