# Evidence fixtures (optional)

For RAG eval: add evidence documents and expected retrieval mapping.

1. **evidence_docs.json** — list of documents to load into the evidence store. Each item:
   - `source_id` (string): identifier for this doc (e.g. `"resume_1"`, `"project_a"`). Eval prefixes these with `eval_fixture_` and removes them after the run.
   - `text` (string): the evidence text (resume bullets, project description, etc.). It will be chunked and embedded like production.

2. **expected_retrieval.json** — which evidence should be retrieved for which requirement. Structure:
   - Keys: case IDs (e.g. `"rag_01"`), for grouping.
   - Values: list of `{"requirement": "...", "expected_source_id": "..."}`. For each pair, we run `EvidenceRAG.retrieve(requirement, top_k=5)` and check that a chunk from `expected_source_id` appears in the **top 3** results. At least 80% of pairs must pass for the RAG eval to pass.

**Run RAG eval:** set `EVAL_RAG=1` and have Postgres (with pgvector) available. From the host, the default `DATABASE_URL` uses host `postgres` (Docker), so run the eval inside the app container:
```bash
docker-compose exec app env EVAL_RAG=1 poetry run python scripts/run_evals.py
```
Or set `DATABASE_URL` to a reachable Postgres (e.g. `postgresql://user:pass@localhost:5432/db`) and run `EVAL_RAG=1 make eval` (or `req-eval`) locally.
