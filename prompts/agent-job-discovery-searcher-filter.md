# Agent prompt: Job discovery (Searcher + optional Filter)

## Goal

Add a **job discovery** layer so users can find jobs on the internet by criteria (role, location, keywords) instead of pasting URLs by hand. The flow is: **user enters search criteria** → **Searcher agent** returns a list of candidate job URLs (with title/snippet) → **optional Filter agent** scores or filters candidates by quick relevance → **user selects which to process** → existing **process_job_links** runs on the chosen URLs.

Implement at least the **Searcher**; the **Filter** is optional but recommended to avoid full processing of obviously irrelevant results.

## Codebase context

- **Ingestion**: `src/workflow.py` – `process_job_links(urls, ...)` takes a list of URLs and for each: fetch via `JobFetcher`, extract requirements, evidence RAG, fit score, edit pack. No discovery step exists today.
- **UI**: `app.py` – Tab "Process Jobs" has a text area for "Job Posting URLs (one per line)" and a button to process. You will add a **"Find jobs"** flow (new tab or section in Process Jobs) where the user enters criteria and gets back a list of candidate jobs to select from before processing.
- **Config**: `src/config.py` – `Settings` with `openai_api_key`, `llm_model`. You may add optional settings for job-search API keys (e.g. `SERPAPI_KEY`, `ADZUNA_APP_ID`, or similar) in `.env`; document any new env vars.
- **Patterns**: Use `logger` and timing logs like other modules; reuse `get_db` / `Session` only if the Filter needs DB (e.g. to compare against existing evidence); Searcher can be stateless.

## Your tasks

### 1. Search criteria model

- **Location**: Add a small dataclass or Pydantic model (e.g. in `src/job_discovery.py` or `src/models.py`) for search criteria, e.g.:
  - `role` (str): job title or role, e.g. "Software Engineer", "ML Engineer"
  - `location` (str, optional): e.g. "London", "Remote", "UK"
  - `keywords` (list of str or str, optional): extra terms, e.g. "Python", "LLMs"
- The Searcher and Filter take this structure as input so the interface is consistent.

### 2. Searcher agent

- **New module**: `src/job_searcher.py` (or `src/job_discovery.py` with a `JobSearcher` class).
- **Class**: `JobSearcher`. It can take optional API keys or config in the constructor (e.g. from `settings`).
- **Method**: `search(criteria: <your_criteria_type>) -> List[Dict]`.
  - **Input**: Search criteria (role, location, keywords).
  - **Output**: List of dicts, each with at least: `url` (str), `title` (str), and optionally `snippet` (str), `source` (str), `posted_date` (str) if available. These are **candidate** job postings; URLs should point to a page that `JobFetcher` can handle (HTML or PDF).
  - **Implementation options** (pick one or combine; document choice):
    - **Job API**: Use a job aggregator API (e.g. Adzuna, Findwork, Reed) if you have or add an API key. Map criteria to the API’s query params and map responses to the unified list format.
    - **Search API**: Use SerpAPI, Brave Search, or Google Custom Search to run queries like “{role} jobs {location}” and optionally restrict to known job domains (e.g. linkedin.com, indeed.com, company career pages). Parse results into `url`, `title`, `snippet`.
    - **RSS / curated list**: If you prefer no external API, you can stub the Searcher with a small set of example URLs or an RSS feed parser and document that “production” would plug in an API.
  - **Robustness**: If the chosen API is unavailable or returns no results, return an empty list and log; do not raise unless the implementation is clearly misconfigured (e.g. missing required API key when the backend requires it).
  - Use the same logging pattern as the rest of the app (e.g. `logger.info("JobSearcher.search: ... done in %.2fs", ...)`).

### 3. Filter agent (optional but recommended)

