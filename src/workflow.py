"""Workflow orchestration."""
from sqlalchemy.orm import Session
from typing import List, Dict
from src.database import Job, Requirement, EditPack, get_db
from src.job_fetcher import JobFetcher
from src.requirement_extractor import RequirementExtractor
from src.evidence_rag import EvidenceRAG
from src.style_rag import StyleRAG
from src.edit_pack_generator import EditPackGenerator
from src.cover_letter_generator import CoverLetterGenerator
from src.application_answer_generator import ApplicationAnswerGenerator


class Workflow:
    """Main workflow orchestrator."""
    
    def __init__(self, db: Session):
        self.db = db
        self.requirement_extractor = RequirementExtractor()
        self.evidence_rag = EvidenceRAG(db)
        self.style_rag = StyleRAG(db)
        self.edit_pack_generator = EditPackGenerator(self.evidence_rag, self.style_rag)
        self.cover_letter_generator = CoverLetterGenerator(self.evidence_rag, self.style_rag)
        self.application_answer_generator = ApplicationAnswerGenerator(self.evidence_rag, self.style_rag)

    def generate_cover_letter(self, job_id: int) -> str:
        """
        Generate a cover letter for a job (on demand). Uses job requirements and evidence RAG.
        """
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        requirements = self.db.query(Requirement).filter(Requirement.job_id == job_id).all()
        evidence_map = self.evidence_rag.match_requirements(requirements)
        return self.cover_letter_generator.generate(job, requirements, evidence_map)

    def approve_cover_letter(self, job_id: int, content: str):
        """Add edited cover letter to Style RAG as a style example."""
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        metadata = {
            "type": "cover_letter",
            "job_title": job.title,
        }
        self.style_rag.add_style_example(content, metadata)

    def generate_application_answer(self, job_id: int, question: str) -> str:
        """Generate an answer to a job application question (on demand)."""
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        requirements = self.db.query(Requirement).filter(Requirement.job_id == job_id).all()
        evidence_map = self.evidence_rag.match_requirements(requirements)
        return self.application_answer_generator.generate(job, requirements, evidence_map, question)

    def approve_application_answer(self, job_id: int, question: str, content: str):
        """Add edited application answer to Style RAG as a style example."""
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        metadata = {
            "type": "application_answer",
            "job_title": job.title,
            "question": question[:500] if question else "",
        }
        self.style_rag.add_style_example(content, metadata)

    def process_job_links(self, urls: List[str], role_tags: List[str] = None) -> List[Dict]:
        """
        Process job posting links.
        
        Args:
            urls: List of job posting URLs
            role_tags: Optional role tags for categorization
            
        Returns:
            List of job processing results
        """
        results = []
        
        with JobFetcher() as fetcher:
            for url in urls:
                try:
                    result = self._process_single_job(url, fetcher, role_tags)
                    results.append(result)
                except Exception as e:
                    self.db.rollback()
                    results.append({
                        "url": url,
                        "status": "error",
                        "error": str(e)
                    })
        
        return results
    
    def _process_single_job(self, url: str, fetcher: JobFetcher, role_tags: List[str] = None) -> Dict:
        """Process a single job posting."""
        # Step 1: Check if job already exists
        existing_job = self.db.query(Job).filter(Job.url == url).first()
        if existing_job:
            return {
                "url": url,
                "status": "exists",
                "job_id": existing_job.id
            }
        
        # Step 2: Fetch job posting
        job_data = fetcher.fetch(url)
        
        # Step 3: Store job
        job = Job(
            url=url,
            title=job_data.get("title"),
            raw_text=job_data.get("text"),
            meta_data=job_data.get("metadata", {})
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        # Step 4: Extract requirements
        requirements_obj = self.requirement_extractor.extract(job.raw_text)
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
        evidence_map = self.evidence_rag.match_requirements(requirements)
        
        # Step 6: Calculate fit score
        fit_score, gaps = self.evidence_rag.calculate_fit_score(requirements)
        
        # Step 7: Generate edit pack
        edit_pack_content = self.edit_pack_generator.generate(job, requirements, evidence_map, gaps)
        
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
        
        return {
            "url": url,
            "status": "success",
            "job_id": job.id,
            "edit_pack_id": edit_pack.id,
            "fit_score": fit_score,
            "gaps_count": len(gaps)
        }
    
    def approve_edit_pack(self, edit_pack_id: int, modified_content: str = None):
        """
        Approve edit pack and store in Style RAG.
        
        Args:
            edit_pack_id: ID of edit pack to approve
            modified_content: Optional modified content (if user edited it)
        """
        edit_pack = self.db.query(EditPack).filter(EditPack.id == edit_pack_id).first()
        if not edit_pack:
            raise ValueError(f"Edit pack {edit_pack_id} not found")
        
        # Use modified content if provided, otherwise use original
        content_to_store = modified_content or edit_pack.content
        
        # Store in Style RAG (style_examples.meta_data)
        job = edit_pack.job
        metadata = {
            "type": "resume-edit-pack",
            "job_title": job.title,
            "fit_score": edit_pack.fit_score
        }
        self.style_rag.add_style_example(content_to_store, metadata)
        
        # Mark as approved
        edit_pack.approved = 1
        if modified_content:
            edit_pack.content = modified_content
        self.db.commit()
    
    def get_ranked_jobs(self) -> List[Dict]:
        """Get jobs ranked by fit score (all processed jobs, not just pending)."""
        jobs = self.db.query(Job).join(EditPack).order_by(
            EditPack.fit_score.desc()
        ).all()
        
        results = []
        for job in jobs:
            edit_pack = job.edit_packs[0] if job.edit_packs else None
            results.append({
                "job_id": job.id,
                "title": job.title,
                "url": job.url,
                "fit_score": edit_pack.fit_score if edit_pack else 0.0,
                "gaps": edit_pack.gap_list if edit_pack else [],
                "edit_pack_id": edit_pack.id if edit_pack else None
            })
        
        return results
