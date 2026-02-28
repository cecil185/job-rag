"""Cover letter reviser agent: revises draft using critic feedback and evidence."""
import logging
import time
from typing import List, Dict
from openai import OpenAI
from src.database import Job, Requirement
from src.config import settings

logger = logging.getLogger(__name__)


class CoverLetterReviser:
    """Revises a cover letter draft using the critic's feedback and candidate evidence."""

    def __init__(self, client: OpenAI = None):
        self.client = client or (
            OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        )

    def revise(
        self,
        draft: str,
        critique: str,
        job: Job,
        requirements: List[Requirement],
        evidence_map: Dict[int, List[Dict]],
    ) -> str:
        """
        Revise the draft to address the critique. Preserves voice; only uses provided evidence.

        Args:
            draft: Original draft cover letter.
            critique: Critique string from CoverLetterCritic.
            job: Job object.
            requirements: List of Requirement objects.
            evidence_map: Dict mapping requirement_id -> evidence matches.

        Returns:
            Full revised cover letter (plain text).
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")

        t0 = time.perf_counter()
        logger.info("CoverLetterReviser.revise: start")

        requirements_text = self._format_requirements(requirements)
        evidence_context = self._build_evidence_context(requirements, evidence_map)

        system_prompt = """You are an expert editor. Revise this cover letter to address the critic's feedback. Do not add unsupported claims; only use the job requirements and candidate evidence provided. Preserve the candidate's voice. Output the full revised letter only (no meta commentary, no greeting or sign-off)."""

        user_prompt = f"""Revise the following cover letter to address the critic's feedback.

Job: {job.url or 'Job'}

Key requirements:
{requirements_text}

Candidate evidence you may use (do not invent facts):
{evidence_context}

---
CRITIQUE:
{critique}
---

---
ORIGINAL DRAFT:
{draft}
---

Instructions:
- Address each point in the critique where possible using only the evidence above.
- Keep 3–4 short paragraphs: hook, why them, why you (with specific evidence), closing.
- Do not add claims not supported by the job or evidence.
- Output the revised letter only (no greeting or sign off)."""

        response = self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
        )
        revised = response.choices[0].message.content
        logger.info("CoverLetterReviser.revise: done in %.2fs", time.perf_counter() - t0)
        return revised

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
