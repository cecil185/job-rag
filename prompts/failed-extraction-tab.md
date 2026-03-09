# Failed Job Extraction Check and "Paste job text" Tab

Add a check for URL job posting extraction success. If extraction fails for any job, show a dedicated tab where the user can paste job requirements and retry.

## Written prompt (spec)

Use this as the implementation spec:

---

**Add a check for URL job posting extraction success. If extraction fails for any job:**

1. **Detection**  
   Treat a job as "extraction failed" when `process_job_links` returns a result with `status == "error"` (fetch/parse exception or empty/invalid text). The backend already returns these in `src/workflow.py` (e.g. exception in `_process_single_job` or empty `raw_text` after fetch).

2. **New tab**  
   Add a fourth tab, e.g. **"Could not extract"** (or "Paste job text"), shown only when there is at least one failed extraction from the last "Process Jobs" run (or persist failed URLs in session state so the tab stays useful across reruns).

3. **Tab content**  
   In that tab, show one row per failed job:
   - **Row contents:** job URL (or label) and a **text box** for "Paste job requirements / job posting text" (multi-line).
   - **Action:** a button per row (e.g. "Process with pasted text") that re-runs processing for that single URL using the pasted text as `raw_text_override` (same as the existing "Raw job text" in `app.py` tab1), so the URL is not fetched again.

4. **Flow**  
   After "Process Jobs" runs, if any result has `status == "error"`, store those `{ url, error }` in session state (e.g. `st.session_state.failed_extractions`). In the new tab, iterate over that list and render URL + text area + "Process with pasted text" for each. On button click, call `workflow.process_job_links([url], role_tags, raw_text_override=pasted_text)` and remove that entry from `failed_extractions` on success (and optionally show success message or rerun).

---

## Implementation outline

- **Backend**  
  No change required. Failed jobs already return `status: "error"` and `error: str` from `src/workflow.py` (`process_job_links` catch block and `_process_single_job` ValueError for empty `raw_text`).

- **Frontend (`app.py`)**  
  - After the "Process Jobs" button block: if any `r.get("status") == "error"`, set `st.session_state.failed_extractions = [{"url": r["url"], "error": r.get("error", "")} for r in results if r.get("status") == "error"]`.
  - Initialize `st.session_state.setdefault("failed_extractions", [])` near other session state init.
  - Add a fourth tab, e.g. `tab1, tab2, tab3, tab4 = st.tabs([..., "Could not extract"])`.
  - In `tab4`: loop over `st.session_state.failed_extractions`; for each item show the URL, the error message (optional), a `st.text_area` for pasted job text (keyed by URL or index), and a "Process with pasted text" button that calls `process_job_links([url], tags, raw_text_override=text_from_area)`, then removes that item from `failed_extractions` and reruns (or shows success).
  - If the list is empty, show a short message like "No failed extractions. Run Process Jobs and any failures will appear here."

- **Edge cases**  
  - Empty paste: disable button or show warning until the text area has content.
  - Same URL processed successfully from this tab: remove it from `failed_extractions` so the tab doesn't keep showing it.

This keeps the existing "one raw text for the first URL" semantics and reuses `process_job_links(..., raw_text_override=...)` for retries.
