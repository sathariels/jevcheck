# jevcheck contract format (v0.1)

A **contract** is the production baseline: pinned model, fixtures, and expected answers. `jevcheck eval` compares a candidate model against that contract and reports unchanged cases, confidence regressions, and answer flips.

This format is owner-locked for v0.1. Ask before changing it.

## Files

- **JSON** (recommended): one object with metadata + `cases`.
- **JSONL**: one case object per line. Blank lines ignored. Optional first-line metadata object with `"_meta": true`.

## Contract object

```json
{
  "version": "0.1",
  "name": "support-triage",
  "baseline_model": "jev-1.13",
  "allow_unpinned": false,
  "defaults": {
    "min_confidence": 0.8,
    "confidence_tolerance": 0.1,
    "noul_true_threshold": 0.5,
    "noul_tolerance": 0.1,
    "score_tolerance": 0.5
  },
  "cases": []
}
```

| Field | Required | Meaning |
| --- | --- | --- |
| `version` | yes | Must be `"0.1"` |
| `name` | no | Shown in the CLI summary |
| `baseline_model` | yes for JSON | Pinned production model this contract was recorded against. Empty `""` is rejected. Floating aliases (`jev-latest`, `jev-preview`, or any name containing `latest`/`preview`) are rejected unless `allow_unpinned` / `--allow-unpinned`. jevcheck does not rewrite aliases: `jev-1.13` is not `jev-1.13.0`. |
| `allow_unpinned` | no | If `true`, floating `jev-latest` / `jev-preview` names are allowed (default `false`) |
| `defaults` | no | Applied when a case field omits the same key |
| `cases` | yes for JSON | Fixture list |

JSONL without a `_meta` line still needs `--baseline-model` on the CLI (or a per-eval override).

## Case object

```json
{
  "id": "ticket-001",
  "state": "I was charged twice. Please fix this ASAP.",
  "questions": {
    "intent": {
      "type": "choice",
      "instructions": "What is this ticket about?",
      "criteria": {"billing": null, "general": null}
    }
  },
  "expect": {
    "intent": {
      "choice": "billing",
      "min_confidence": 0.85,
      "baseline_confidence": 0.94
    }
  }
}
```

`state` and `questions` match the verified System One request: see `docs/jev-api.md`. Question objects use `type` of `noul`, `choice`, or `score` and only those official fields.

Every key in `expect` must exist in `questions`. Extra unknown keys are rejected. An empty field expect (`{}`) is rejected. Kind-specific keys on the wrong question type (for example `score` on a choice question) are rejected. Shared confidence keys may appear on any field. This is an applicability check; the fixture key set is unchanged.

## Field expectations

All keys optional except that a field must state at least one *effective* constraint (a kind-specific answer key, `min_noul`, `min_confidence`, or `baseline_confidence` **together with** a resolved `confidence_tolerance` or `min_confidence` floor). A baseline-confidence-only expect with no applicable floor or tolerance after defaults is rejected (exit 2). Do not assume a default `confidence_tolerance`. Tolerance-only objects are rejected.

| Key | Applies to | Meaning |
| --- | --- | --- |
| `choice` | choice | Expected winning label. Different label → **answer flip** |
| `noul_true` | noul | Expected yes (`true`) or no (`false`) vs `noul_true_threshold`. Opposite polarity → **answer flip** |
| `noul` | noul | Expected `noul` float. Used with `noul_tolerance` / `min_noul` |
| `min_noul` | noul | Floor on the `noul` float (yes-probability) |
| `noul_tolerance` | noul | Allowed absolute drift from `noul` (inclusive; exact 0.1 drop against 0.1 passes, with a 1e-9 epsilon so binary float subtraction of decimal tenths does not false-fail) |
| `score` | score | Expected expected-score. Nearest integer level change → **answer flip** |
| `score_tolerance` | score | **Level-flip suppression**, not an absolute max distance. If `\|actual - expected\|` is within this inclusive bound (same 1e-9 epsilon as confidence/noul; so 1.4 vs 1.6 at 0.2 is within), a nearest-level change is not a flip. When both values already share a nearest level (Python `round`, ties toward even: `1.5→2`, `2.5→2`), a larger float gap still counts as unchanged. Example: expected 1.8, actual 2.2, tolerance 0.1 → unchanged (both level 2). |
| `min_confidence` | all | Floor on the [mapped scalar](jev-api.md#confidence-mapping-used-by-jevcheck) |
| `baseline_confidence` | all | Previously recorded scalar (e.g. `0.94`) |
| `confidence_tolerance` | all | Allowed drop from `baseline_confidence` (inclusive, same 1e-9 epsilon as noul drift) |

Noul has no API `confidence`. The mapped scalar is `noul` itself.

## Outcomes (per field, worst wins the case)

1. **answer flip** — categorical change: choice label, noul yes/no, or score nearest level (unless `score_tolerance` suppresses that flip); or the answer is missing / wrong type.
2. **confidence regression** — same answer, but the mapped scalar is below `min_confidence` / `min_noul`, or dropped more than `confidence_tolerance` from `baseline_confidence`, or noul drifted more than `noul_tolerance` from expected `noul`. Inclusive boundaries: a drop of exactly 0.1 against tolerance 0.1 is not a regression.
3. **unchanged** — answer matches and scalars stay within the pinned floors/tolerances.

Choice and score answers must include a nonempty probability map of finite values `>= 0` whose sum is `1 ± 1e-6`. Missing, null, empty, negative, NaN, or badly normalized maps are rejected (exit 2). The adapter does not invent an empty map. Score answers also require a nonempty `legend` (SDK-shaped responses always include it). Score `legend` / `probabilities` coming from typesafe-sdk 0.7.0 may use integer keys; jevcheck stringifies those keys.

When `--candidate-model` is a **concrete pin**, every response `model` must equal that candidate exactly. A null or missing model is an error (never the string `"None"`). Opted-in floating aliases (`jev-latest`, `jev-preview`, or names containing those tokens) under `--allow-unpinned` accept a nonempty concrete response `model` that is not itself a floating alias; the eval report prints the resolved response model. Without `--allow-unpinned`, floating aliases stay rejected.

Repo examples such as `jev-1.13` / `jev-1.14` are **unverified example pin labels** for fixtures, not a claim that those IDs exist on the live TypeSafe catalog. A documented version pin on the 2026-09-19 model list is `jev-1.13.0`.

A higher candidate confidence is not a regression.

## Replay file (`--answers`)

For mocked evals and tests, a JSON object keyed by case `id`:

```json
{
  "ticket-001": {
    "model": "jev-1.14",
    "usage": {"input_tokens": 10, "output_tokens": 4},
    "answers": {
      "intent": {
        "type": "choice",
        "choice": "general",
        "confidence": 0.71,
        "probabilities": {"billing": 0.29, "general": 0.71}
      }
    }
  }
}
```

Answer objects use only verified System One fields.

`jevcheck record` (v0.2) writes this same file. `jevcheck compare --from` reads it as the baseline snapshot. See [`adr-009-two-model-compare.md`](adr-009-two-model-compare.md). `eval` remains fixture-versus-candidate.
