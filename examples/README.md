# Examples pack

Copy this directory into a repo that should gate a Jev upgrade with replay fixtures. The commands below are offline replays.

Walkthrough: [docs/tutorial.md](../docs/tutorial.md). Contract schema: [docs/contract.md](../docs/contract.md).

`jev-1.13` and `jev-1.14` are **unverified example pin labels**. A documented catalog pin is `jev-1.13.0`. The label in `--candidate-model` / `--to` must match each candidate replay's `model`. The contract `baseline_model` must match `replay-baseline.json`. A mismatch exits 2.

| File | Role |
| --- | --- |
| `support.json` | Minimal v0.1 contract (two `choice` cases, slimmed from `fixtures/support-triage.json`) |
| `replay-baseline.json` | Baseline snapshot (`model` `jev-1.13`) for `record` and `compare --from` |
| `replay-unchanged.json` | Compatible candidate (`model` `jev-1.14`), exit 0 |
| `replay-breaking.json` | Answer flip plus confidence drop, exit 1 |
| `jevcheck.yml` | Sample workflow. Copy to `.github/workflows/jevcheck.yml`. No secret. |

## Run locally

From the jevcheck repo root (or your repo, if this folder stays at `examples/`):

```bash
jevcheck eval examples/support.json \
  --candidate-model jev-1.14 \
  --answers examples/replay-unchanged.json
```

Exit 0. Summary ends with `compatible`.

```bash
jevcheck eval examples/support.json \
  --candidate-model jev-1.14 \
  --answers examples/replay-breaking.json
```

Exit 1. Summary ends with `breaking` and includes `general→billing` and `0.94→0.71`.

```bash
jevcheck record examples/support.json \
  --answers examples/replay-baseline.json \
  --out /tmp/baseline-answers.json
```

Exit 0. Writes a replay JSON.

```bash
jevcheck compare examples/support.json \
  --from examples/replay-baseline.json \
  --to jev-1.14 \
  --answers examples/replay-unchanged.json
```

Exit 0.

```bash
jevcheck compare examples/support.json \
  --from examples/replay-baseline.json \
  --to jev-1.14 \
  --answers examples/replay-breaking.json
```

Exit 1.

`python -m jevcheck` is the same CLI when the `jevcheck` script is not on `PATH`.

## GitHub Actions

Copy `jevcheck.yml` to `.github/workflows/jevcheck.yml`. Leave this directory at the repo root so the workflow paths (`examples/support.json`, `examples/replay-unchanged.json`, `examples/replay-baseline.json`) resolve. If you move the JSON files, change those inputs.

The workflow calls `sathariels/jevcheck/.github/actions/jevcheck@main`, installs `jevcheck==0.2.0` from PyPI, and runs `eval` plus `compare` on the unchanged replay. It does not set `TYPESAFE_API_KEY`. The breaking replay is omitted because exit 1 fails the job.

Use `@main` until a tag that contains `.github/actions/jevcheck` exists. `v0.2.0` is the PyPI package tag and does not include the action.
