# Job RAG - Resume Editor MVP

A resume editor that uses Evidence RAG and Style RAG to help tailor your resume to job postings.

## Features

- **Job Posting Ingestion**: Fetch and extract text from job posting links
- **Requirement Extraction**: Use LLM to extract structured requirements from postings
- **Evidence RAG**: Retrieve matching proof points from your resume/brag-doc/projects
- **Style RAG**: Learn and apply your preferred writing style
- **Edit Pack Generation**: Generate exact bullets to add/replace with citations
- **Job Ranking**: Rank jobs by evidence coverage

## Setup

### Prerequisites
- Docker and Docker Compose
- Poetry (for local development, optional)

### Quick Start

1. Copy `.env.example` to `.env` and fill in your API keys:
   ```bash
   cp .env.example .env
   # Add your OPENAI_API_KEY
   ```

2. Build and start services:
   ```bash
   make build
   make up
   ```

3. Initialize the database:
   ```bash
   make init-db
   ```

4. Access Streamlit UI at http://localhost:8501

## Usage

### Streamlit UI

1. **Add Evidence**: Use the sidebar to add evidence from your resume, brag-doc, or projects
2. **Process Jobs**: Paste job posting URLs in the "Process Jobs" tab
3. **Review Rankings**: Check the "Ranked Jobs" tab to see jobs sorted by evidence coverage
4. **Approve Edit Packs**: Review and approve/edit packs in the "Review Edit Packs" tab
   - Approved packs are automatically added to Style RAG for future use

## Running evals

The regression suite runs requirement extraction on fixed job-posting fixtures and compares results to expected outputs. Use it to catch regressions after LLM or RAG changes.

```bash
make eval
```

- **Fixtures**: `tests/fixtures/job_postings.json` — each case has `raw_text` and `expected_requirements`. Add cases from the DB with `poetry run python scripts/export_job_fixtures.py` (then add `expected_requirements` by hand).
- **Results**: Written to `data/eval/extraction_results.json` (metrics, pass/fail, latency per case). The command exits with code 0 if all pass, non-zero if any fail (e.g. for CI).
- **RAG evals** (optional): Set `EVAL_RAG=1` and add `tests/fixtures/evidence/evidence_docs.json` and `expected_retrieval.json` to run evidence retrieval checks. Requires a running DB.

## Architecture

- **Evidence RAG**: Stores resume snippets, project descriptions, brag-doc entries
- **Style RAG**: Stores approved edit packs to learn writing style
- **Postgres + pgvector**: Vector database for embeddings
- **Streamlit**: Web UI for workflow and review
