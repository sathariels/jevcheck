# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.2] - 2026-10-13

### Added

- Eval tests for tolerance edges, several expectations on one case, wrong-type and missing answers, identity failures, and alias resolution.
- `pytest-cov` on the `dev` extra. CI prints a coverage report and does not fail on a coverage threshold.

### Changed

- `requirements.lock` pins `typesafe-sdk==0.7.4`. The `pyproject.toml` floor stays `typesafe-sdk>=0.7.0`. Releases 0.7.1 through 0.7.4 are bug fixes, an optional `http2` extra, stricter request validation, and non-finite number serialization. They do not change a successful System One call or jevcheck's response adaptation.
- GitHub Actions stay pinned by commit SHA: `actions/checkout` 7.0.1, `actions/setup-python` 7.0.0, and `hashgraph-online/ai-plugin-scanner-action` 1.2.777 (from 4.2.2, 5.6.0, and 1.2.635). Checkout v5+ and setup-python v6+ run on Node 24 and need Actions runner v2.327.1 or newer. Checkout v7 refuses fork-PR checkouts for `pull_request_target` and `workflow_run`; these workflows do not use those events. `persist-credentials` and `python-version` are unchanged. setup-python v7 removes the unused `pip-install` input. The scanner bump is a patch; `plugin_dir`, `min_score`, and `fail_on_severity` are unchanged.
- Package version is `0.2.2` in `pyproject.toml`, `jevcheck.__version__`, and the Action input `jevcheck-version` (default `0.2.2`). Documented Action refs pin `@v0.2.2`. `@v0.2.1` remains the first tag that contains the Action.
- The v0.1 recheck's four P1/P2 findings are marked resolved in be58041 (v0.2.0).

### Fixed

- `evaluate()` identity-checks the stripped candidate returned by `require_pinned`. A concrete name with surrounding whitespace no longer passes the pin check and then fails against the same model id.

## [0.2.1] - 2026-09-30

Library source since [0.2.0] is the version string only. CLI commands, exit codes, and eval rules are unchanged.

### Added

- Composite GitHub Action [`.github/actions/jevcheck`](https://github.com/sathariels/jevcheck/blob/main/.github/actions/jevcheck/action.yml). It installs `jevcheck` from PyPI and runs `eval`, `compare`, or `record`.
- Example workflow [`.github/workflows/jevcheck-example.yml`](https://github.com/sathariels/jevcheck/blob/main/.github/workflows/jevcheck-example.yml) for replay `eval` and `compare` with no API key.
- Optional [pr-triage workflow](https://github.com/sathariels/jevcheck/blob/main/.github/workflows/pr-triage.yml). It calls `sathariels/jevtriage@v0.1.0` with model `jev-1.13.0` only when `TYPESAFE_API_KEY` is set.
- First-run tutorial ([`docs/tutorial.md`](https://github.com/sathariels/jevcheck/blob/main/docs/tutorial.md)) and an offline [`examples/`](https://github.com/sathariels/jevcheck/blob/main/examples/README.md) pack for compatible (exit 0) and breaking (exit 1) replays with no API key.
- `SECURITY.md`, Dependabot, `requirements.lock`, and the Plugin Security Scan workflow. That change does not alter public CLI or Action behavior.
- This changelog and [`RELEASING.md`](https://github.com/sathariels/jevcheck/blob/main/RELEASING.md).

### Changed

- Package version is `0.2.1` in `pyproject.toml`, `jevcheck.__version__`, and the Action input `jevcheck-version` (default `0.2.1`).
- Documented Action refs pin `@v0.2.1`. That is the first tag that contains `.github/actions/jevcheck`. `v0.2.0` does not.
- License metadata is the SPDX expression `MIT`, with `license-files = ["LICENSE"]`. The `License :: OSI Approved :: MIT License` classifier is removed. Builds require `setuptools>=77`.
- Classifiers and the CI test matrix include Python 3.13 and 3.14. `requires-python` stays `>=3.11`.
- `project.urls` lists Homepage, Source, Documentation, Issues, and Changelog.
- README install leads with `pip install jevcheck`. README links to docs, examples, and workflows are absolute GitHub URLs.

## [0.2.0] - 2026-09-20

### Added

- `jevcheck record` writes a baseline replay JSON in the same shape as `eval --answers`. The contract schema stays `"0.1"`.
- `jevcheck compare` checks a candidate against that snapshot (`--from`) or fetches both models live (`--from-model` and `--to`).
- Record and compare summaries print `alias → resolved` when an opted-in alias resolves to a different model id.
- [ADR 009](https://github.com/sathariels/jevcheck/blob/v0.2.0/docs/adr-009-two-model-compare.md) locks this path. `eval`, identity rules, exit codes, and Gate stay as in 0.1.0.

### Fixed

- `record`, and `compare` when it loads a replay, reject an answer whose kind does not match the question (choice, noul, or score) instead of writing a snapshot `compare` later refuses.

## [0.1.0] - 2026-09-20

### Added

- Fixture-versus-candidate `jevcheck eval` for a v0.1 JSON or JSONL contract (baseline model, cases, and expected answers).
- Choice, noul, and score checks, including confidence floors and confidence drops.
- Explicit model pinning. `jev-latest` and `jev-preview` are rejected unless `--allow-unpinned`.
- CLI (`jevcheck` and `python -m jevcheck`), Jev client, and optional Gate helper.
- Contract loader, replay fixtures, the support-triage example, and API docs (`docs/contract.md`, `docs/jev-api.md`).
- GitHub Actions CI that runs a CLI eval smoke test on replay fixtures.

### Fixed

- Fail-closed model pinning and response identity, rejection of ineffective expects and invalid probability maps, inclusive float tolerances, and SDK HTTP errors as a distinct ops exit with secret redaction.
- A baseline-confidence-only expect needs a floor or tolerance after defaults. An opted-in floating alias accepts a concrete resolved response model. Replay and adapter paths require nonempty normalized score probabilities and a legend.
- The sdist ships tests and fixtures.

[0.2.2]: https://github.com/sathariels/jevcheck/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/sathariels/jevcheck/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/sathariels/jevcheck/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/sathariels/jevcheck/releases/tag/v0.1.0