- **New module**: `src/job_filter.py` or inside `src/job_discovery.py`.
- **Class**: `JobFilter`. It can take an LLM client (e.g. OpenAI via `settings`) and optionally `EvidenceRAG` or a DB session if you want to pre-filter by fit (e.g. only jobs that mention skills the user has evidence for).
- **Method**: `filter(candidates: List[Dict], criteria: <criteria_type>, top_k: int = 20) -> List[Dict]`.
  - **Input**: List of candidates from the Searcher (each with `url`, `title`, `snippet`), the same search criteria, and an optional `top_k`.
  - **Output**: A subset (or reordering) of candidates, e.g. the top `top_k` by relevance. You can:
    - Use an LLM to score or rank each candidate’s title + snippet against the criteria (and optionally against a short summary of the user’s evidence); or
    - Use keyword matching / embedding similarity if you have embeddings for criteria vs. title+snippet.
  - **Goal**: Cheap relevance check so the user sees a shorter, more relevant list before running full `process_job_links` (which does fetch + extraction + RAG).
  - If you skip the Filter, document that and ensure the Searcher’s list is still usable (e.g. limit to first N results from the API).

### 4. Workflow integration

- In `src/workflow.py`:
  - Instantiate `JobSearcher` (and optionally `JobFilter`) in `Workflow.__init__`.
  - Add a new method: `find_jobs(criteria: <criteria_type>, top_k: int = 20) -> List[Dict]` that:
    1. Calls `job_searcher.search(criteria)` → list of candidates.
    2. If Filter is implemented, calls `job_filter.filter(candidates, criteria, top_k)` and returns the filtered list.
    3. Otherwise returns the first `top_k` from the Searcher (or all if fewer).
  - Return format: list of dicts with `url`, `title`, and any extra fields the UI needs (e.g. `snippet`). Do not run `process_job_links` inside `find_jobs`; let the UI or CLI call `process_job_links(selected_urls)` when the user confirms.

### 5. UI (Streamlit)

- In `app.py`:
  - Add a **"Find jobs"** experience. Options:
    - **Option A**: New tab "Find jobs" with a form: role (text), location (text), keywords (text or tags), and a "Search" button. On submit, call `workflow.find_jobs(criteria, top_k=20)` and store results in session state (e.g. `st.session_state.job_search_results`).
  - Display the results as a list or table: title, snippet, URL (as link). Each row has a **checkbox** (or multi-select) so the user can select which jobs to process.
  - A button **"Process selected jobs"** (or "Add to pipeline") that:
    1. Reads the selected URLs from the search results.
    2. Calls `workflow.process_job_links(selected_urls)` (or the same API used by the existing Process Jobs tab).
    3. Shows success/error and redirects or refreshes so the user can see the new jobs in "Ranked Jobs".
  - **Option B**: Integrate into the existing "Process Jobs" tab: above the URL text area, add a collapsible "Or find jobs by criteria" section that expands to the criteria form and search results; selected URLs can be pasted into the URL text area or sent directly to `process_job_links`.
  - Handle empty results: show "No jobs found" and suggest broadening criteria.

### 6. CLI (optional)

- In `cli.py`, add a command or subcommand, e.g. `find-jobs --role "Software Engineer" --location "Remote" --top 10`, that calls `workflow.find_jobs(...)` and prints the list of URLs (and optionally titles) so power users can pipe or copy URLs.

### 7. Configuration and docs

- **Env vars**: If the Searcher uses an external API (SerpAPI, Adzuna, etc.), add optional settings to `Settings` and document in `.env.example`, e.g. `SERPAPI_KEY=`, `ADZUNA_APP_ID=`, `ADZUNA_APP_KEY=`. If keys are missing and the Searcher needs them, return an empty list and log a warning (or document that the feature is no-op without keys).
- **README**: Add a short "Job discovery" section: users can search by role/location/keywords, get a list of candidate jobs, select which to process, and run the existing pipeline on the selected URLs.

## Success criteria

- **Searcher** returns a list of job candidates (each with `url`, `title`, and optional `snippet`/`source`) from at least one source (API, search, or stub).
- **Workflow** exposes `find_jobs(criteria, top_k)` that returns candidates (filtered if Filter is implemented).
- **UI** lets the user enter criteria, run a search, see results, select a subset, and process those URLs with the existing `process_job_links` flow.
- Existing behavior (pasting URLs in Process Jobs and processing them) is unchanged.
- New env vars (if any) are documented; missing keys do not crash the app.
