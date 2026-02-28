"""Requirement extractor using LLM."""
import logging
import time
from pydantic import BaseModel, Field
from typing import List, Optional
from openai import OpenAI
from src.config import settings
import json
import tiktoken

logger = logging.getLogger(__name__)

# Max input tokens for the LLM request (system + user message). Exceeding prompts raise before submit.
MAX_PROMPT_TOKENS = 8000

# Requirement text containing any of these words (case-insensitive) is filtered out (no LLM).
EXCLUDED_REQUIREMENT_WORDS = frozenset({
    "python", "diversity", "pay", "benefits", "equity", "privacy", "candidate", "remote work"
})


def _should_exclude_requirement(text: str) -> bool:
    """True if requirement text contains any excluded word (case-insensitive)."""
    lower = (text or "").lower()
    return any(word in lower for word in EXCLUDED_REQUIREMENT_WORDS)


def _filter_requirements_dict(data: dict) -> dict:
    """Filter out list entries that contain any excluded word. Modifies and returns data."""
    for key in ("skills", "responsibilities", "must_haves", "keywords"):
        if key in data and isinstance(data[key], list):
            data[key] = [s for s in data[key] if isinstance(s, str) and not _should_exclude_requirement(s)]
    return data


class RequirementItem(BaseModel):
    """Single requirement item."""
    text: str = Field(description="The requirement text")
    category: str = Field(description="One of: skills, responsibilities, must_haves, keywords")
    priority: str = Field(description="One of: must_have, nice_to_have")


class Requirements(BaseModel):
    """Structured requirements from job posting."""
    skills: List[str] = Field(default_factory=list, description="Technical skills and technologies")
    responsibilities: List[str] = Field(default_factory=list, description="Job responsibilities and duties")
    must_haves: List[str] = Field(default_factory=list, description="Must-have requirements")
    keywords: List[str] = Field(default_factory=list, description="Important keywords and phrases")
    
    def to_requirement_items(self) -> List[RequirementItem]:
        """Convert to list of RequirementItem objects."""
        items = []
        
        for skill in self.skills:
            items.append(RequirementItem(text=skill, category="skills", priority="must_have"))
        
        for resp in self.responsibilities:
            items.append(RequirementItem(text=resp, category="responsibilities", priority="nice_to_have"))
        
        for must in self.must_haves:
            items.append(RequirementItem(text=must, category="must_haves", priority="must_have"))
        
        for keyword in self.keywords:
            items.append(RequirementItem(text=keyword, category="keywords", priority="nice_to_have"))
        
        return items


def _count_tokens(text: str, encoding: tiktoken.Encoding) -> int:
    return len(encoding.encode(text))


class RequirementExtractor:
    """Extracts structured requirements from job postings."""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self._encoding = tiktoken.get_encoding("cl100k_base")
    
    def extract(self, job_text: str) -> Requirements:
        """
        Extract requirements from job posting text.
        
        Args:
            job_text: Raw text from job posting
            
        Returns:
            Requirements object with structured data
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")
        if not job_text or not job_text.strip():
            raise ValueError("Job text is empty; cannot extract requirements.")

        t0 = time.perf_counter()
        logger.info("RequirementExtractor.extract: calling LLM")

        system_content = "You are an expert at analyzing job postings and extracting structured requirements. Always return valid JSON."
        template = """Extract structured requirements from this job posting. Be thorough and specific.

Job Posting:
{job_text}

Extract:
1. Technical skills and technologies (programming languages, frameworks, tools)
2. Job responsibilities and duties
3. Must-have requirements (non-negotiable qualifications)
4. Important keywords and phrases

Return a JSON object with these fields: skills, responsibilities, must_haves, keywords.
Each field should be a list of strings. Be specific and comprehensive."""

        prompt = template.format(job_text=job_text)
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ]
        total_tokens = sum(_count_tokens(m["content"], self._encoding) for m in messages)
        logging.info(f"total_tokens: {total_tokens}")
        if total_tokens > MAX_PROMPT_TOKENS:
            raise ValueError(
                f"Prompt exceeds max token limit: {total_tokens} > {MAX_PROMPT_TOKENS}. "
                "Reduce job text or increase MAX_PROMPT_TOKENS."
            )

        response = self.client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3
        )
        logger.info("RequirementExtractor.extract: done in %.2fs", time.perf_counter() - t0)
        result_text = response.choices[0].message.content
        
        try:
            result_dict = json.loads(result_text)
            _filter_requirements_dict(result_dict)
            return Requirements(**result_dict)
        except Exception as e:
            # Fallback: try to parse manually
            print(f"Warning: Failed to parse JSON response: {e}")
            return self._fallback_extract(job_text)
    
    def _fallback_extract(self, job_text: str) -> Requirements:
        """Fallback extraction if JSON parsing fails."""
        # Simple keyword-based extraction as fallback
        skills_keywords = ['python', 'javascript', 'java', 'react', 'aws', 'docker', 'kubernetes', 'sql', 'postgresql']
        found_skills = [kw for kw in skills_keywords if kw.lower() in job_text.lower()]
        
        return Requirements(
            skills=found_skills,
            responsibilities=[],
            must_haves=[],
            keywords=[]
        )
