# Quality gates for Job RAG.
# Philosophy: humans steer, agents execute. Every gate is mechanical and
# produces a clear, actionable error message so agents can self-correct.

default:
    @just --list

# --- Quality gates --------------------------------------------------------

# Fast static checks: ruff lint + format-check + custom conventions. No Docker.
lint:
    ruff check src app.py cli.py scripts tests
    ruff format --check src app.py cli.py scripts tests
    python scripts/lint_conventions.py

# Auto-fix what can be fixed, then format.
format:
    ruff check --fix src app.py cli.py scripts tests
    ruff format src app.py cli.py scripts tests

# Type check (mypy strict on src/, per existing pre-commit config).
typecheck:
    mypy --strict --ignore-missing-imports --explicit-package-bases src

# Run all pre-commit hooks against the whole tree.
hooks:
    pre-commit run --all-files

# --- Gardening agents -----------------------------------------------------
# Run every gardener once. Report-only — never opens a PR locally.
garden:
    just garden-docs
    just garden-slop

# Doc-gardener: scan docs/eng/ for drift against the repo. Report only.
garden-docs:
    bash scripts/gardening/garden_docs.sh

# Doc-gardener with PR creation. Needs `gh` auth + a working tree on a branch.
# Used by the scheduled GitHub Actions workflow; rarely run by humans.
garden-docs-pr:
    GARDEN_OPEN_PR=1 bash scripts/gardening/garden_docs.sh

# Slop-gardener: auto-fix lint + format drift across the tree. Report only.
# Stages the resulting diff but does not commit — you decide what ships.
garden-slop:
    ruff check --fix src app.py cli.py scripts tests
    ruff format src app.py cli.py scripts tests
    python scripts/lint_conventions.py
    git --no-pager diff --stat

# Show the current convention-lint baseline (grandfathered violators).
garden-baseline:
    @cat .lint-baseline.txt

# Pytest stack (Docker, Postgres on 5433). Matches `make test`.
test:
    docker-compose -f docker-compose.pytest.yml run --rm pytest

# Requirement extraction regression suite.
eval:
    docker-compose run --rm app python scripts/run_evals.py

# The full gate. Run before opening a PR / before merge.
check: lint typecheck test

# --- Setup ----------------------------------------------------------------

# One-time dev setup: install pre-commit hooks.
install-hooks:
    pre-commit install

# --- Docker shortcuts (mirror Makefile) -----------------------------------

build:
    docker-compose build

up:
    docker-compose down
    docker-compose up

down:
    docker-compose down

logs:
    docker-compose logs -f app

shell:
    docker-compose exec app /bin/bash

db:
    docker-compose exec postgres psql -U jobrag -d jobrag_db

init-db:
    docker-compose exec app poetry run python scripts/init_db.py
