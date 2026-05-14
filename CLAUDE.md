# Job RAG — Agent Map

> This file is the **table of contents**, not the encyclopedia.
> Keep it under ~120 lines. Real knowledge lives under `docs/eng/`.
> If a rule belongs in many places, put it in `docs/eng/` and link to it here.

**Job RAG** is a personal resume editor MVP that tailors resumes to job postings using two retrieval systems: *Evidence RAG* (proof points from resume/brag-doc/projects) and *Style RAG* (writing voice from approved edit packs). Stack: Python 3.11 (Poetry), Streamlit, Postgres + pgvector, OpenAI APIs, Docker Compose.

## Where to look

| Topic | File |
|---|---|
| Repository layout, modules, data flow | `docs/eng/architecture.md` |
| Code conventions and golden principles | `docs/eng/conventions.md` |
| Quality gates: `just`, lint, format, CI | `docs/eng/quality-gates.md` |
| How agents work in this repo | `docs/eng/agents.md` |
| Design decisions (ADRs) | `docs/eng/design-docs/index.md` |
| Active execution plans | `docs/eng/exec-plans/index.md` |
| Issue tracking conventions | `docs/eng/issue-tracking.md` |

## Run

Everything goes through `just`. Discover recipes with `just --list`.

```bash
just up          # start app at http://localhost:8501
just init-db     # initialize schema
just test        # pytest stack (Docker, Postgres on 5433)
just lint        # ruff + custom conventions lint
just typecheck   # mypy --strict on src/
just check       # full gate: lint + typecheck + test
just db          # psql shell
```

Development runs in Docker — do not run Python locally. Static checks (`lint`, `typecheck`) run on the host because they're faster and don't need the DB.

## Hard rules for agents

These are enforced mechanically. Violating one will fail `just lint`.

1. **No top-of-file `"""..."""` docstring banners.** They add noise without value. Use module-level comments only when the *why* is non-obvious. See `docs/eng/conventions.md#no-top-docstring`.
2. **No compound `cd`.** Every `cd` is its own Bash call. Never chain with `&&`, `;`, or `|`. See `docs/eng/conventions.md#no-compound-cd`.
3. **No unrelated drift.** When working a ticket, only touch files relevant to it. Revert incidental changes.
4. **Never reformat existing code** unless your change requires it.
5. **Never delete or modify tests** without explicit per-file approval.

Everything else lives in `docs/eng/conventions.md` — read it before non-trivial work.

## Issue tracking

All work tracked in the **Linear project "Job RAG"** via `mcp__linear-server__*` tools. See `docs/eng/issue-tracking.md` for status conventions.

## MCP tools

- File search: `mcp__fff__grep`, `mcp__fff__find_files`, `mcp__fff__multi_grep`. Plain `grep` in Bash is denied.
- Linear: `mcp__linear-server__*`.
