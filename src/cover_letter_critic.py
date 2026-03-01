"""Cover letter critic agent: reviews drafts against job and evidence."""
import logging
import time
from typing import Dict
from typing import List

from openai import OpenAI

from src.config import settings
from src.database import Job
from src.database import Requirement

logger = logging.getLogger(__name__)


class CoverLetterCritic:
    """Reviews a draft cover letter and returns a structured critique."""

    def __init__(self, client: OpenAI = None):
        self.client = client or (
            OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        )

    def critique(
        self,
        draft: str,
        job: Job,
        requirements: List[Requirement],
        evidence_map: Dict[int, List[Dict]],
    ) -> str:
        """
        Critique the draft cover letter against the job and candidate evidence.

        Args:
            draft: The draft cover letter text.
            job: Job object.
            requirements: List of Requirement objects.
            evidence_map: Dict mapping requirement_id -> evidence matches.

        Returns:
            Plain-text structured critique (sections for tone, gaps, repetition, ATS/keywords, structure).
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")

        t0 = time.perf_counter()
        logger.info("CoverLetterCritic.critique: start")

        requirements_text = self._format_requirements(requirements)
        evidence_context = self._build_evidence_context(requirements, evidence_map)

        system_prompt = """You are an expert hiring manager and editor. Your job is to critique this cover letter against the job and the candidate evidence. Be specific and actionable. Output a structured critique with clear sections or bullet points that a reviser can act on."""

        user_prompt = f"""Critique this cover letter draft for the following job.

Job: {job.url or 'Job'}

Key requirements from the posting:
{requirements_text}

Candidate evidence available (proof points the letter could use):
{evidence_context}

---
DRAFT COVER LETTER:
{draft}
---

Provide a structured critique covering:
1. **Tone**: Too generic, too casual, or appropriate?
2. **Gaps**: Which requirements from the job are not addressed or not backed by evidence in the letter?
3. **Repetition**: Any redundant phrases or bullets?
4. **ATS/keywords**: Missing important terms from the job posting that could help pass ATS?
5. **Structure**: Paragraph flow, hook, "why you" evidence, closing.

Output the critique only (no JSON). Use clear section headers or bullets so the reviser can address each point."""

        response = self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        critique = response.choices[0].message.content
        logger.info("CoverLetterCritic.critique: done in %.2fs", time.perf_counter() - t0)
        return critique

    def _format_requirements(self, requirements: List[Requirement]) -> str:
        lines = []
        for req in requirements:
            lines.append(f"- [{req.category}] {req.text}")
        return "\n".join(lines)

    def _build_evidence_context(
        self,
        requirements: List[Requirement],
        evidence_map: Dict[int, List[Dict]],
    ) -> str:
        parts = []
        for req in requirements:
            evidence = evidence_map.get(req.id, [])
            if evidence:
                parts.append(f"\nRe: {req.text}")
                for i, ev in enumerate(evidence, 1):
                    content = ev.get("content", "")[:250]
                    if len(ev.get("content", "")) > 250:
                        content += "..."
                    parts.append(f"  #{i}: {content}")
        return "\n".join(parts) if parts else "No evidence matches yet."
