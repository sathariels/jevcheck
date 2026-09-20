# ADR 009 — Two-model / baseline comparison (v0.2 slice)

Status: accepted for the v0.2 slice. Packaging version stays `0.1.0` in this PR; the owner can tag `0.2.0` later. This document is the lock for `record` / `compare`.

v0.1 `eval` remains fixture-versus-candidate. This slice adds a second, explicit path so upgrade safety can mean **baseline answers versus candidate answers**, not only authored `expect` versus candidate.

## Commands

| Command | Meaning |
| --- | --- |
| `record` | Given a v0.1 contract and a baseline model, fetch System One answers for every case and write a replay JSON. The file is the same shape as `eval --answers` (`dump_replay` / `load_replay`). |
| `compare` | Evaluate a candidate against those recorded baseline answers, **or** fetch both models live. |
| Baseline recording | The act of calling `record` (or an equivalent in-process `record_answers`). It does **not** rewrite the contract schema. Fixture `expect` stays the v0.1 authored contract. |

Chosen CLI (one UX, documented here):

```
jevcheck record CONTRACT --out FILE [--baseline-model MODEL] [--answers REPLAY]
jevcheck compare CONTRACT --from FILE --to MODEL [--answers CANDIDATE_REPLAY]
jevcheck compare CONTRACT --from-model MODEL --to MODEL [--answers CANDIDATE_REPLAY]
```

- `--from FILE` is a recorded baseline replay. `--from-model MODEL` is a live baseline fetch. Exactly one is required.
- `--to` is the candidate pin (same role as `eval --candidate-model`).
- `--answers` on `record` / `compare` is a mocked replay so CI and tests need no key. On `compare` it is the **candidate** replay.
- `--baseline-model` still overrides contract / JSONL metadata. With `--from-model`, that live pin is the baseline identity.
- `eval CONTRACT --candidate-model … [--answers]` is unchanged.

## How compare decides

Compare does not invent a second scoring engine. It builds a derived contract: same cases, questions, defaults, and floors/tolerances; each `expect` field is filled from the baseline answer (`choice` / `noul`+`noul_true` / `score`, plus `baseline_confidence` from the [mapped scalar](jev-api.md#confidence-mapping-used-by-jevcheck)). Then it runs existing `evaluate()` on the candidate.

Missing baseline cases or missing expected fields are usage errors (exit 2), not silent flips. Wrong-kind baseline answers are usage errors. Candidate missing answers stay v0.1 **answer flips**.

Compare does **not** invent a default `confidence_tolerance`. Drop detection uses the contract’s resolved defaults, same as v0.1.

## Identity and pinning

Reuse v0.1 `require_pinned` / `require_response_identity` for every requested model and every response `model`:

- Concrete pins: exact string equality. `jev-1.13` is not `jev-1.13.0`.
- Floating aliases (`jev-latest`, `jev-preview`, or any name containing `latest` / `preview`) stay rejected unless `--allow-unpinned`.
- With that opt-in, a nonempty concrete (non-alias) response model is accepted and reported. jevcheck never rewrites a name.

`record` identity-checks the baseline. `compare --from` identity-checks each recorded baseline response against the contract / `--baseline-model` pin. `compare --from-model` identity-checks the live baseline. The candidate is identity-checked as in `eval`.

## Exit codes (unchanged)

| Code | Meaning |
| --- | --- |
| 0 | Compatible (`compare`) or successful write (`record`) |
| 1 | Behavioral contract failure (flips / confidence regressions) |
| 2 | Usage / input / identity / missing answers / unpinned without opt-in |
| 3 | Operational (SDK HTTP / invalid API body) |

Secret redaction on error text is unchanged.

## Non-goals

- Not a pytest plugin.
- `Gate` is unchanged and is still not the product.
- Contract JSON schema stays v0.1 (`version: "0.1"`). Record writes a replay file; it does not emit a new contract format.
- No TypeSafe / System One fields beyond [docs/jev-api.md](jev-api.md).
- No `0.2.0` git tag in this PR.
