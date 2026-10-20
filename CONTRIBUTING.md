# Contributing

## Git workflow

1. Branch from `main`: `git switch -c feat/score-weights` (prefixes: `feat/`, `fix/`, `docs/`, `chore/`).
2. Make small commits using [Conventional Commits](https://www.conventionalcommits.org/), for example `feat(api): allow custom score weights`.
3. Run the checks locally (see below), then push and open a pull request. The PR template lists what to check.
4. CI must pass before merging. Prefer **squash merge** so `main` has one commit per change.
5. A merge to `main` triggers deployment once CI is green.

## Local checks

```bash
cd api && ruff check . && ruff format --check . && pytest
cd ingestor && mvn verify
docker compose up -d --build    # optional full-stack check
```

## Conventions

- Configuration comes only from environment variables. Never hard-code secrets, and never commit `.env`.
- Every new endpoint gets a test in `api/tests/`.
- Schema changes go in `ingestor/src/main/resources/schema.sql` and must be idempotent (`IF NOT EXISTS`).
