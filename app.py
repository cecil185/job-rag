"""Streamlit UI for Job RAG."""
import io
import logging
import sys

import streamlit as st
from sqlalchemy.orm import Session

from scripts.pdf_to_txt import pdf_to_text
from sqlalchemy.orm import joinedload

from src.database import EditPack
from src.database import get_db
from src.database import init_db
from src.database import Job
from src.evidence_rag import EvidenceRAG
from src.workflow import Workflow

# Configure logging so INFO shows where time is spent
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Job RAG - Resume Editor", layout="wide")

# Initialize session state
if "workflow" not in st.session_state:
    logger.info("Creating workflow and db session")
    db = next(get_db())
    st.session_state.workflow = Workflow(db)
    st.session_state.db = db

if "evidence_rag" not in st.session_state:
    logger.info("Creating EvidenceRAG")
    st.session_state.evidence_rag = EvidenceRAG(st.session_state.db)

st.session_state.setdefault("failed_extractions", [])
st.session_state.setdefault("last_role_tags", [])


def main():
    # Clear any aborted transaction from a previous failed query so the session is usable
    try:
        st.session_state.db.rollback()
    except Exception:
        pass

    st.title("🎯 Job RAG - Resume Editor")
    st.markdown("Tailor your resume to job postings using Evidence RAG and Style RAG")

    # Sidebar for evidence management
    with st.sidebar:
        st.header("📚 Evidence Management")

        st.subheader("Add Evidence")
        evidence_id = st.text_input("Source ID", placeholder="e.g., resume, linkedin", key="evidence_source_id")
        is_resume = st.checkbox("Resume (replaces previous resume)", value=False, help="Check if this is your base resume. Uploading a new resume replaces the old one in the system.")

        # File upload option
        uploaded_file = st.file_uploader("Upload a file", type=["txt", "md", "pdf"], help="Upload a text, markdown, or PDF file with your resume/project content")

        if uploaded_file is not None:
            if uploaded_file.type == "application/pdf":
                try:
                    evidence_text = pdf_to_text(io.BytesIO(uploaded_file.getvalue()))
                except Exception as e:
                    st.error(f"Failed to extract text from PDF: {e}")
                    evidence_text = ""
            else:
                evidence_text = uploaded_file.read().decode("utf-8")
            if evidence_text:
                st.text_area("Preview uploaded content", evidence_text, height=150, disabled=True)
        else:
            evidence_text = st.text_area("Or Paste Text", height=200, placeholder="Paste your resume bullets, project descriptions, or brag-doc entries here...\n\nYou can paste multiple items at once - the system will automatically chunk them.")

        if st.button("Add Evidence", type="primary"):
            if not evidence_id or not evidence_id.strip():
                st.error("Please enter a Source ID")
            elif evidence_text:
                with st.spinner("Processing and storing evidence..."):
                    logger.info("Adding evidence (source_id=%s, is_resume=%s)", evidence_id.strip(), is_resume)
                    st.session_state.evidence_rag.add_evidence(
                        evidence_text,
                        evidence_id.strip(),
                        is_resume=is_resume
                    )
                    logger.info("Evidence added successfully")
                st.success("✓ Evidence added!")
                st.info(f"Your content has been chunked and stored in the Evidence RAG database.")
            else:
                st.error("Please enter evidence text or upload a file")

        st.divider()

        st.subheader("Database Status")
        job_count = st.session_state.db.query(Job).count()
        edit_pack_count = st.session_state.db.query(EditPack).filter(EditPack.approved == 0).count()
        st.metric("Jobs Processed", job_count)
        st.metric("Pending Edit Packs", edit_pack_count)

    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📥 Process Jobs", "📊 Ranked Jobs", "✅ Review Edit Packs", "⚠️ Could not extract", "🔍 Search Jobs"
    ])

    with tab1:
        st.header("Process Job Postings")
        st.markdown("Paste job posting URLs to extract requirements and generate edit packs")

        urls_text = st.text_area(
            "Job Posting URLs (one per line)",
            height=120,
            placeholder="https://example.com/job1\nhttps://example.com/job2"
        )

        raw_text_paste = st.text_area(
            "Raw job text (optional)",
            height=200,
            placeholder="Paste raw job posting text here. If provided, this is used for the first URL and the URL is not fetched.",
            help="If you provide text here, it will be used for the first URL above and the app will skip fetching that URL."
        )

        role_tags = st.text_input("Role Tags (optional, comma-separated)")

        if st.button("Process Jobs", type="primary"):
            if urls_text:
                urls = [url.strip() for url in urls_text.split("\n") if url.strip()]
                tags = [tag.strip() for tag in role_tags.split(",")] if role_tags else None
                raw_override = raw_text_paste.strip() if raw_text_paste else None

                with st.spinner("Processing jobs..."):
                    logger.info("Processing %d job URL(s), raw_text_override=%s", len(urls), bool(raw_override))
                    results = st.session_state.workflow.process_job_links(urls, tags, raw_text_override=raw_override)
                    logger.info("Process jobs finished: %d results", len(results))

                success_count = sum(1 for r in results if r.get("status") == "success")
                st.success(f"Processed {success_count} jobs")

                failed = [{"url": r["url"], "error": r.get("error", "")} for r in results if r.get("status") == "error"]
                if failed:
                    st.session_state.failed_extractions = failed
                st.session_state.last_role_tags = tags or []

                for result in results:
                    if result["status"] == "success":
                        st.success(f"✅ {result['url']} - Fit Score: {result['fit_score']:.2%}")
                    elif result["status"] == "exists":
                        st.info(f"ℹ️ {result['url']} - Already processed")
                    else:
                        st.error(f"❌ {result['url']} - Error: {result.get('error', 'Unknown')}")
            else:
                st.warning("Please enter at least one URL")

    with tab2:
        st.header("Ranked Jobs by Evidence Coverage")

        if st.button("Refresh Rankings"):
            st.rerun()

        logger.info("Fetching ranked jobs")
        ranked_jobs = st.session_state.workflow.get_ranked_jobs()
        logger.info("Ranked jobs: %d", len(ranked_jobs) if ranked_jobs else 0)

        if ranked_jobs:
            for i, job in enumerate(ranked_jobs, 1):
                with st.expander(f"#{i} {job['url']} - Fit: {job['fit_score']:.2%}"):
                    st.write(f"**URL:** {job['url']}")
                    st.write(f"**Fit Score:** {job['fit_score']:.2%}")

                    if job.get("requirements"):
                        st.write("**Requirements:**")
                        for req in job["requirements"]:
                            conf = req.get("confidence")
                            conf_str = f" — {conf:.0%}" if conf is not None else ""
                            st.write(f"- {req['text']}{conf_str}")

                    if job['gaps']:
                        st.write("**Gaps:**")
                        for gap in job['gaps']:
                            st.write(f"- {gap}")

                    if job['edit_pack_id']:
                        st.write(f"**Edit Pack ID:** {job['edit_pack_id']}")

                    st.divider()
                    cover_key = f"cover_letter_{job['job_id']}"
                    if "cover_letter_revisions" not in st.session_state:
                        st.session_state.cover_letter_revisions = {}
                    if st.button("📝 Generate cover letter", key=f"btn_cl_rev_{job['job_id']}"):
                        with st.spinner("Generating draft, then critique and revision..."):
                            try:
                                logger.info("Generate with revision for job_id=%s", job["job_id"])
                                result = st.session_state.workflow.generate_cover_letter_with_revision(job["job_id"])
                                st.session_state.cover_letter_revisions[job["job_id"]] = result
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))
                    if job["job_id"] in st.session_state.cover_letter_revisions:
                        rev = st.session_state.cover_letter_revisions[job["job_id"]]
                        with st.expander("📝 Draft"):
                            st.write(rev["draft"])
                        with st.expander("🔍 Critique"):
                            st.write(rev["critique"])
                        st.subheader("Revised cover letter")
                        edited = st.text_area(
                            "Edit revised letter (optional)",
                            value=rev["revised"],
                            height=320,
                            key=cover_key
                        )
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Approve (add to Style RAG)", key=f"cl_approve_{job['job_id']}", type="primary"):
                                try:
                                    st.session_state.workflow.approve_cover_letter(job["job_id"], edited)
                                    del st.session_state.cover_letter_revisions[job["job_id"]]
                                    st.success("Cover letter added to Style RAG!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(str(e))
                        with col2:
                            if st.button("❌ Reject (discard)", key=f"cl_reject_{job['job_id']}"):
                                del st.session_state.cover_letter_revisions[job["job_id"]]
                                st.rerun()

                    st.divider()
                    st.subheader("Application question")
                    app_q_placeholder = "e.g. Why do you want to work here? Tell us about a challenge you solved..."
                    app_question = st.text_area(
                        "Paste the application question",
                        height=80,
                        placeholder=app_q_placeholder,
                        key=f"app_q_{job['job_id']}"
                    )
                    if st.button("📝 Generate answer", key=f"btn_app_{job['job_id']}"):
                        if not (app_question and app_question.strip()):
                            st.error("Please enter a question")
                        else:
                            with st.spinner("Generating answer..."):
                                try:
                                    logger.info("Generating application answer for job_id=%s", job["job_id"])
                                    answer = st.session_state.workflow.generate_application_answer(job["job_id"], app_question.strip())
                                    logger.info("Application answer generated for job_id=%s", job["job_id"])
                                    if "app_answers" not in st.session_state:
                                        st.session_state.app_answers = {}
                                    st.session_state.app_answers[job["job_id"]] = {"question": app_question.strip(), "answer": answer}
                                    st.rerun()
                                except Exception as e:
                                    st.error(str(e))
                    if "app_answers" in st.session_state and job["job_id"] in st.session_state.app_answers:
                        data = st.session_state.app_answers[job["job_id"]]
                        st.write("**Question:** ", data["question"])
                        answer = data["answer"]
                        edited_answer = st.text_area(
                            "Edit response (optional)",
                            value=answer,
                            height=220,
                            key=f"app_ans_{job['job_id']}"
                        )
                        if edited_answer != answer:
                            st.session_state.app_answers[job["job_id"]]["answer"] = edited_answer
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button("✅ Approve (add to Style RAG)", key=f"app_approve_{job['job_id']}", type="primary"):
                                try:
                                    st.session_state.workflow.approve_application_answer(
                                        job["job_id"], data["question"], edited_answer
                                    )
                                    del st.session_state.app_answers[job["job_id"]]
                                    st.success("Answer added to Style RAG!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(str(e))
                        with col_b:
                            if st.button("❌ Reject (discard)", key=f"app_reject_{job['job_id']}"):
                                del st.session_state.app_answers[job["job_id"]]
                                st.rerun()
        else:
            st.info("No jobs processed yet. Process some jobs in the 'Process Jobs' tab.")

    with tab3:
        st.header("Review and Approve Edit Packs")

        # Get pending edit packs
        logger.info("Loading pending edit packs")
        pending_packs = (
            st.session_state.db.query(EditPack)
            .filter(EditPack.approved == 0)
            .join(Job)
            .options(joinedload(EditPack.job).joinedload(Job.requirements))
            .order_by(EditPack.fit_score.desc())
            .all()
        )

        if pending_packs:
            for pack in pending_packs:
                job = pack.job
                with st.expander(f"{job.url} - Fit: {pack.fit_score:.2%}"):
                    st.write(f"**Job URL:** {job.url}")
                    st.write(f"**Fit Score:** {pack.fit_score:.2%}")

                    if pack.job.requirements:
                        st.write("**Requirements:**")
                        for req in pack.job.requirements:
                            conf_str = f" — {req.confidence:.0%}" if req.confidence is not None else ""
                            st.write(f"- {req.text}{conf_str}")

                    if pack.gap_list:
                        st.write("**Gaps:**")
                        for gap in pack.gap_list:
                            st.write(f"- {gap}")

                    st.divider()
                    st.subheader("Edit Pack")

                    # Show edit pack content
                    st.markdown(pack.content)

                    st.divider()

                    # Allow editing
                    edited_content = st.text_area(
                        "Edit Content (optional)",
                        value=pack.content,
                        height=300,
                        key=f"edit_{pack.id}"
                    )

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Approve", key=f"approve_{pack.id}", type="primary"):
                            st.session_state.workflow.approve_edit_pack(
                                pack.id,
                                edited_content if edited_content != pack.content else None
                            )
                            st.success("Edit pack approved and added to Style RAG!")
                            st.rerun()

                    with col2:
                        if st.button("❌ Reject", key=f"reject_{pack.id}"):
                            st.session_state.workflow.reject_edit_pack(pack.id)
                            st.info("Edit pack rejected")
                            st.rerun()
        else:
            st.info("No pending edit packs. Process some jobs first.")

    with tab4:
        st.header("Could not extract")
        st.markdown("Jobs where URL extraction failed. Paste the job text below and retry.")

        failed_extractions = st.session_state.failed_extractions
        if not failed_extractions:
            st.info("No failed extractions. Run Process Jobs and any failures will appear here.")
        else:
            tags = st.session_state.get("last_role_tags") or []
            for i, item in enumerate(failed_extractions):
                url = item["url"]
                error = item.get("error", "")
                with st.expander(f"🔗 {url}", expanded=True):
                    if error:
                        st.caption(f"Error: {error}")
                    pasted = st.text_area(
                        "Paste job requirements / job posting text",
                        height=200,
                        placeholder="Paste the full job posting text here...",
                        key=f"failed_paste_{i}",
                    )
                    if st.button("Process with pasted text", key=f"failed_btn_{i}", type="primary"):
                        if not pasted or not pasted.strip():
                            st.warning("Please paste job text first.")
                        else:
                            with st.spinner("Processing..."):
                                try:
                                    results = st.session_state.workflow.process_job_links(
                                        [url], tags, raw_text_override=pasted.strip()
                                    )
                                    if not results:
                                        st.error("Processing failed: No result returned.")
                                    else:
                                        r = results[0]
                                        status = r.get("status")
                                        if status == "success":
                                            st.session_state.failed_extractions = [
                                                e for e in st.session_state.failed_extractions if e["url"] != url
                                            ]
                                            st.success("Job processed successfully.")
                                            st.rerun()
                                        elif status == "exists":
                                            st.info("This job was already processed.")
                                            st.session_state.failed_extractions = [
                                                e for e in st.session_state.failed_extractions if e["url"] != url
                                            ]
                                            st.rerun()
                                        else:
                                            err = r.get("error") or "Unknown error"
                                            st.error(f"Processing failed: {err}")
                                except Exception as e:
                                    msg = str(e).strip() or repr(e) or "An error occurred"
                                    st.error(f"Processing failed: {msg}")

    with tab5:
        st.header("Search Jobs (Adzuna API)")
        from src.config import settings as app_settings
        if not app_settings.adzuna_app_id or not app_settings.adzuna_app_key:
            st.warning(
                "Adzuna API not configured. Set **ADZUNA_APP_ID** and **ADZUNA_APP_KEY** in `.env` to enable job search."
            )
        else:
            col_q, col_loc = st.columns(2)
            with col_q:
                search_query = st.text_input("Keywords (what)", placeholder="e.g. Python developer")
            with col_loc:
                search_location = st.text_input("Location (where)", placeholder="e.g. London")
            if st.button("Search", type="primary", key="search_jobs_btn"):
                with st.spinner("Searching..."):
                    try:
                        search_results = st.session_state.workflow.search_jobs(
                            query=search_query.strip() or None,
                            location=search_location.strip() or None,
                            page=1,
                        )
                        st.session_state.search_results = search_results
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            if st.session_state.get("search_results"):
                results = st.session_state.search_results
                st.success(f"Found {len(results)} result(s)")
                urls_for_process = []
                for i, r in enumerate(results):
                    with st.expander(f"{r.get('title', 'No title')} — {r.get('company', '')}"):
                        st.write("**Company:**", r.get("company", ""))
                        st.write("**Location:**", r.get("location", ""))
                        url = r.get("url", "")
                        if url:
                            st.write("**URL:**", url)
                            urls_for_process.append(url)
                        if r.get("description"):
                            st.caption(r["description"][:300] + ("..." if len(r.get("description", "")) > 300 else ""))
                if urls_for_process:
                    st.subheader("Use in Process Jobs")
                    st.text_area(
                        "Copy these URLs into the Process Jobs tab",
                        "\n".join(urls_for_process),
                        height=120,
                        key="search_urls_export",
                    )


if __name__ == "__main__":
    main()
