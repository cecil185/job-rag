"""Cover letter reviser agent: revises draft using critic feedback and evidence."""
import logging
import time
from typing import Any
from typing import List

from openai import OpenAI

from src.config import settings
from src.database import Job
from src.prompt_loader import load_prompt
from src.database import Requirement

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
        evidence_map: dict[int, List[dict[str, Any]]],
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

        system_prompt = load_prompt("cover_letter_reviser_system")
        user_prompt = load_prompt("cover_letter_reviser_user").format(
            job_url=job.url or "Job",
            requirements_text=requirements_text,
            evidence_context=evidence_context,
            critique=critique,
            draft=draft,
        )

        response = self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
        )
        revised = response.choices[0].message.content or ""
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
        evidence_map: dict[int, List[dict[str, Any]]],
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
