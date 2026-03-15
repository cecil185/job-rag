"""Edit pack generator using Evidence and Style RAG."""
import logging
import time
from typing import Any
from typing import List
from typing import Optional

from openai import OpenAI

from src.config import settings
from src.database import Job
from src.database import Requirement
from src.prompt_loader import load_prompt
from src.evidence_rag import EvidenceRAG
from src.prompt_helpers import format_requirements
from src.style_rag import StyleRAG

logger = logging.getLogger(__name__)


class EditPackGenerator:
    """Generates resume edit packs with citations."""

    def __init__(self, evidence_rag: EvidenceRAG, style_rag: StyleRAG):
        self.evidence_rag = evidence_rag
        self.style_rag = style_rag
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def generate(
        self,
        job: Job,
        requirements: List[Requirement],
        evidence_map: dict[int, List[dict[str, Any]]],
        gaps: Optional[List[str]] = None,
    ) -> str:
        """
        Generate edit pack with bullets to add and projects to highlight (no replace section).

        Args:
            job: Job object
            requirements: List of Requirement objects
            evidence_map: Dict mapping requirement_id -> evidence matches
            gaps: Requirement phrases with weak/no evidence; put these words directly in Bullets to Add

        Returns:
            Markdown-formatted edit pack
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")

        t0 = time.perf_counter()
        gaps = gaps or []

        # Get style examples
        job_context = job.url or "Job"
        logger.info("EditPackGenerator.generate: retrieving style examples")
        style_examples = self.style_rag.retrieve_style_examples(job_context, top_k=settings.top_k_style)

        # Build evidence context
        evidence_context = self._build_evidence_context(requirements, evidence_map)

        # Build style context
        style_context = "\n\n".join([ex["content"] for ex in style_examples]) if style_examples else ""

        gap_block = ""
        if gaps:
            gap_block = f"""
Gap phrases (requirements with NO or weak evidence — do NOT invent bullets for these; only use these keywords when rewording evidence that you do have):
{chr(10).join("- " + g for g in gaps)}

"""
        prompt = load_prompt("edit_pack_user").format(
            job_url=job.url or "Job",
            requirements_formatted=format_requirements(requirements, include_priority=True),
            evidence_context=evidence_context,
            gap_block=gap_block,
            style_context=style_context,
        )

        logger.info("EditPackGenerator.generate: calling LLM (edit pack)")
        response = self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": load_prompt("edit_pack_system")},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        logger.info("EditPackGenerator.generate: done in %.2fs", time.perf_counter() - t0)
        return response.choices[0].message.content or ""

    def _build_evidence_context(
        self,
        requirements: List[Requirement],
        evidence_map: dict[int, List[dict[str, Any]]],
    ) -> str:
        """Build evidence context string."""
        context_parts = []

        for req in requirements:
            evidence = evidence_map.get(req.id, [])
            if evidence:
                context_parts.append(f"\nRequirement: {req.text}")
                for i, ev in enumerate(evidence, 1):
                    # Include enough content to ground bullets (cap to avoid huge prompts)
                    raw = (ev["content"] or "").strip()
                    content = raw if len(raw) <= 600 else raw[:597] + "..."
                    on_resume = ev.get("is_resume", False)
                    resume_label = " (on current resume)" if on_resume else " (not on resume)"
                    context_parts.append(f"  Evidence #{i} (score: {ev['similarity_score']:.2f}){resume_label}: {content}")
                    context_parts.append(f"    Source ID: {ev.get('source_id', 'N/A')}")

        return "\n".join(context_parts)
