# CI/CD quality gate

`.github/workflows/ci.yml` runs on pull requests and pushes to `main`/`master`.
It provisions pgvector PostgreSQL and Redis, installs from lock/requirements,
runs Alembic, Ruff, pytest coverage, TypeScript, Vitest and the production build.
Separate jobs run Bandit, pip-audit, npm audit, secret-pattern scanning and
Playwright smoke tests. Failed Playwright reports are uploaded without using
application credentials.

The workflow has read-only repository permissions and no OpenAI secret. E2E uses
an empty provider configuration; paid calls are never part of CI. Branch
protection should require `quality-gate` and the organization should pin action
references to approved commit SHAs according to its policy.

Known local limitation: npm/pip advisory services may be unavailable in a
restricted network. A blocked scanner is reported as not verified; it must not
be converted into an always-successful step.
