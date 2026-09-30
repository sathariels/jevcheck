# Releasing

Tag, GitHub Release, and PyPI upload happen after the release pull request is merged. The release pull request does not push a tag, open a GitHub Release, or upload to PyPI.

There is no publish workflow. `.github/workflows/` contains `ci.yml`, `jevcheck-example.yml`, `pr-triage.yml`, and `plugin-scan.yml` only. PyPI upload is a manual `twine upload` from the tag.

`v0.2.1` is the first tag that contains `.github/actions/jevcheck`. Documented `uses:` refs pin `@v0.2.1`. The composite action installs `jevcheck==0.2.1` from PyPI, so that install succeeds only after the upload below.

## Post-merge steps for 0.2.1

1. Merge the release pull request into `main`.
2. Tag that merge commit and push the tag:

   ```bash
   git switch main
   git pull origin main
   # HEAD must be the merge commit of the 0.2.1 release PR.
   git tag -a v0.2.1 -m "v0.2.1 — GitHub Action, tutorial, and packaging metadata"
   git push origin v0.2.1
   ```

3. Create the GitHub Release `v0.2.1` from that tag. Title:

   ```text
   v0.2.1 — GitHub Action, tutorial, and packaging metadata
   ```

   Notes: use the [v0.2.1 release notes](#github-release-notes-for-v021) below. Paste them as the release body. They use `pip install jevcheck==0.2.1` with no "after PyPI publish" heading.

4. From a clean checkout of the tag, build and upload:

   ```bash
   git switch --detach v0.2.1
   python3 -m venv .venv-release
   source .venv-release/bin/activate
   python -m pip install --upgrade build twine
   python -m build
   python -m twine check dist/*
   python -m twine upload dist/*
   ```

   `twine check` should pass with no deprecation warnings. `twine upload` uses the owner's PyPI credentials for the `jevcheck` project.

5. After the upload, `.github/workflows/jevcheck-example.yml` on `main` can install `jevcheck==0.2.1`. Until then, that workflow's PyPI install fails. `ci.yml` does not install from PyPI.

If the tag date is not 2026-09-30, update the `[0.2.1]` heading in `CHANGELOG.md` on a follow-up commit. The compare link at the bottom of the changelog resolves once `v0.2.1` exists.

## GitHub release notes for v0.2.1

Paste the following as the release body:

~~~~markdown
## Highlights

- Composite GitHub Action `.github/actions/jevcheck`. Pin `sathariels/jevcheck/.github/actions/jevcheck@v0.2.1`. `v0.2.0` does not contain the Action.
- First-run tutorial (`docs/tutorial.md`) and an offline `examples/` pack. Replay eval and compare need no API key.
- Optional jevtriage pull-request workflow, skipped when `TYPESAFE_API_KEY` is unset.
- SPDX `license = "MIT"`, Python 3.13 and 3.14 in classifiers and CI, changelog, and Homepage / Source / Issues / Changelog URLs.
- CLI commands, exit codes, and eval rules match 0.2.0.

## Install

```
pip install jevcheck==0.2.1
```

## Action

```yaml
- uses: sathariels/jevcheck/.github/actions/jevcheck@v0.2.1
  with:
    contract: contracts/support.json
    command: eval
    candidate-model: jev-1.14
    answers: fixtures/candidate-replay.json
```
~~~~

## Existing v0.2.0 GitHub Release

The published [v0.2.0 release](https://github.com/sathariels/jevcheck/releases/tag/v0.2.0) still says "Install (after PyPI publish)". PyPI has had `jevcheck==0.2.0` since 2026-09-19. A release pull request cannot edit that release. If the owner edits it by hand, replace that section with:

~~~~markdown
## Install

```
pip install jevcheck==0.2.0
```
~~~~

Leave the rest of the v0.2.0 highlights as published. Leave the `v0.2.0` tag where it is.
