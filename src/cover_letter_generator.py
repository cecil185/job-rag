"""Cover letter generator using Evidence and Style RAG."""
import logging
import time
from typing import Dict
from typing import List

from openai import OpenAI

from src.config import settings
from src.database import Job
from src.database import Requirement
from src.evidence_rag import EvidenceRAG
from src.style_rag import StyleRAG

logger = logging.getLogger(__name__)


class CoverLetterGenerator:
    """Generates cover letters tailored to a job with evidence-backed content."""

    def __init__(self, evidence_rag: EvidenceRAG, style_rag: StyleRAG):
        self.evidence_rag = evidence_rag
        self.style_rag = style_rag
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def generate(self, job: Job, requirements: List[Requirement], evidence_map: Dict[int, List[Dict]]) -> str:
        """
        Generate a cover letter for the job.

        Args:
            job: Job object
            requirements: List of Requirement objects
            evidence_map: Dict mapping requirement_id -> evidence matches

        Returns:
            Plain-text or markdown cover letter
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")

        t0 = time.perf_counter()
        job_context = job.url or "Job"
        logger.info("CoverLetterGenerator.generate: retrieving style examples")
        style_examples = self.style_rag.retrieve_style_examples(job_context, top_k=3)
        evidence_context = self._build_evidence_context(requirements, evidence_map)
        style_context = "\n\n".join([ex["content"] for ex in style_examples]) if style_examples else ""

        prompt = f"""Write a professional cover letter for this job application.

Job: {job.url or 'Job'}

Key requirements from the posting:
{self._format_requirements(requirements)}

Candidate evidence (proof points from resume/projects to weave in):
{evidence_context}

Tone/style reference (match this voice where appropriate):
{style_context or "(No style examples yet; use professional, concise tone.)"}

Instructions:
- 3–4 short paragraphs: hook, why them, why you (with specific evidence), closing
- Weave in concrete proof points from the evidence above; do not make unsupported claims
- Match the role language where it fits
- Stay focused - talk about only 1 project per paragraph - 1-3 projects in total.
- Output the letter only (no meta commentary). No greeting or sign off."""

        logger.info("CoverLetterGenerator.generate: calling LLM")
        response = self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You are an expert cover letter writer. Ground every claim in the evidence provided. Be specific and professional."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6
        )
        logger.info("CoverLetterGenerator.generate: done in %.2fs", time.perf_counter() - t0)
        return response.choices[0].message.content

    def _format_requirements(self, requirements: List[Requirement]) -> str:
        lines = []
        for req in requirements:
            lines.append(f"- [{req.category}] {req.text}")
        return "\n".join(lines)

    def _build_evidence_context(self, requirements: List[Requirement], evidence_map: Dict[int, List[Dict]]) -> str:
        context_parts = []
        for req in requirements:
            evidence = evidence_map.get(req.id, [])
            if evidence:
                context_parts.append(f"\nRe: {req.text}")
                for i, ev in enumerate(evidence, 1):
                    context_parts.append(f"  #{i}: {ev['content'][:250]}{'...' if len(ev.get('content','')) > 250 else ''}")
        return "\n".join(context_parts) if context_parts else "No evidence matches yet."
