# Quality Gates

> Mechanical enforcement is what lets humans steer and agents execute. Every gate listed here produces an actionable error message so an agent can self-correct without human intervention.

## The single entrypoint

Everything goes through `just`. Discover recipes: `just --list`.

| Recipe | What it does |
|---|---|
| `just lint` | `ruff check` + `ruff format --check` + `scripts/lint_conventions.py` |
| `just format` | `ruff check --fix` + `ruff format` |
| `just typecheck` | `mypy --strict` on `src/` |
| `just test` | Pytest stack via Docker Compose (Postgres on 5433) |
| `just hooks` | Run all pre-commit hooks on every tracked file |
| `just check` | Full gate: lint + typecheck + test. Run before opening a PR. |
| `just install-hooks` | One-time setup: install pre-commit |

## What runs where

| Gate | Host | Docker | Pre-commit | CI |
|---|---|---|---|---|
| `ruff check` | ✓ | | ✓ | ✓ |
| `ruff format` | ✓ | | ✓ | ✓ |
| `lint_conventions.py` | ✓ | | ✓ | ✓ |
| `mypy --strict` | ✓ | | ✓ | ✓ |
| `pytest` | | ✓ | | (future: needs DB service) |

Static checks run on the host because they're fast and need no DB. Tests run in Docker because they need Postgres + pgvector.

## Ruff

Configured in `pyproject.toml` under `[tool.ruff]`. Conservative ruleset (`E,F,I,B,UP`) — real errors, unused code, import order, common bugs, py-version upgrades. Expand the rule set only when the baseline is clean.

When you add a new ruff rule, prefer ones whose default message is already actionable. Otherwise wrap the rule in `lint_conventions.py` so we control the error text.

## Custom conventions lint

`scripts/lint_conventions.py` enforces project-specific rules that ruff doesn't cover — see [`conventions.md`](./conventions.md) for the full list. Each rule:

- Has a stable kebab-case ID.
- Prints a remediation hint and a link back to the conventions doc.
- Honors `.lint-baseline.txt` so we can add rules without a one-shot mass cleanup.

To run it standalone:

```bash
python scripts/lint_conventions.py
```

## CI

`.github/workflows/check.yml` runs `just lint` and `just typecheck` on every PR and on pushes to `main`. Tests are not yet wired into CI (they need a Postgres + pgvector service container — track in Linear).

## Pre-commit

`.pre-commit-config.yaml` runs the same lints locally before each commit. To activate:

```bash
just install-hooks
```

To run on the whole tree (useful before opening a PR):

```bash
just hooks
```

## Adding a new gate

1. Add the check (custom script or off-the-shelf tool).
2. Wire it into `justfile` as a named recipe.
3. Add it to `.pre-commit-config.yaml` so it runs locally.
4. Add it to `.github/workflows/check.yml` so it runs in CI.
5. Document it here.

If steps 2–5 feel like too much for the gate to justify, the gate probably isn't worth adding.
