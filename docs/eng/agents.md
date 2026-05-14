# Working in this repo as an agent

This repo is designed around the *Humans steer, agents execute* model. The human picks the goal; the agent does the work end-to-end, including reading docs, writing code, running tests, opening PRs, and responding to review.

## Entry point

1. Read `CLAUDE.md` (the map).
2. Read the topic-specific doc under `docs/eng/` that the map points to.
3. Read the relevant `src/` files.
4. Do the work. Do not invent context that isn't in the repo — if it isn't here, it doesn't exist.

## Repository legibility rules

- **No untracked context.** If a constraint matters, it lives in `docs/eng/` or in a lint rule. Slack threads and meeting notes don't survive context resets — promote them to the repo.
- **Progressive disclosure.** The map is small; the deeper docs are scoped. Don't grow `CLAUDE.md` past ~120 lines.
- **Mechanical over aspirational.** A rule that isn't enforced by lint or CI will drift. Either encode it or delete it.
- **Plans are first-class.** Non-trivial work goes through `docs/eng/exec-plans/active/`, then moves to `completed/` on merge.

## The execution loop (Ralph Wiggum)

For a typical feature:

1. Read the Linear ticket.
2. Drop a brief plan into `docs/eng/exec-plans/active/<slug>.md` if the change is non-trivial.
3. Write the code.
4. `just check` — fix anything red.
5. Open a PR.
6. Respond to review feedback. Iterate until green.
7. Merge. Move the plan file to `docs/eng/exec-plans/completed/`.

## The gardening agents

Two scheduled agents keep entropy in check:

- **Doc gardener** (`scripts/gardening/garden_docs.sh`) — scans `docs/eng/` for drift against the actual code (renamed files, missing references, stale recipes) and opens a PR if it finds something.
- **Slop gardener** (planned) — runs `ruff --fix` + `ruff format` + the custom conventions lint across the tree and opens cleanup PRs.

They run as GitHub Actions cron jobs (see `.github/workflows/`). Their PRs are small and auto-mergeable by design.

## When the agent gets stuck

If you find yourself working around the same problem twice, the fix is almost never "try harder." Identify the missing capability — a tool, a doc, a lint rule, a script — and add it to the repo so the next run doesn't hit the same wall. Then continue the task.
