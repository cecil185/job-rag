# Feature A: Structured Extraction with Confidence, Validation, and Audit Trail

Implement the following changes to improve traceability, correctness, and auditability of the job-rag pipeline. This feature demonstrates domain workflow modeling, context engineering, and guardrails/auditability.

## 1. Requirement extraction: confidence and validation

### 1.1 Per-requirement confidence

- Extend the requirement extractor so that each extracted requirement has a **confidence score** in the range [0, 1].
- Options for obtaining confidence:
  - Add a separate small LLM call that scores each requirement (e.g. “How confident are you that this is a real requirement from the posting?”), or
  - Use a single structured response that includes both requirement text and confidence per item.
- Prefer a single structured response if token usage is a concern (e.g. extend the existing JSON schema to include `confidence` per item).

### 1.2 Validation against source text

- For each extracted requirement, add a **validation** step that checks whether the requirement (or its key phrases) appears in the original job `raw_text`.
- Validation should be:
  - Heuristic: e.g. requirement text or normalized substring appears in `raw_text` (case-insensitive, optional fuzzy match), or
  - LLM-based: “Does the following requirement appear in this job posting?” with yes/no or confidence.
- Persist a **validation result** per requirement (e.g. `validated: bool` and optionally `raw_snippet: str` — a short excerpt from `raw_text` that supports the requirement).

### 1.3 Persistence

- Extend the `Requirement` model (or add a related table) to store:
  - `confidence` (float, nullable if you need backward compatibility),
  - `validated` (bool),
  - `raw_snippet` (optional string, or JSON field for multiple snippets).
- Ensure existing code paths that create `Requirement` rows are updated to set these fields from the extractor output.
- If you add a new table (e.g. `extraction_runs`), link requirements to the run and store run-level metadata (e.g. `job_id`, `created_at`) for audit.

## 2. Audit log

### 2.1 Audit log table

- Add an **audit_log** table (or equivalent) with at least:
  - `id` (primary key),
  - `entity_type` (e.g. `"job"`, `"edit_pack"`, `"extraction_run"`),
  - `entity_id` (e.g. job id, edit_pack id),
  - `action` (e.g. `"extraction_run"`, `"edit_pack_approved"`, `"edit_pack_rejected"`),
  - `actor` (string; can be `"system"` or a placeholder like `"user"` until auth exists),
  - `at` (timestamp, UTC),
  - `payload` (JSON; optional details such as rejection reason, confidence summary, etc.).

### 2.2 Where to write audit events

- **Extraction:** After a job’s requirements are extracted and stored, write an audit event: `entity_type="job"` (or `"extraction_run"` if you have that), `entity_id=job_id`, `action="extraction_run"`, `payload` containing e.g. number of requirements, mean confidence, counts of validated vs not.
- **Edit pack approved:** In the workflow (or service) that approves an edit pack, after updating the edit pack and committing:
  - Set `EditPack.approved_at` to the current UTC timestamp (this column already exists but is not currently set).
  - Write an audit event: `entity_type="edit_pack"`, `entity_id=edit_pack_id`, `action="edit_pack_approved"`, `at=now`, optional `payload` (e.g. whether content was modified).
- **Edit pack rejected:** When the user rejects an edit pack (e.g. sets `approved=-1`), write an audit event: `action="edit_pack_rejected"`, same entity fields; optionally store a rejection reason in `payload` if you add a UI field for it later.

### 2.3 Schema and migrations

- Prefer database migrations (e.g. Alembic) for new columns and the audit_log table. If the project does not yet have migrations, add the table and columns via a migration script or `init_db` and document how to apply it.

## 3. Backward compatibility and config

- Existing jobs/requirements without confidence or validation should still work: use nullable fields and treat `None` as “unknown” in the UI or downstream.
- Consider a config flag or env var to disable validation (e.g. for speed in dev) if validation is expensive.

## 4. Acceptance criteria

- [ ] Each extracted requirement has a confidence score and a validation result (and optionally raw_snippet) stored in the DB.
- [ ] An audit_log table exists and receives events for extraction_run, edit_pack_approved, and edit_pack_rejected.
- [ ] `EditPack.approved_at` is set when an edit pack is approved.
- [ ] No breaking changes to existing APIs or UI; new fields can be shown in the UI later in a follow-up.

## 5. Files to touch (suggested)

- `src/requirement_extractor.py` — extend response schema and logic; add validation step.
- `src/database.py` — add/alter models: Requirement (confidence, validated, raw_snippet), AuditLog (or equivalent).
- `src/workflow.py` — after extraction, write extraction audit event; in `approve_edit_pack` set `approved_at` and write approved event; in reject path (or wherever approved=-1 is set) write rejected event.
- Migration or init_db — create audit_log table and new columns.
- Optional: small `src/audit.py` helper to write audit events and keep workflow code clean.

Run your code to test that it works.