# Feature B: Eval Suite and Regression Tests for Extraction and RAG

Implement an evaluation suite that runs requirement extraction and evidence RAG matching on fixed inputs and compares results to expected outputs. This enables regression testing and basic observability (token count, latency) for LLM and RAG changes.

## 1. Eval dataset

### 1.1 Job posting fixtures

- Get raw_text from postgres data base jobs table
- Store them in a deterministic location, e.g.:
  - `tests/fixtures/job_postings/` with one file per case (e.g. `job_01.txt`, `job_02.txt`), or
  - A single JSON/YAML file mapping `case_id` → `{"raw_text": "...", "expected_requirements": [...]}`.
- For each case, define **expected requirements** (golden set) in a format you can compare against:
  - At minimum: a list of requirement strings (or categories + text) that should appear in the extractor output (e.g. overlap, containment, or set equality).
  - Optional: allow fuzzy matching (e.g. normalized text, or “at least N of the expected items appear in extracted”).

### 1.2 Evidence fixtures (optional but recommended)

- Add 1–2 **fixed evidence documents** (e.g. short resume or brag-doc snippets) with known chunks/source_ids.
- Define for a subset of job fixtures: “for requirement R, we expect evidence from source X to appear in top_k.”
- This allows regression testing of the evidence RAG path (embedding + retrieval) as well as extraction.

## 2. Extraction eval

### 2.1 Run extractor on fixtures

- For each job fixture, run the existing requirement extractor (same code path as production, e.g. `RequirementExtractor().extract(job_text)`).
- Parse the result into a comparable form (e.g. set of normalized requirement strings, or list of (category, text)).

### 2.2 Compare to expected

- Compare extracted requirements to the golden set using a defined metric, e.g.:
  - **Overlap:** fraction of expected items that appear in extracted (or vice versa), or
  - **F1 over sets:** precision and recall of extracted vs expected, then F1.
- Define a **pass threshold** (e.g. F1 ≥ 0.7 or “at least 80% of expected requirements have a matching extracted requirement”).
- If the extractor returns confidence/validation (Feature A), you can optionally assert minimum average confidence or that validated count is above a threshold.

### 2.3 Output and failure mode

- Write results to a structured format (e.g. JSON or SQLite) under `tests/eval_results/` or `data/eval/` with:
  - case_id, passed (bool), metric value(s), extracted list, expected list, optional diff.
- If any case fails (below threshold), the eval command should **exit with non-zero** so CI or `make eval` can fail the build.

## 3. Evidence RAG eval

### 3.1 Setup

- Use a **test DB or in-memory SQLite** (if supported) or a dedicated test schema so eval does not pollute production data.
- Load evidence fixtures into the evidence store (same chunking/embedding as production), then run retrieval for each requirement in the job fixture (or a subset of “expected requirement → expected evidence” pairs).

### 3.2 Check retrieval quality

- For each (requirement, expected_evidence) pair, run `EvidenceRAG.retrieve(requirement_text, top_k=5)` (or match_requirements) and check that the expected evidence (e.g. by source_id or content snippet) appears in the top_k results.
- Define pass criteria (e.g. “expected evidence in top 3 for at least 80% of pairs”).
- Eval command should exit non-zero if RAG checks fail.

## 4. CLI and Make integration

### 4.1 Eval command

- Add a **CLI entrypoint** (e.g. `python -m scripts.run_evals` or `poetry run eval`) that:
  - Runs extraction evals on all job fixtures.
  - Optionally runs RAG evals if evidence fixtures exist.
  - Writes results to the chosen output dir.
  - Exits with code 0 if all pass, non-zero if any fail.

### 4.2 Make target

- In the `Makefile`, add a target (e.g. `eval` or `run-evals`) that runs this command.
- Document in README that `make eval` runs the regression suite.

## 5. Observability hooks (optional)

- For each LLM call during eval, record **token count** (input + output if available) and **latency** (seconds).
- Log these to the result file or to stdout so that regressions in cost/latency can be spotted when comparing runs (e.g. in CI artifacts).

## 6. Acceptance criteria

- [ ] At least 5 job-posting fixtures with golden expected requirements.
- [ ] Extraction eval runs and compares to expected using a defined metric and threshold.
- [ ] Eval results are written to a file; eval command exits non-zero on failure.
- [ ] `make eval` (or equivalent) runs the full suite.
- [ ] Optional: evidence fixtures and RAG eval; optional: token/latency logging in results.

## 7. Files to add/touch (suggested)

- `tests/fixtures/job_postings/*.txt` (or one JSON/YAML) — job text + expected requirements.
- `tests/fixtures/evidence/*.txt` (optional) — evidence docs and expected mapping.
- `scripts/run_evals.py` (or `src/evals/run.py`) — load fixtures, run extractor and optionally RAG, compare, write results, set exit code.
- `src/evals/metrics.py` (optional) — functions for overlap/F1 between expected and extracted.
- `Makefile` — add `eval` target.
- `README.md` — add “Running evals” section.

Run your code to test that it works.