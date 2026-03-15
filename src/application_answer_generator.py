"""Application question answer generator using Evidence and Style RAG."""
import logging
import time
from typing import Any
from typing import List

from openai import OpenAI

from src.config import settings
from src.database import Job
from src.database import Requirement
from src.prompt_loader import load_prompt
from src.evidence_rag import EvidenceRAG
from src.prompt_helpers import build_evidence_context_brief
from src.prompt_helpers import format_requirements
from src.style_rag import StyleRAG

logger = logging.getLogger(__name__)


class ApplicationAnswerGenerator:
    """Generates answers to job application questions (e.g. "Why do you want to work here?")."""

    def __init__(self, evidence_rag: EvidenceRAG, style_rag: StyleRAG):
        self.evidence_rag = evidence_rag
        self.style_rag = style_rag
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def generate(
        self,
        job: Job,
        requirements: List[Requirement],
        evidence_map: dict[int, List[dict[str, Any]]],
        question: str,
    ) -> str:
        """
        Generate an answer to an application question.

        Args:
            job: Job object
            requirements: List of Requirement objects
            evidence_map: Dict mapping requirement_id -> evidence matches
            question: The application question to answer

        Returns:
            Plain-text answer
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")

        t0 = time.perf_counter()
        job_context = job.url or "Job"
        logger.info("ApplicationAnswerGenerator.generate: retrieving style examples")
        style_examples = self.style_rag.retrieve_style_examples(job_context, top_k=settings.top_k_style)
        evidence_context = build_evidence_context_brief(requirements, evidence_map)
        style_context = "\n\n".join([ex["content"] for ex in style_examples]) if style_examples else ""

        style_display = style_context or "(Use professional, concise tone.)"
        prompt = load_prompt("application_answer_user").format(
            job_url=job.url or "Job",
            question=question,
            requirements_formatted=format_requirements(requirements),
            evidence_context=evidence_context,
            style_context=style_display,
        )

        logger.info("ApplicationAnswerGenerator.generate: calling LLM")
        response = self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": load_prompt("application_answer_system")},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6
        )
        logger.info("ApplicationAnswerGenerator.generate: done in %.2fs", time.perf_counter() - t0)
        return response.choices[0].message.content or ""
