"""Workflow orchestration."""
import logging
import time
from typing import Any
from typing import List
from typing import Optional

from sqlalchemy.orm import Session

from src.application_answer_generator import ApplicationAnswerGenerator
from src.cover_letter_critic import CoverLetterCritic
from src.cover_letter_generator import CoverLetterGenerator
from src.cover_letter_reviser import CoverLetterReviser
from src.database import EditPack
from src.database import get_db
from src.database import Job
from src.database import Requirement
from src.edit_pack_generator import EditPackGenerator
from src.evidence_rag import EvidenceRAG
from src.job_fetcher import JobFetcher
from src.requirement_extractor import RequirementExtractor
from src.style_rag import StyleRAG

logger = logging.getLogger(__name__)


class Workflow:
    """Main workflow orchestrator."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.requirement_extractor = RequirementExtractor()
        self.evidence_rag = EvidenceRAG(db)
        self.style_rag = StyleRAG(db)
        self.edit_pack_generator = EditPackGenerator(self.evidence_rag, self.style_rag)
        self.cover_letter_generator = CoverLetterGenerator(self.evidence_rag, self.style_rag)
        self.cover_letter_critic = CoverLetterCritic()
        self.cover_letter_reviser = CoverLetterReviser()
        self.application_answer_generator = ApplicationAnswerGenerator(self.evidence_rag, self.style_rag)

    def generate_cover_letter_with_revision(self, job_id: int) -> dict[str, Any]:
        """
        Generate draft, run critic, then reviser; return draft, critique, and revised letter.
        """
        t0 = time.perf_counter()
        logger.info("generate_cover_letter_with_revision: job_id=%s start", job_id)
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        requirements = self.db.query(Requirement).filter(Requirement.job_id == job_id).all()
        evidence_map = self.evidence_rag.match_requirements(requirements)
        draft = self.cover_letter_generator.generate(job, requirements, evidence_map)
        critique = self.cover_letter_critic.critique(draft, job, requirements, evidence_map)
        revised = self.cover_letter_reviser.revise(draft, critique, job, requirements, evidence_map)
        logger.info(
            "generate_cover_letter_with_revision: job_id=%s done in %.2fs",
            job_id,
            time.perf_counter() - t0,
        )
        return {"draft": draft, "critique": critique, "revised": revised}

    def approve_cover_letter(self, job_id: int, content: str) -> None:
        """Add edited cover letter to Style RAG as a style example."""
        t0 = time.perf_counter()
        logger.info("approve_cover_letter: job_id=%s start", job_id)
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        metadata = {
            "type": "cover_letter",
            "job_url": job.url,
        }
        self.style_rag.add_style_example_chunked(content, metadata)
        logger.info("approve_cover_letter: job_id=%s done in %.2fs", job_id, time.perf_counter() - t0)

    def generate_application_answer(self, job_id: int, question: str) -> str:
        """Generate an answer to a job application question (on demand)."""
        t0 = time.perf_counter()
        logger.info("generate_application_answer: job_id=%s start", job_id)
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        requirements = self.db.query(Requirement).filter(Requirement.job_id == job_id).all()
        evidence_map = self.evidence_rag.match_requirements(requirements)
        answer = self.application_answer_generator.generate(job, requirements, evidence_map, question)
        logger.info("generate_application_answer: job_id=%s done in %.2fs", job_id, time.perf_counter() - t0)
        return answer

    def approve_application_answer(self, job_id: int, question: str, content: str) -> None:
        """Add edited application answer to Style RAG as a style example."""
        t0 = time.perf_counter()
        logger.info("approve_application_answer: job_id=%s start", job_id)
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        metadata = {
            "type": "application_answer",
            "job_url": job.url,
            "question": question[:500] if question else "",
        }
        self.style_rag.add_style_example_chunked(content, metadata)
        logger.info("approve_application_answer: job_id=%s done in %.2fs", job_id, time.perf_counter() - t0)

    def process_job_links(
        self,
        urls: List[str],
        role_tags: Optional[List[str]] = None,
        raw_text_override: Optional[str] = None,
    ) -> List[dict[str, Any]]:
        """
        Process job posting links.

        Args:
            urls: List of job posting URLs
            role_tags: Optional role tags for categorization
            raw_text_override: If provided, used for the first URL and that URL is not fetched.

        Returns:
            List of job processing results
        """
        results = []
        t0 = time.perf_counter()
        logger.info("process_job_links: %d URLs, raw_text_override=%s", len(urls), bool(raw_text_override))

        raw_override = (raw_text_override.strip() if raw_text_override and raw_text_override.strip() else None)
        with JobFetcher() as fetcher:
            for i, url in enumerate(urls):
                try:
                    raw_for_this = (raw_override if i == 0 else None)
                    result = self._process_single_job(url, fetcher, role_tags, raw_text=raw_for_this)
                    results.append(result)
                except Exception as e:
                    self.db.rollback()
                    results.append({
                        "url": url,
                        "status": "error",
                        "error": str(e)
                    })

        logger.info("process_job_links: done in %.2fs, %d results", time.perf_counter() - t0, len(results))
        return results

    def _process_single_job(
        self,
        url: str,
        fetcher: JobFetcher,
        role_tags: Optional[List[str]] = None,
        raw_text: Optional[str] = None,
    ) -> dict[str, Any]:
        """Process a single job posting. If raw_text is provided, skip fetching the URL and use it."""
        t0 = time.perf_counter()
        logger.info("_process_single_job: url=%s start, raw_text=%s", url[:60], bool(raw_text))

        # Step 1: Check if job already exists
        existing_job = self.db.query(Job).filter(Job.url == url).first()
        if existing_job:
            logger.info("_process_single_job: url=%s exists, skip in %.2fs", url[:60], time.perf_counter() - t0)
            return {
                "url": url,
                "status": "exists",
                "job_id": existing_job.id
            }

        # Step 2: Fetch job posting or use provided raw_text
        if raw_text is not None:
            job_data = {"text": raw_text, "metadata": {}}
            logger.info("_process_single_job: using provided raw_text (skip fetch)")
        else:
            t_fetch = time.perf_counter()
            job_data = fetcher.fetch(url)
            logger.info("_process_single_job: fetch done in %.2fs", time.perf_counter() - t_fetch)

        # Step 3: Store job
        job = Job(
            url=url,
            raw_text=job_data.get("text"),
            meta_data=job_data.get("metadata", {})
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        # Step 4: Extract requirements (raw_text must be non-empty for LLM)
        if not (job.raw_text and job.raw_text.strip()):
            raise ValueError("Job raw_text is empty; cannot extract requirements.")
        t_extract = time.perf_counter()
        try:
            requirements_obj = self.requirement_extractor.extract(job.raw_text)
        except ValueError as e:
            if "max token limit" in str(e) or "MAX_PROMPT_TOKENS" in str(e):
                self.db.delete(job)
                self.db.commit()
                logger.warning("_process_single_job: deleted job id=%s due to token limit", job.id)
            raise
        logger.info("_process_single_job: requirement_extractor.extract done in %.2fs", time.perf_counter() - t_extract)
        requirements = []

        for req_item in requirements_obj.to_requirement_items():
            req = Requirement(
                job_id=job.id,
                category=req_item.category,
                text=req_item.text,
                priority=req_item.priority
            )
            self.db.add(req)
            requirements.append(req)

        self.db.commit()
        for req in requirements:
            self.db.refresh(req)

        # Step 5: Evidence RAG retrieval
        t_evidence = time.perf_counter()
        evidence_map = self.evidence_rag.match_requirements(requirements)
        logger.info("_process_single_job: evidence_rag.match_requirements done in %.2fs", time.perf_counter() - t_evidence)

        # Step 6: Calculate fit score
        t_fit = time.perf_counter()
        fit_score, gaps = self.evidence_rag.calculate_fit_score(requirements)
        logger.info("_process_single_job: calculate_fit_score done in %.2fs", time.perf_counter() - t_fit)

        # Step 7: Generate edit pack
        t_edit = time.perf_counter()
        edit_pack_content = self.edit_pack_generator.generate(job, requirements, evidence_map, gaps)
        logger.info("_process_single_job: edit_pack_generator.generate done in %.2fs", time.perf_counter() - t_edit)

        # Step 8: Store edit pack
        edit_pack = EditPack(
            job_id=job.id,
            content=edit_pack_content,
            fit_score=fit_score,
            gap_list=gaps,
            approved=0
        )
        self.db.add(edit_pack)
        self.db.commit()
        self.db.refresh(edit_pack)

        logger.info("_process_single_job: url=%s done in %.2fs total", url[:60], time.perf_counter() - t0)
        return {
            "url": url,
            "status": "success",
            "job_id": job.id,
            "edit_pack_id": edit_pack.id,
            "fit_score": fit_score,
            "gaps_count": len(gaps)
        }

    def approve_edit_pack(
        self, edit_pack_id: int, modified_content: Optional[str] = None
    ) -> None:
        """
        Approve edit pack and store in Style RAG.

        Args:
            edit_pack_id: ID of edit pack to approve
            modified_content: Optional modified content (if user edited it)
        """
        t0 = time.perf_counter()
        logger.info("approve_edit_pack: edit_pack_id=%s start", edit_pack_id)
        edit_pack = self.db.query(EditPack).filter(EditPack.id == edit_pack_id).first()
        if not edit_pack:
            raise ValueError(f"Edit pack {edit_pack_id} not found")

        # Use modified content if provided, otherwise use original
        content_to_store = modified_content or edit_pack.content

        # Store in Style RAG (style_examples.meta_data)
        job = edit_pack.job
        metadata = {
            "type": "resume-edit-pack",
            "job_url": job.url,
            "fit_score": edit_pack.fit_score
        }
        self.style_rag.add_style_example_chunked(content_to_store, metadata)

        # Mark as approved
        edit_pack.approved = 1
        if modified_content:
            edit_pack.content = modified_content
        self.db.commit()
        logger.info("approve_edit_pack: edit_pack_id=%s done in %.2fs", edit_pack_id, time.perf_counter() - t0)

    def get_ranked_jobs(self) -> List[dict[str, Any]]:
        """Get jobs ranked by fit score (all processed jobs, not just pending)."""
        t0 = time.perf_counter()
        jobs = self.db.query(Job).join(EditPack).order_by(
            EditPack.fit_score.desc()
        ).all()
        logger.info("get_ranked_jobs: query done in %.2fs, %d jobs", time.perf_counter() - t0, len(jobs))

        results = []
        for job in jobs:
            edit_pack = job.edit_packs[0] if job.edit_packs else None
            results.append({
                "job_id": job.id,
                "url": job.url,
                "fit_score": edit_pack.fit_score if edit_pack else 0.0,
                "gaps": edit_pack.gap_list if edit_pack else [],
                "edit_pack_id": edit_pack.id if edit_pack else None
            })

        return results
