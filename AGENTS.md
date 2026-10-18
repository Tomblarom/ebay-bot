# Agent guide

Read README.md and CONTRIBUTING.md. Use only the external Kleinanzeigen CLI and
its generated files. Never contact marketplaces in tests or publish real offers
as a development check. Preserve SPDX, AGPL and human credits. Use full Python
3.12+ type hints and English runtime messages with German translations. Validate
with `pdm run format`, `pdm run lint`, `pdm run test`. Changes to publish barriers
or uncertainty handling need regression tests.
