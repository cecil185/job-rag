"""Application question answer generator using Evidence and Style RAG."""
from openai import OpenAI
from typing import List, Dict
from src.database import Requirement, Job
from src.evidence_rag import EvidenceRAG
from src.style_rag import StyleRAG
from src.config import settings


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
        evidence_map: Dict[int, List[Dict]],
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

        job_context = job.title or "Job"
        style_examples = self.style_rag.retrieve_style_examples(job_context, top_k=3)
        evidence_context = self._build_evidence_context(requirements, evidence_map)
        style_context = "\n\n".join([ex["content"] for ex in style_examples]) if style_examples else ""

        prompt = f"""Answer the following job application question. Be specific and ground your answer in the candidate evidence below.

Job: {job.title or 'Job'}

Application question:
{question}

Key requirements from the posting:
{self._format_requirements(requirements)}

Candidate evidence (proof points from resume/projects to use):
{evidence_context}

Tone/style reference (match this voice):
{style_context or "(Use professional, concise tone.)"}

Instructions:
- Answer in 1–3 short paragraphs (or bullets if the question suits it)
- Use concrete examples from the evidence; avoid generic claims
- Match the role language where relevant
- Output only the answer, no preamble or meta commentary."""

        response = self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You answer job application questions. Be specific and evidence-based. Match the provided style."},
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
                    context_parts.append(f"  #{i}: {ev['content'][:250]}{'...' if len(ev.get('content', '')) > 250 else ''}")
        return "\n".join(context_parts) if context_parts else "No evidence matches yet."
