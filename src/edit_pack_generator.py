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
from src.evidence_rag import EvidenceRAG
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
        style_examples = self.style_rag.retrieve_style_examples(job_context, top_k=3)

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

        prompt = f"""Generate a Resume Edit Pack for this job posting.

Job: {job.url or 'Job'}

Requirements:
{self._format_requirements(requirements)}

Evidence (the ONLY source of facts — you may only paraphrase or combine this text; do not add anything not stated here). Labels: "(on current resume)" = already on the user's base resume; "(not on resume)" = from brag doc/projects, not yet on the resume.
{evidence_context}
{gap_block}Style Examples (preferred writing style):
{style_context}

Generate a markdown document with:
1. **Bullets to Add**: Only use evidence marked "(not on resume)". Each bullet MUST cite at least one such Evidence #N. The bullet text may ONLY contain information that appears in the cited evidence. Do NOT suggest bullets that merely reword or paraphrase content already on the resume — every bullet must describe something that does NOT currently appear on the resume (different project, outcome, metric, or responsibility). Skip this section if there is no such evidence.
2. **Projects to Highlight**: For each project you recommend emphasizing, name it and explain WHY it should be highlighted for this job (e.g. which requirements it supports, what signal it sends). Only reference projects/sources that appear in the Evidence list.

Rules (strict):
- Bullets to Add: only from evidence marked (not on resume). Each must be genuinely new content — not a rephrasing of bullets already on the resume.
- Only use wording and facts that appear in the Evidence excerpts above. Do not invent metrics, technologies, or outcomes.
- For requirements with no evidence, do not make up a bullet. You may reword evidence to include gap phrases as keywords where relevant."""

        logger.info("EditPackGenerator.generate: calling LLM (edit pack)")
        response = self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You are an expert resume writer. Suggest only bullets that are directly supported by the evidence and that do NOT already appear on the resume (no rewording of existing bullets). For projects to highlight, always explain why each project is relevant to this job. Every bullet must cite its evidence source."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        logger.info("EditPackGenerator.generate: done in %.2fs", time.perf_counter() - t0)
        return response.choices[0].message.content or ""

    def _format_requirements(self, requirements: List[Requirement]) -> str:
        """Format requirements for prompt."""
        lines = []
        for req in requirements:
            lines.append(f"- [{req.category}] {req.text} (Priority: {req.priority})")
        return "\n".join(lines)

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
