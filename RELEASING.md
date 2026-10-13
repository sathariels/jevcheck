# Releasing

Tag, GitHub Release, and PyPI upload happen after the release pull request is merged. The release pull request does not push a tag, open a GitHub Release, or upload to PyPI.

There is no publish workflow. `.github/workflows/` contains `ci.yml`, `jevcheck-example.yml`, `pr-triage.yml`, and `plugin-scan.yml` only. PyPI upload is a manual `twine upload` from the tag.

`v0.2.1` is on PyPI and is the first tag that contains `.github/actions/jevcheck`. Documented `uses:` refs for this release pin `@v0.2.2`. The composite action's default install is `jevcheck==0.2.2`, so that install succeeds only after the upload below.

`.github/workflows/jevcheck-example.yml` passes `jevcheck-version: "0.2.1"` so the in-repo proof installs the published package and stays green before the upload. `ci.yml` installs the checkout and does not use PyPI.

## Post-merge steps for 0.2.2

1. Merge the release pull request into `main`.
2. Tag that merge commit and push the tag:

   ```bash
   git switch main
   git pull origin main
   # HEAD must be the merge commit of the 0.2.2 release PR.
   git tag -a v0.2.2 -m "v0.2.2 — dependency pins, eval tests, and audit status"
   git push origin v0.2.2
   ```

3. Create the GitHub Release `v0.2.2` from that tag. Title:

   ```text
   v0.2.2 — dependency pins, eval tests, and audit status
   ```

   Notes: use the [v0.2.2 release notes](#github-release-notes-for-v022) below. Paste them as the release body. They use `pip install jevcheck==0.2.2` with no "after PyPI publish" heading.

4. From a clean checkout of the tag, build and upload:

   ```bash
   git switch --detach v0.2.2
   python3 -m venv .venv-release
   source .venv-release/bin/activate
   python -m pip install --upgrade build twine
   python -m build
   python -m twine check dist/*
   python -m twine upload dist/*
   ```

   `twine check` should pass with no deprecation warnings. `twine upload` uses the owner's PyPI credentials for the `jevcheck` project.

5. After the upload, remove `jevcheck-version: "0.2.1"` from `.github/workflows/jevcheck-example.yml` so that workflow uses the Action default `0.2.2`.

If the tag date is not 2026-10-13, update the `[0.2.2]` heading in `CHANGELOG.md` on a follow-up commit. The compare link at the bottom of the changelog resolves once `v0.2.2` exists.

## GitHub release notes for v0.2.2

Paste the following as the release body:

~~~~markdown
## Highlights

- `typesafe-sdk` lock is 0.7.4. The install floor stays `typesafe-sdk>=0.7.0`.
- GitHub Actions pins: `actions/checkout` 7.0.1, `actions/setup-python` 7.0.0, and `hashgraph-online/ai-plugin-scanner-action` 1.2.777, still by commit SHA.
- Eval coverage for tolerance edges, multiple expectations, and error paths. CI prints a coverage report.
- `evaluate()` accepts a concrete candidate pin that has surrounding whitespace.
- The v0.1 recheck P1/P2 findings are marked resolved in be58041 (v0.2.0).
- Pin `sathariels/jevcheck/.github/actions/jevcheck@v0.2.2`. `@v0.2.1` is the first tag that contains the Action.

## Install

```
pip install jevcheck==0.2.2
```

## Action

```yaml
- uses: sathariels/jevcheck/.github/actions/jevcheck@v0.2.2
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
