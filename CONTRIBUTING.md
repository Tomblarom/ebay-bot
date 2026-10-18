# Contributing

Use Python 3.12+ and PDM. Run `pdm install`, then `pdm run format`, `pdm run lint`,
and `pdm run test`. Tests must remain offline with synthetic data/API responses.
New Python files require SPDX copyright, AGPL-3.0-or-later and homepage headers.
Preserve existing copyright and human credits; use full type hints and tests for
observable behavior and failure/duplicate handling.

Use English code/docs/logs, with German runtime translations. Never commit
credentials, private ad files, tokens or runtime databases. Use only the external
Kleinanzeigen CLI and generated files, never internal Python APIs. Submit focused
pull requests describing behavior, motivation and validation.
