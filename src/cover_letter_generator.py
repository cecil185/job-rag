"""Cover letter generator using Evidence and Style RAG."""
from openai import OpenAI
from typing import List, Dict
from src.database import Requirement, Job
from src.evidence_rag import EvidenceRAG
from src.style_rag import StyleRAG
from src.config import settings


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

        job_context = job.title or "Job"
        style_examples = self.style_rag.retrieve_style_examples(job_context, top_k=3)
        evidence_context = self._build_evidence_context(requirements, evidence_map)
        style_context = "\n\n".join([ex["content"] for ex in style_examples]) if style_examples else ""

        prompt = f"""Write a professional cover letter for this job application.

Job: {job.title or 'Job'}

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
- Be concise; avoid generic fluff
- Output the letter only (no meta commentary). You may use a simple greeting like "Dear Hiring Manager," and sign off with "[Your Name]" or similar."""

        response = self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You are an expert cover letter writer. Ground every claim in the evidence provided. Be specific and professional."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6
        )

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
