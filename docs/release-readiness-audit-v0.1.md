# Jevcheck v0.1.0 release-readiness audit

**Verdict: NOT READY. I would not tag this commit v0.1.0.**

Audited GitHub commit `55986d9d8cfc291e5c8c36e8475a0071652d4210` on 2026-09-19. The GitHub clone matched `/Users/sathariels/Downloads/jevcheck-main` before generated installation files. The task's original directory contained no source. The audited clone remained Git-clean. No product code, dependencies, fixture formats, or semantics were changed; all additional probes were written outside the repository.

## What the project actually does

Jevcheck loads a manually authored JSON or JSONL contract, obtains one candidate response per case from Jev or a replay file, and compares expected fields with those responses. It reports choice changes, yes/no polarity changes, score-level changes, and confidence/drift violations. A passing evaluation exits 0; detected contract violations exit 1. Many input/setup failures exit 2.

**This is fixture-versus-model evaluation, not two-model execution.** `baseline_model` labels the report; it does not trigger a baseline request or establish that the fixture values were recorded from that model. There is no `compare --from --to`, baseline-recording command, `pin` command, or pytest plugin. The README generally describes contract evaluation correctly, but “proves” safety and reproducibility are stronger than the implementation supports. See [src/jevcheck/cli.py:61](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/src/jevcheck/cli.py#L61) and [src/jevcheck/eval.py:100](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/src/jevcheck/eval.py#L100).

The actual CLI has one subcommand, `eval`, with `--candidate-model`, `--baseline-model`, `--answers`, and `--allow-unpinned`. Both the console command and `python -m jevcheck` work after wheel installation. The top-level Python API exports `JevClient`, `load_contract`, `Contract`, `Case`, `FieldExpect`, typed answer/response models, `evaluate`, `evaluate_case`, report/result/outcome models, pinning helpers, and optional `Gate`/`Action`/`Decision`. `ContractDefaults`, replay helpers and `FieldDiff` are available in submodules but not top-level exports. See [src/jevcheck/__init__.py:3](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/src/jevcheck/__init__.py#L3).

## Highest-priority fixes, in release order

1. **Fix the real SDK score adapter (P1).** SDK 0.7.0 returns integer-keyed score `legend` and `probabilities`. Jevcheck uses `dict[str, ...]`, and calls SDK `model_dump()` in Python mode. A valid mocked HTTP score response therefore reaches Jevcheck and fails with six key-validation errors, exit 2. The support-triage live path and README Python example are affected. Existing FakeSDK objects use string keys and conceal this. Evidence: `sdk-results.json`, mode `score`; [src/jevcheck/answers.py:35](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/src/jevcheck/answers.py#L35), `adapt_answer` at line 66 and `_to_mapping` at line 111. Add a regression test using the actual SDK with a mocked transport.
2. **Make model identity and pinning trustworthy (P1).** Asking for `jev-1.14` with a replay response labeled `unrelated-model` or null still exits 0 and reports the requested candidate. Null is converted to the string `"None"`. Baselines `""` and `jev-latest` also pass, and the genuinely floating `jev-preview` is accepted as pinned. Validate baseline policy and response identity, define alias resolution explicitly, and replace unverified live model examples. Evidence: `wrong-model`, `null-model`, `floating-baseline`, `empty-baseline`, `preview-alias`; [src/jevcheck/eval.py:100](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/src/jevcheck/eval.py#L100), [src/jevcheck/answers.py:96](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/src/jevcheck/answers.py#L96), [src/jevcheck/pinning.py:10](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/src/jevcheck/pinning.py#L10), [src/jevcheck/contract.py:83](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/src/jevcheck/contract.py#L83). Model-version policy changes need the owner's approval.
3. **Reject ineffective contracts and malformed answers (P1).** `expect: {"q": {}}` passes; a choice question with `expect: {"q": {"score": 2}}` also passes because that expectation is ignored. Missing, empty, negative, NaN, or badly normalized choice probabilities can all yield exit 0. The adapter silently supplies empty probability maps. Validate expectation applicability and meaningful constraints, numeric finiteness, and required response data; agree on normalization tolerance before enforcing it. Evidence: `empty-expect`, `wrong-kind-expect`, `prob-*`; [src/jevcheck/contract.py:25](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/src/jevcheck/contract.py#L25), [src/jevcheck/contract.py:61](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/src/jevcheck/contract.py#L61), [src/jevcheck/answers.py:66](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/src/jevcheck/answers.py#L66). Do not silently redefine the fixture format.
4. **Fix inclusive numeric boundaries and document score semantics (P1/P2).** Baseline confidence 0.8, actual 0.7, tolerance 0.1 fails, although the intended decimal drop is exactly permitted: binary subtraction produces 0.10000000000000009. Noul absolute drift has the same defect. Score tolerance currently suppresses level flips; it is not an absolute maximum difference. Expected 1.8, actual 2.2, tolerance 0.1 passes because both round to level 2. This latter behavior matches the detailed format documentation, so changing it requires a semantic decision. Evidence: `drop-exact`, `noul-drift-exact`, `score-same-level-outside-tolerance`; [src/jevcheck/eval.py:248](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/src/jevcheck/eval.py#L248), [src/jevcheck/eval.py:274](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/src/jevcheck/eval.py#L274), [src/jevcheck/eval.py:299](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/src/jevcheck/eval.py#L299). Python `round` also uses ties-to-even at half levels; document/test that rule.
5. **Harden operational errors and release verification (P2, security-sensitive).** Real SDK HTTP 401/429/500 and invalid-response exceptions escape the CLI handler, print tracebacks, and exit 1, indistinguishable by exit code from behavioral failure. Catch appropriate SDK errors, redact secrets, add transport/installed-wheel tests to CI, and repair the source manifest so tests/examples ship coherently. Evidence: SDK modes `401`, `429`, `500`, `invalid-response`; [src/jevcheck/cli.py:56](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/src/jevcheck/cli.py#L56) and [pyproject.toml:37](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/pyproject.toml#L37). A synthetic server error echoing the fake API key printed that sentinel; no real secret was used.

## Commands and results

Commands below were executed from the task workspace unless specified. `work/repo` is the fresh clone; separate virtual environments isolate editable and built-wheel checks. The evidence archive includes the exact CLI command arrays, outputs, probe scripts and inputs.

| Command/check | Result |
|---|---|
| `git clone https://github.com/sathariels/jevcheck.git work/repo` | Success; HEAD `55986d9d8cfc291e5c8c36e8475a0071652d4210` |
| `git status --short`, `git log --all --oneline`, `git rev-parse HEAD` | Clean; available history inspected |
| `diff -rq -x .git -x '*.egg-info' work/repo /Users/sathariels/Downloads/jevcheck-main` | Sources identical |
| `python3 -m venv work/audit-venv` | Clean Python 3.12.3 environment |
| `work/audit-venv/bin/python -m pip install -e 'work/repo[dev]'` | Documented editable install succeeds; SDK 0.7.0, Pydantic 2.13.5, pytest 9.1.1 |
| In `work/repo`: `env -u TYPESAFE_API_KEY ../audit-venv/bin/python -m pytest -ra` | **32 passed, 1 skipped**, 0.14 seconds |
| Configured lint/type checks | None present in pyproject or CI; none claimed as passed |
| In `work/repo`: `../audit-venv/bin/python -m build --outdir ../dist` | Wheel and sdist built successfully; setuptools license-metadata deprecation warnings |
| `python3 -m venv work/wheel-venv`; install `work/dist/jevcheck-0.1.0-py3-none-any.whl` | Success in second clean environment |
| `work/wheel-venv/bin/python -m pip check` | No broken requirements |
| Import/version outside repository | Imported installed wheel from site-packages; version 0.1.0 |
| Installed console help and eval help | Exit 0; one actual subcommand (`eval`) |
| Installed CLI on unchanged replay | Exit 0; 3 unchanged, compatible |
| Installed CLI on breaking replay | Exit 1; 1 unchanged, 1 regression, 1 flip |
| Installed `python -m jevcheck eval ... --answers ...replay-unchanged.json` | Exit 0 outside repository |
| `work/audit-venv/bin/python work/audit_checks.py` | 40 process-level CLI probes; observations below |
| `work/wheel-venv/bin/python work/run_sdk_probes.py` | 9 actual-SDK/mock-transport scenarios; no live service calls |
| `pip wheel --no-deps work/dist/jevcheck-0.1.0.tar.gz -w work/sdist-wheel` | Rebuild from sdist succeeds |
| `pytest -q` in extracted sdist, with key removed | Exit 2, four collection errors: missing `tests.helpers` |
| Python snippet syntax checks | README snippet compiles; `docs/jev-api.md` snippet does not |
| History secret-pattern scan | 34 reachable Git blobs scanned; no matching credential material; only `.env.example` tracked |

No live API request was made. The complete normal suite ran with `TYPESAFE_API_KEY` removed from its environment; the optional test is gated by that variable. Only Python 3.12 was exercised locally, not the CI matrix's Python 3.11.

## Explicit comparison and error matrix

All replay checks below used the installed wheel's CLI in a directory outside the source checkout. They are observations, not a claim that all checks passed their intended safety criteria.

| Input/scenario | Observed result |
|---|---|
| Same expected and actual choice | Compatible, exit 0 |
| Changed choice a → b | Breaking, exit 1 |
| Confidence floor 0.8: actual 0.8 / 0.800001 / 0.799999 | Exits 0 / 0 / 1, correct inclusive floor |
| Same answer, confidence 0.2 against floor 0.8 | Regression, exit 1 |
| Baseline 0.8, drop allowance 0.1: actual 0.7 / 0.700001 / 0.699999 | Exits **1 / 0 / 1**; exact decimal boundary incorrectly fails |
| Score expected 2, tolerance 0.5: actual 1.5 / 1.500001 / 1.499999 | Exits 0 / 0 / 1 |
| Score expected 1.8, tolerance 0.1, actual 2.2 | Exit 0: same rounded level, despite difference 0.4 |
| Noul expected true at 0.5 threshold: actual 0.5 / 0.500001 / 0.499999 | Exits 0 / 0 / 1 |
| Noul expected 0.8, tolerance 0.1, actual 0.7 | Incorrect regression, exit 1 |
| Missing / empty / negative / NaN / bad-sum choice probabilities | All compatible, exit 0 |
| Probability data is a string | Validation error, exit 2 |
| Missing answer | Repo test confirms answer flip; no silent pass |
| NaN score | Exit 2 during evaluation, rather than schema validation |
| Malformed contract JSON | Exit 2 with concise diagnostic |
| Non-mapping response answers | Uncaught TypeError, traceback, exit 1 |
| Missing credentials | Exit 2, helpful key/replay instruction |
| SDK mocked network connection failure / timeout | Exit 2, no traceback |
| SDK mocked 401 / 429 / 500 / invalid response | Exit 1 with traceback |
| Real SDK choice response through mocked HTTP | Compatible, exit 0; request model explicitly passed |
| Real SDK score response through mocked HTTP | Adapter validation failure, exit 2 |
| Response model differs from requested candidate | Compatible, exit 0; candidate heading is misleading |

The transport probes captured only requests to the candidate model. Source inspection confirms `evaluate` invokes `fetch(case)` once per case; there is no baseline model execution.

## Jev API: verified versus uncertain

Official pages were fetched directly over HTTPS after the browser retrieval tool could not open their Markdown URLs. Installed SDK source was also inspected.

- **Verified:** `typesafe-sdk`, `TypeSafeClient`, keyword model selection at client/call level, `system_one(state, questions, model=...)`, dictionary questions, and `TYPESAFE_API_KEY` auth. The mocked transport confirmed `/v1/systemone`, the model in the request body, and Bearer authentication without displaying the header value. [Python SDK](https://docs.typesafe.ai/sdk/python.md), [client reference](https://docs.typesafe.ai/sdk/python/api/clients/sync/client.md).
- **Verified:** Choice has choice/confidence/probabilities; Noul has a yes-probability with no independent confidence; Score has expected score, confidence, legend and probabilities. The SDK's public score maps use integer keys. Jevcheck's fake SDK does not reproduce that detail. [Response reference](https://docs.typesafe.ai/sdk/python/api/types/responses.md), [question reference](https://docs.typesafe.ai/sdk/python/api/types/questions.md).
- **Verified mismatch:** Current official model documentation lists `jev-1.13.0`, and identifies both `jev-latest` and `jev-preview` as moving aliases. The response model identifies the actual version. Jevcheck only checks names containing `latest`. [Models](https://docs.typesafe.ai/models.md).
- **Unverified live assumptions:** This audit found no authoritative confirmation that the repository's `jev-1.13` shorthand or `jev-1.14` example is a usable current model. The documented list does not establish either. Do not present them as verified production pins; no live server rejection or acceptance was tested.
- **Policy rather than upstream API:** Mapping Noul's yes-probability to “confidence” is a documented Jevcheck decision. It treats highly confident “no” differently from Choice confidence. It is not a fabricated API field, but defaults such as `min_confidence: 0.8` can conflict with an expected false answer. Preserve the policy unless explicitly changed.

## Test quality and CI

The tests provide useful basic coverage: fixture loading, unknown-field rejection, minimum nonempty structure, mocked client calls, choice and Noul flips, score-level changes, confidence regression, missing answers, replay summaries, floating-latest rejection, and module invocation. Normal tests need no API key. `test_live.py` skips without `TYPESAFE_API_KEY`; with a key present, plain pytest does opt into the live call automatically. See [tests/test_live.py:10](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/tests/test_live.py#L10).

They provide **insufficient release confidence**. `FakeSDK` uses `SimpleNamespace` responses with hand-authored string-keyed scores; it bypasses SDK response normalization. Most CLI tests invoke `main()` rather than an installed console script. Pytest's `pythonpath = ["src", "."]` can hide packaging mistakes. Test helpers supply distributions not necessarily consistent with their score/choice values. There were no exact drop-tolerance, candidate-model mismatch, real SDK error, invalid distribution, effective-expectation, or built-artifact tests. This is why 32 green tests coexist with a broken live score adapter.

CI runs editable installation and pytest on Python 3.11/3.12 only. There is no configured linter/type checker, build/install verification, independent console-script smoke job, or release workflow. The existing module smoke test is exercised indirectly through pytest. [.github/workflows/ci.yml:9](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/.github/workflows/ci.yml#L9).

## Packaging, documentation, Gate, and security

**Packaging:** Wheel installation, imports, `py.typed`, license inclusion, console entry point and module entry point work. Dependencies are lower-bounded without an upper bound or lock; this audit verifies only the resolved versions above. The sdist rebuilds, but contains tests without `tests/helpers.py`, `tests/conftest.py` or `tests/__init__.py`, and omits fixtures and docs. Consequently its tests cannot collect and README fixture commands cannot run from the extracted archive. This is an sdist completeness problem, not a wheel import failure.

**Documentation/example:** The repository includes a plausible three-ticket support-triage example spanning choice, Noul and score, plus passing/breaking replay files and a JSONL example. Both README replay commands behave as described. The live command cannot be endorsed until model IDs and score adaptation are fixed. Replay fixtures are not proven recorded baselines; some score values are inconsistent with their distributions (e.g. probabilities 0.02/0.08/0.90 imply 1.88, while the fixture says 1.9). `docs/jev-api.md`'s Python snippet closes the questions mapping with `)` instead of `}` around line 39, causing SyntaxError. There is no consumer GitHub Actions example that gates an upgrade on `jevcheck eval`; the repo's own CI tests replay behavior. [README.md:28](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/README.md#L28), [docs/jev-api.md:26](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/docs/jev-api.md#L26).

**Gate:** Optional and unrelated to model comparison. Boundaries work: below 0.5 rejects, exactly 0.5 asks a human, exactly 0.85 auto-accepts. Inverted thresholds are rejected when `decide()` is called, not at construction. Noul uses the documented yes-probability mapping. This helper does not compensate for release blockers in the primary evaluator. [src/jevcheck/gate.py:26](https://github.com/sathariels/jevcheck/blob/55986d9d8cfc291e5c8c36e8475a0071652d4210/src/jevcheck/gate.py#L26).

**Security:** `.gitignore` excludes real `.env` files while retaining an empty `.env.example`. A credential-pattern scan of 34 reachable historical blobs found no matching secrets; this is not proof against every possible credential format or unreachable/deleted remote objects. The client reads `TYPESAFE_API_KEY` or an explicit `api_key=` and does not intentionally print it. Normal mocked authentication did not leak the fake key. However, a mocked API error body containing the fake key was printed in an uncaught traceback. There is no application-level redaction, and raw Pydantic errors can include input values. Treat “secrets are never printed” as unverified and currently falsifiable under echoed-error conditions. No real keys were printed or used.

## Release decision

Keep the current snapshot untagged as v0.1.0. Fix SDK score interoperability and the paths that incorrectly report compatibility first, agree on model/validation semantics, then add independent regression tests and rerun the complete suite plus wheel/sdist and CLI checks. Two-model execution is absent; it need not be added to ship a clearly scoped fixture evaluator, but it must not be advertised as implemented.

Evidence accompanies this report in `jevcheck-audit-evidence.zip`. It contains raw process results, synthetic inputs, probe scripts, test/build logs, and the bounded history scan results. All security probes use a deliberately fake credential sentinel.
