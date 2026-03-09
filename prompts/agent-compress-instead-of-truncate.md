# Agent prompt: Compress long inputs instead of truncating

## Goal

Replace naive truncation (e.g. `job_text[:8000]`, `ev['content'][:250]`) with compression strategies so we stay within token limits without losing important content. Prefer summarization, section extraction, or relevance-based selection over cutting text at a character index.

## Codebase context

- **Requirement extractor** (`src/requirement_extractor.py`): currently sends `job_text[:8000]` to the LLM. Long postings lose the tail (often qualifications/requirements).
- **Evidence in generators** (`cover_letter_generator.py`, `application_answer_generator.py`): each evidence chunk is capped at 250 chars. **Edit pack** (`edit_pack_generator.py`): evidence content capped at 600 chars per chunk.
- **RAG**: `EvidenceRAG` and `StyleRAG` already do retrieval; the issue is post-retrieval truncation when building the prompt string.

## Your tasks

1. **Job posting (requirement extractor)**  
   - Add a **preprocessing step** before the main extraction call. It must produce a shortened version of the job posting that fits the token budget while preserving requirements, responsibilities, skills, and keywords.  
   - Allowed approaches (pick one or combine):  
     - **Section extraction**: Parse the raw job text for common section headers (e.g. "Responsibilities", "Qualifications", "Requirements", "What you'll do", "About the role") and concatenate only those sections (with a fallback to full text if no headers found).  
     - **Summarization**: One LLM call that takes the full job text and returns a condensed version containing only: role summary, responsibilities, qualifications/requirements, and key skills/keywords. Pass that summary into the existing requirement-extractor prompt instead of raw `job_text`.  
     - **Chunk + select**: Split job text by paragraphs or sections, score or filter chunks for relevance to "requirements and qualifications", then concatenate only the top chunks up to a token limit.  
   - Do **not** keep a simple `job_text[:N]` as the only strategy. Either remove it or use it only as fallback when preprocessing fails or returns empty.  
   - Preserve the existing `RequirementExtractor.extract(job_text)` interface: input is still full `job_text`; preprocessing is internal.

2. **Evidence chunks (cover letter, application answer, edit pack)**  
   - Replace fixed character truncation (250 / 600) with a clearer strategy. Options:  
     - **Token-aware cap**: Truncate by approximate token count (e.g. 4 chars per token) so we respect a token budget per chunk and per prompt.  
     - **Merge/summarize per requirement**: For each requirement, if there are multiple evidence chunks, optionally merge consecutive ones or summarize them into one short paragraph so we need fewer chunks and less truncation.  
     - **Prioritize**: Cap total evidence context by token budget; when over budget, drop lowest-similarity chunks first instead of truncating each chunk in the middle.  
   - Document the chosen strategy in code (comment or docstring) and ensure the prompt still receives coherent, citation-friendly evidence (no mid-sentence cuts if avoidable).

3. **Implementation requirements**  
   - Reuse existing config (e.g. `settings.llm_model`) and logging patterns.  
   - No new dependencies unless necessary (e.g. a tokenizer); prefer simple heuristics or one extra LLM call for summarization.  
   - Add minimal unit tests or integration tests for the new preprocessing so we don’t regress (e.g. short job text unchanged, long job text compressed and still parseable by the extractor).

## Success criteria

- Requirement extractor never relies on `job_text[:8000]` as the primary path; long postings are compressed by structure or summarization.  
- Evidence in prompts is bounded by token budget or relevance, not by arbitrary character limits that cut sentences.  
- Existing behavior for short inputs is unchanged; only long inputs are handled differently.

## Out of scope

- Changing the structure of the final JSON from the requirement extractor.  
- Modifying RAG retrieval logic (e.g. `EvidenceRAG.retrieve` or `match_requirements`); only how retrieved text is formatted and truncated for the prompt.
