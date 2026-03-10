"""Cover letter generator using Evidence and Style RAG."""
import logging
import time
from typing import Any
from typing import List

from openai import OpenAI

from src.config import settings
from src.database import Job
from src.prompt_loader import load_prompt
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

    def generate(
        self,
        job: Job,
        requirements: List[Requirement],
        evidence_map: dict[int, List[dict[str, Any]]],
    ) -> str:
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

        style_display = style_context or "(No style examples yet; use professional, concise tone.)"
        prompt = load_prompt("cover_letter_user").format(
            job_url=job.url or "Job",
            requirements_formatted=self._format_requirements(requirements),
            evidence_context=evidence_context,
            style_context=style_display,
        )

        logger.info("CoverLetterGenerator.generate: calling LLM")
        response = self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": load_prompt("cover_letter_system")},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6
        )
        logger.info("CoverLetterGenerator.generate: done in %.2fs", time.perf_counter() - t0)
        return response.choices[0].message.content or ""

    def _format_requirements(self, requirements: List[Requirement]) -> str:
        lines = []
        for req in requirements:
            lines.append(f"- [{req.category}] {req.text}")
        return "\n".join(lines)

    def _build_evidence_context(
        self,
        requirements: List[Requirement],
        evidence_map: dict[int, List[dict[str, Any]]],
    ) -> str:
        context_parts = []
        for req in requirements:
            evidence = evidence_map.get(req.id, [])
            if evidence:
                context_parts.append(f"\nRe: {req.text}")
                for i, ev in enumerate(evidence, 1):
                    context_parts.append(f"  #{i}: {ev['content'][:250]}{'...' if len(ev.get('content','')) > 250 else ''}")
        return "\n".join(context_parts) if context_parts else "No evidence matches yet."
