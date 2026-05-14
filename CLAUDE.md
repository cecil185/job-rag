# Project Context

**Job RAG** is a personal resume editor MVP that tailors resumes to job postings using two retrieval systems:
- **Evidence RAG** — pulls proof points from resume/brag-doc/projects
- **Style RAG** — learns from approved edit packs to match the user's writing voice

Stack: Python (Poetry), Streamlit UI, Postgres + pgvector, OpenAI APIs, Docker Compose.

## Layout

| Path | Purpose |
|---|---|
| `app.py` | Streamlit entrypoint |
| `cli.py` | CLI entrypoint |
| `src/` | Application code (extractors, RAG, edit pack generator, etc.) |
| `prompts/`, `prompts_dev/` | LLM prompt templates |
| `scripts/` | One-off scripts (init_db, fixture export, evals) |
| `tests/` | Pytest suite + fixtures |
| `adr/`, `docs/` | Architecture decision records and docs |
| `data/` | Local data outputs (eval results, etc.) |
| `worktree-*/`, `run-agent-*.sh` | Parallel agent worktrees and launchers |

## Run

Development happens in Docker via the Makefile — do not run Python locally.

```bash
make build       # build images
make up          # start app at http://localhost:8501
make init-db     # initialize schema
make test        # pytest stack (Postgres on port 5433)
make eval        # requirement extraction regression suite
make db          # psql shell
```

# Issue Tracking

Use the **Linear project "Job RAG"** for all task tracking on this repo. Create tickets there for bugs, features, and follow-ups discovered during work. Use the Linear MCP tools (`mcp__linear-server__*`) — see the `linear` and `create-linear-ticket` skills for conventions.

# Agent Instructions

## Worktree Discipline
- Verify the working directory and git branch before editing
- When working a Linear ticket, only modify files related to that ticket; revert unrelated drift
- With multiple worktrees present, confirm the target worktree path before applying edits

## No Compound Commands
STRICTLY FORBIDDEN: never use `cd` in a compound command. Each `cd` must be its own isolated Bash tool call — never chain with `&&`, `;`, or any other operator.

## Style
- No `""" """` docstring blocks at the top of `.py` files
- Comment sparingly — prefer code that expresses intent on its own
- Don't repeat the same point twice in a response
- Never reformat whitespace or style in existing code unless the change requires it

## Testing
Never delete or modify tests without explicit approval per file. When splitting PRs or refactoring, preserve all existing tests unless told otherwise.

# MCP

## Find
- Use fff MCP tools for all file search — `grep` in Bash is denied
- `mcp__fff__grep` (file contents), `mcp__fff__find_files` (by name/topic), `mcp__fff__multi_grep` (OR across patterns)
- The `mcp__fff` namespace has no direct tools — call the suffixed names above
