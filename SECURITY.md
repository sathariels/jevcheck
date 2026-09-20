# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.2.x   | Yes       |
| 0.1.x   | No        |

Only the latest 0.2.x release line receives security updates.

## Reporting a Vulnerability

If you discover a security vulnerability in jevcheck, please report it privately.

1. Do not open a public GitHub issue for the vulnerability.
2. Use [GitHub private vulnerability reporting](https://github.com/sathariels/jevcheck/security/advisories/new) on this repository.
3. Include the affected version or commit, reproduction steps, impact, and any known mitigations.

Please do not attach live API keys, tokens, or other credentials to the report. Redact secrets and describe how they were obtained.

We aim to:

- acknowledge vulnerability reports within 7 days
- provide an initial triage response within 14 days
- resolve confirmed issues as quickly as practical based on severity and release risk

## Scope

This policy covers:

- the `jevcheck` Python package published from this repository
- the reusable GitHub Action under `.github/actions/jevcheck`
- CI workflows and automation maintained in this repository

## Secure Use Guidance

- Keep live TypeSafe / System One credentials in `TYPESAFE_API_KEY` (or another secret store). Never commit real keys.
- Use replay fixtures (`--answers`, `--from`) in CI so jobs do not need a live API key.
- Pin third-party GitHub Actions to full commit SHAs.
- Prefer the latest supported 0.2.x release.
