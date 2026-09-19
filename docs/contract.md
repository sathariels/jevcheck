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
| `baseline_model` | yes for JSON | Pinned production model this contract was recorded against |
| `allow_unpinned` | no | If `true`, floating `*latest*` names are allowed (default `false`) |
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

Every key in `expect` must exist in `questions`. Extra unknown keys are rejected.

## Field expectations

All keys optional except that a field should state *what* must hold.

| Key | Applies to | Meaning |
| --- | --- | --- |
| `choice` | choice | Expected winning label. Different label → **answer flip** |
| `noul_true` | noul | Expected yes (`true`) or no (`false`) vs `noul_true_threshold`. Opposite polarity → **answer flip** |
| `noul` | noul | Expected `noul` float. Used with `noul_tolerance` / `min_noul` |
| `min_noul` | noul | Floor on the `noul` float (yes-probability) |
| `noul_tolerance` | noul | Allowed absolute drift from `noul` |
| `score` | score | Expected expected-score. Nearest integer level change → **answer flip** |
| `score_tolerance` | score | If `\|actual - expected\| <=` this, treat score as same even if nearest level would differ |
| `min_confidence` | all | Floor on the [mapped scalar](jev-api.md#confidence-mapping-used-by-jevcheck) |
| `baseline_confidence` | all | Previously recorded scalar (e.g. `0.94`) |
| `confidence_tolerance` | all | Allowed drop from `baseline_confidence` |

Noul has no API `confidence`. The mapped scalar is `noul` itself.

## Outcomes (per field, worst wins the case)

1. **answer flip** — categorical change: choice label, noul yes/no, or score nearest level (unless within `score_tolerance`); or the answer is missing / wrong type.
2. **confidence regression** — same answer, but the mapped scalar is below `min_confidence` / `min_noul`, or dropped more than `confidence_tolerance` from `baseline_confidence`, or noul drifted more than `noul_tolerance` from expected `noul`.
3. **unchanged** — answer matches and scalars stay within the pinned floors/tolerances.

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
