# Jevcheck v0.1.0 — release audit recheck

**Verdict: NOT READY, but substantially improved.** I would not tag exact commit `8b1852d05e952d66d7cee49cc6e49d14a10b1a5f` until the remaining effective-expectation and score-boundary defects are fixed, and the advertised alias opt-in is reconciled with response identity checking.

Audited the latest fetched `origin/main`, advancing from `55986d9` to `8b1852d05e952d66d7cee49cc6e49d14a10b1a5f`. No source changes were made. Git status is clean. This is still fixture-versus-model evaluation, not execution of two versions; the updated README now says so explicitly.

## Verification completed

- Full repository suite: **73 passed, 1 skipped** (live test gated by `TYPESAFE_API_KEY`). Previously 32 passed.
- Built a new wheel and sdist, installed the wheel into a fresh Python 3.12.3 virtual environment, confirmed imports/dependencies and both CLI entry points outside the repository.
- Repeated the original **40 installed-console CLI probes**, plus **6 additional edge-case probes**.
- Repeated **9 real-SDK scenarios with a mocked HTTP transport**. No live API requests or real credentials were used. Valid SDK choice and score responses now succeed; the score scenario completes all three support-triage cases.
- Extracted the new sdist and ran the whole suite: **73 passed, 1 skipped**. Test helpers, fixtures, and docs are now included.
- README and API documentation Python snippets both compile.
- Rechecked official model documentation over HTTPS: aliases resolve to a versioned response ID. [Official models](https://docs.typesafe.ai/models.md).
- Bounded credential-pattern scan: **56 reachable Git blobs**, no matching credentials; only `.env.example` tracked. This is not an exhaustive guarantee against every secret format.
- No lint/type checks are configured, and no Python 3.11 or live-service execution was performed locally. CI configuration now includes build, installed-wheel, and sdist tests; I did not claim a remote Actions run passed.

## Previous findings: results now

| Previous defect | Independent recheck |
|---|---|
| Real SDK integer-keyed score maps rejected | **Fixed:** valid mocked HTTP score responses exit 0 |
| Wrong/null response model falsely compatible | **Fixed:** exit 2 |
| Empty/floating baseline accepted | **Fixed:** exit 2 without opt-in |
| `jev-preview` accepted as pinned | **Fixed:** rejected without opt-in |
| Empty or wrong-kind expectation accepted | **Fixed for those inputs:** exit 2; related baseline-only hole remains below |
| Missing/empty/negative/NaN/bad-sum choice probabilities accepted | **Fixed:** exit 2 |
| Exact confidence drop and Noul drift false failures | **Fixed:** exact boundary exits 0, just-beyond boundary exits 1 |
| SDK 401/429/500 and invalid API response tracebacks | **Fixed:** concise errors, exit 3 |
| Synthetic echoed API key printed | **Fixed for tested CLI path:** sentinel redacted, no traceback |
| Malformed non-mapping response traceback | **Fixed:** exit 2 |
| Broken sdist test collection | **Fixed:** complete extracted suite passes |
| API docs snippet syntax error | **Fixed** |

Passing replay exits 0; breaking replay exits 1. Minimum-confidence and Noul polarity boundaries still behave correctly. SDK connection/timeouts exit 2 without tracebacks; HTTP/invalid SDK responses exit 3. The source comment broadly labels operational failures as exit 3, so documenting or unifying connection/timeout classification would improve clarity.

## Remaining findings

### 1. P1 — a baseline-confidence-only expectation is still ineffective

A choice contract with `expect: {"q": {"baseline_confidence": 0.95}}`, no defaults, and an actual confidence of **0.51** exits **0**, prints **unchanged**, and declares **compatible**. The response is otherwise coherent: selected `b`, probabilities `a=0.49`, `b=0.51`.

`_require_applicable_expect()` treats `baseline_confidence` as sufficient, but `_confidence_diff()` only evaluates a drop when `confidence_tolerance` is also present. Without a floor, choice constraint, or resolved tolerance, nothing is actually tested. The documentation explicitly calls this an effective constraint, making the silent pass misleading.

Evidence: `extra-results-recheck.json`, `baseline-only`; [src/jevcheck/contract.py:219](https://github.com/sathariels/jevcheck/blob/8b1852d05e952d66d7cee49cc6e49d14a10b1a5f/src/jevcheck/contract.py#L219) and [src/jevcheck/eval.py:323](https://github.com/sathariels/jevcheck/blob/8b1852d05e952d66d7cee49cc6e49d14a10b1a5f/src/jevcheck/eval.py#L323).

Suggested fix: validate effective constraints after resolving defaults; reject a baseline-only expectation when no applicable tolerance is available. Do not silently assume a new default tolerance or redefine semantics.

### 2. P2 — score tolerance still mishandles exact decimal boundaries

Expected score **1.4**, actual score **1.6**, `score_tolerance: 0.2` exits **1**, reporting an answer flip. The actual score response has valid legend and normalized probabilities (`1=0.4`, `2=0.6`). Decimal difference is exactly 0.2, which the documented inclusive tolerance should permit. Binary subtraction produces `0.20000000000000018`.

Confidence and Noul now use a tolerant comparison; score still uses direct `<=`. The original 2.0/1.5/0.5 score test passes because those values are exactly representable in binary and does not catch this.

Evidence: `extra-results-recheck.json`, `score-decimal-boundary`; [src/jevcheck/eval.py:297](https://github.com/sathariels/jevcheck/blob/8b1852d05e952d66d7cee49cc6e49d14a10b1a5f/src/jevcheck/eval.py#L297).

Suggested fix: apply the agreed inclusive numerical-boundary policy to score tolerance and add a decimal boundary regression test. Keep the documented same-rounded-level behavior unchanged.

### 3. P2 — allowed aliases cannot accept their legitimate resolved identity

With `--candidate-model jev-preview --allow-unpinned`, a matching response whose `model` is `jev-1.13.0` exits **2**, saying it does not match the requested candidate. The official API explicitly returns the versioned ID that answered an alias request. The CLI opt-in passes initial pin validation, but unconditional exact identity matching then rejects the expected API behavior.

This was reproduced with replay input, exercising the same `evaluate()` identity check used by live calls; no live alias request was made. [Official model/alias behavior](https://docs.typesafe.ai/models.md).

Evidence: `extra-results-recheck.json`, `alias-opt-in`; [src/jevcheck/eval.py:123](https://github.com/sathariels/jevcheck/blob/8b1852d05e952d66d7cee49cc6e49d14a10b1a5f/src/jevcheck/eval.py#L123) and [src/jevcheck/pinning.py:70](https://github.com/sathariels/jevcheck/blob/8b1852d05e952d66d7cee49cc6e49d14a10b1a5f/src/jevcheck/pinning.py#L70).

Suggested fix: explicitly decide how an opted-in alias resolves to a concrete version and how that version is reported/validated. Keep strict identity checking for concrete pins. Alternatively, stop advertising alias execution until that behavior is supported. This is a model-policy choice, not permission to relax every identity check.

### 4. P2 — malformed/missing score distributions still pass replay validation

A score response with `score=2`, `confidence=0.9`, and omitted, null, or empty `probabilities` exits **0** in each case. The corresponding choice defects are fixed, but ScoreAnswer still defaults missing maps to empty, accepts empty maps, and the adapter drops explicit nulls. Missing legends likewise remain optional locally, even though the real SDK response schema requires those fields.

The new contract documentation explicitly permits the empty-score-map path by only validating nonempty maps, so this is a remaining validation limitation and API parity gap, not a claim that the new implementation contradicts that particular documentation sentence. Replay can accept data that the SDK live path would reject.

Evidence: `extra-results-recheck.json`, `score-prob-missing`, `score-prob-null`, `score-prob-empty`; [src/jevcheck/answers.py:58](https://github.com/sathariels/jevcheck/blob/8b1852d05e952d66d7cee49cc6e49d14a10b1a5f/src/jevcheck/answers.py#L58), [src/jevcheck/answers.py:82](https://github.com/sathariels/jevcheck/blob/8b1852d05e952d66d7cee49cc6e49d14a10b1a5f/src/jevcheck/answers.py#L82), [src/jevcheck/answers.py:145](https://github.com/sathariels/jevcheck/blob/8b1852d05e952d66d7cee49cc6e49d14a10b1a5f/src/jevcheck/answers.py#L145). [Official response reference](https://docs.typesafe.ai/sdk/python/api/types/responses.md).

Suggested fix: agree on strict replay validation for required score fields and add parity tests using valid and invalid SDK-shaped responses.

## Documentation and test quality

The added real SDK transport tests materially improve confidence: they expose SDK normalization instead of substituting only handwritten namespaces. Packaging verification is also now meaningful. The new tests cover the earlier concrete cases, but the baseline-only acceptance, score decimal boundary, and alias opt-in interaction show that nearby boundaries still need independent checks.

The README distinguishes example labels from catalog IDs, but its primary live command and Python example still use unverified `jev-1.14`. The optional live test now uses `jev-1.13.0`. Prefer an executable live example using a documented ID and reserve hypothetical upgrade labels for replay examples. A live call was not used to verify availability for this account.

No two-model comparison was added. Gate behavior was not changed by this update; its tests still pass. Score tolerance is now clearly documented as level-flip suppression, and this audit does not propose changing that product rule.

## Commands run

From the task workspace unless a working directory is specified:

```text
git -C work/repo fetch origin
git -C work/repo merge --ff-only origin/main
git -C work/repo diff 55986d9 -- src/jevcheck pyproject.toml MANIFEST.in .github/workflows/ci.yml README.md docs/contract.md
(cd work/repo) env -u TYPESAFE_API_KEY ../audit-venv/bin/python -m pytest -ra
(cd work/repo) ../audit-venv/bin/python -m build --outdir ../dist-recheck
python3 -m venv work/recheck-venv
work/recheck-venv/bin/python -m pip install work/dist-recheck/jevcheck-0.1.0-py3-none-any.whl
work/recheck-venv/bin/python -m pip check
work/audit-venv/bin/python work/recheck_checks.py
work/recheck-venv/bin/python work/run_sdk_recheck.py
work/recheck-venv/bin/python work/extra_recheck.py
(cd work/sdist-recheck/jevcheck-0.1.0) env -u TYPESAFE_API_KEY ../../audit-venv/bin/python -m pytest -ra
python3 work/security_scan.py
git -C work/repo status --short
```

The evidence archive includes exact installed-CLI command arrays, outputs, synthetic inputs, scripts, and test/build results. The new artifact tests used SDK 0.7.0 and Pydantic 2.13.5. All original source edits were made upstream; this recheck modified no project source.

**Tag decision: no for this exact commit.** Most earlier blockers are genuinely fixed. Address the four remaining findings above, rerun the new reproductions, and the project will be much closer to a defensible fixture-evaluator v0.1.0 release.
