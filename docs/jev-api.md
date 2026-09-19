# TypeSafe Jev / System One API (verified)

Pinned from official TypeSafe Python SDK docs on 2026-09-19. **Do not invent fields** beyond this page.

Sources:

- [Python SDK](https://docs.typesafe.ai/sdk/python.md)
- [Sync client](https://docs.typesafe.ai/sdk/python/api/clients/sync/client.md)
- [Questions](https://docs.typesafe.ai/sdk/python/api/types/questions.md)
- [Responses](https://docs.typesafe.ai/sdk/python/api/types/responses.md)

## Install and auth

- Package: `typesafe-sdk` (`pip install typesafe-sdk`)
- Auth: `TYPESAFE_API_KEY` only (or `TypeSafeClient(api_key=...)`)
- Optional env: `TYPESAFE_DEFAULT_MODEL`, `TYPESAFE_BASE_URL`
- HTTP (third-party guides; prefer the SDK): `POST https://api.typesafe.ai/v1/systemone`

jevcheck never reads any other API-key environment variable.

## Client call

```python
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

with TypeSafeClient(model="jev-1.13.0") as client:  # documented version pin; not jev-latest
    response = client.system_one(
        state="I was charged twice. Please fix this ASAP.",
        questions={
            "billing": Noul(instructions="Is this ticket about billing?"),
            "tone": Choice(
                instructions="What is the customer's tone?",
                criteria={"calm": None, "frustrated": None, "angry": None},
            ),
            "urgency": Score(
                instructions="How urgent is this ticket?",
                criteria=["can wait", "this week", "today"],
            ),
        },
        model="jev-1.13.0",  # per-call override
    )

print(response.nouls["billing"].noul)
print(response.choices["tone"].choice)
print(response.scores["urgency"].score)
```

`state` is text, a JSON object, or an array. It cannot be `None`; nested values may be `None`.

Questions may be SDK objects or dictionaries with a `type` of `"noul"`, `"choice"`, or `"score"`.

## Question types

| Type | Class | Key fields |
| --- | --- | --- |
| noul | `Noul` | `instructions?`, `criteria?` `{true, false}` (yes/no descriptions) |
| choice | `Choice` | `instructions?`, **required** `criteria: Mapping[str, desc \| None]` |
| score | `Score` | `instructions?`, **required** nonempty ordered `criteria: Sequence` (levels from 0) |

`instructions` and criteria descriptions are JSON content: text, object, or array.

Empty `questions` and an empty score `criteria` list are SDK errors.

## Response (`SystemOneResponse`)

- `model: str`
- `usage: {input_tokens?, output_tokens?}`
- `answers: dict[str, Answer]`
- helpers: `.nouls`, `.choices`, `.scores`

### ChoiceAnswer

- `type`: `"choice"`
- `choice: str` — highest-probability label
- `confidence: float` in `[0, 1]`
- `probabilities: dict[str, float]` — per-label, sums to ~1

### NoulAnswer

- `type`: `"noul"`
- `noul: float` in `[0, 1]` — probability of yes/true
- **No separate `confidence` field** in the official schema

### ScoreAnswer

- `type`: `"score"`
- `score: float` — probability-weighted expected score (may fall between integer levels)
- `confidence: float` in `[0, 1]`
- `legend` — SDK 0.7.0 public type uses **integer** keys; JSON wire keys are strings
- `probabilities` — same integer-key SDK map; values should sum to ~1

jevcheck stringifies score map keys when adapting a real SDK response. It does not invent TypeSafe fields.

## Confidence mapping used by jevcheck

Owner lock: do not invent a second noul confidence field.

| Answer | Scalar used for min-confidence / regressions / optional Gate |
| --- | --- |
| choice | API `confidence` |
| score | API `confidence` |
| noul | API `noul` (probability of yes) |

If this mapping is not enough, stop and ask — do not fabricate fields.

## Model pinning and alias resolution

The SDK may inherit a model from `TypeSafeClient(model=...)` or `TYPESAFE_DEFAULT_MODEL`. Official TypeSafe model docs (fetched 2026-09-19) list a versioned pin `jev-1.13.0` and identify **`jev-latest` and `jev-preview` as moving aliases**. The response `model` field is the resolved version.

jevcheck alias policy (also in `jevcheck.pinning`):

1. Names are never rewritten. `jev-1.13` is not treated as `jev-1.13.0`.
2. A name is **unpinned** when it is `jev-latest` or `jev-preview` (case-insensitive) or contains `latest` or `preview`.
3. Empty / whitespace names are invalid (not pins).
4. Production calls fail closed unless `allow_unpinned=True` / `--allow-unpinned`.
5. When a candidate is requested, the response `model` must equal that candidate exactly. Null is rejected; it is never stringified to `"None"`.

Repo fixtures that say `jev-1.13` or `jev-1.14` are **unverified example labels**. Do not treat them as confirmed live catalog IDs.
