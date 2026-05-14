# Architecture

## Layout

| Path | Purpose |
|---|---|
| `app.py` | Streamlit UI entrypoint |
| `cli.py` | CLI entrypoint (Typer) |
| `src/` | Application code — extractors, RAG, generators, edit packs |
| `prompts/` | LLM prompt templates used in production paths |
| `prompts_dev/` | Experimental prompts; not loaded in prod |
| `scripts/` | One-off scripts: `init_db.py`, fixture export, evals, gardening |
| `tests/` | Pytest suite + fixtures |
| `docs/eng/` | Engineering knowledge base (this directory) |
| `docs/` (rest) | Local-only user content — resume, brag doc, LinkedIn export. **Gitignored.** |
| `adr/` | (legacy) Architecture decision records — see `docs/eng/design-docs/` |
| `data/` | Local data outputs (eval results). Gitignored. |

## Two retrieval systems

- **Evidence RAG** — pulls proof points from resume, brag doc, projects. See `src/evidence_*.py`.
- **Style RAG** — learns the user's voice from approved edit packs. See `src/style_rag.py`, `src/edit_pack_generator.py`.

Both index into Postgres + pgvector. Schema is initialized by `scripts/init_db.py` and managed by Alembic migrations.

## Runtime topology

```
┌───────────┐    ┌──────────────────┐
│ Streamlit │───▶│ src/ orchestrators│──┐
│  (app.py) │    └──────────────────┘  │
└───────────┘                          ▼
                       ┌──────────────────────┐
                       │ Postgres + pgvector  │
                       └──────────────────────┘
                                  ▲
                                  │
                         ┌────────────────┐
                         │ OpenAI/Anthropic│
                         └────────────────┘
```

Docker Compose brings up `app` (Streamlit on 8501) and `postgres` (5432, 5433 for tests).

## Layering rule

Until we have enough surface area to justify a strict layered architecture, follow the conventional Python practice: **`app.py` and `cli.py` are thin entrypoints; all business logic lives in `src/`; `src/` modules import only from `src/` and stdlib/third-party.** No reverse dependencies. Tests in `tests/` import from `src/` but not vice versa.

When this stops being enough (e.g. we need stricter boundaries between Evidence RAG, Style RAG, and the editor pipeline), promote it to an explicit layer model with a custom lint — following the article's pattern of [layered domain architecture](https://openai.com/index/codex-engineering/).
