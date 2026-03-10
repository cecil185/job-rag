"""Requirement extractor using LLM."""
import json
import logging
import time
from typing import Any
from typing import List
from typing import Optional

import tiktoken
from openai import OpenAI
from pydantic import BaseModel
from pydantic import Field

from src.config import settings
from src.prompt_loader import load_prompt

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


def _filter_requirements_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Filter out list entries that contain any excluded word. Modifies and returns data."""
    for key in ("skills", "responsibilities", "must_haves", "keywords"):
        if key in data and isinstance(data[key], list):
            data[key] = [s for s in data[key] if isinstance(s, str) and not _should_exclude_requirement(s)]
    return data


def _parse_entries(raw_list: list) -> List[dict[str, Any]]:
    """Normalize LLM list: each element can be a string or {text, confidence}. Returns list of {text, confidence?}."""
    out: List[dict[str, Any]] = []
    for x in raw_list or []:
        if isinstance(x, str):
            out.append({"text": x, "confidence": None})
        elif isinstance(x, dict) and isinstance(x.get("text"), str):
            out.append({"text": x["text"], "confidence": x.get("confidence")})
    return out


def _normalize_for_match(s: str) -> str:
    """Normalize text for heuristic validation: lowercase, collapse whitespace."""
    return " ".join((s or "").lower().split())


def _validate_requirement_against_source(requirement_text: str, raw_text: str, snippet_max_len: int = 200) -> tuple[bool, Optional[str]]:
    """
    Heuristic validation: check if requirement (or key phrase) appears in raw_text.
    Returns (validated, raw_snippet). Snippet is a short excerpt from raw_text that contains the match.
    """
    if not raw_text or not requirement_text:
        return False, None
    raw_norm = _normalize_for_match(raw_text)
    req_norm = _normalize_for_match(requirement_text)
    if not req_norm:
        return False, None
    # Prefer full phrase match; fall back to significant substring (e.g. first 5+ words)
    if req_norm in raw_norm:
        idx = raw_norm.find(req_norm)
        # Map back to original raw_text for snippet (approximate by using same span length)
        start = max(0, idx - 50)
        end = min(len(raw_norm), idx + len(req_norm) + 80)
        snippet = raw_text[start:end].strip()
        if len(snippet) > snippet_max_len:
            snippet = snippet[:snippet_max_len] + "..."
        return True, snippet or None
    # Try key phrase: longest substring of 3+ words
    words = req_norm.split()
    for n in range(min(5, len(words)), 2, -1):
        phrase = " ".join(words[:n])
        if len(phrase) < 10:
            continue
        if phrase in raw_norm:
            idx = raw_norm.find(phrase)
            start = max(0, idx - 40)
            end = min(len(raw_norm), idx + len(phrase) + 60)
            snippet = raw_text[start:end].strip()
            if len(snippet) > snippet_max_len:
                snippet = snippet[:snippet_max_len] + "..."
            return True, snippet or None
    return False, None


class RequirementItem(BaseModel):
    """Single requirement item."""
    text: str = Field(description="The requirement text")
    category: str = Field(description="One of: skills, responsibilities, must_haves, keywords")
    priority: str = Field(description="One of: must_have, nice_to_have")
    confidence: Optional[float] = Field(default=None, description="Confidence score in [0, 1]")
    validated: Optional[bool] = Field(default=None, description="Whether requirement was found in source text")
    raw_snippet: Optional[str] = Field(default=None, description="Excerpt from source that supports the requirement")


class RequirementEntry(BaseModel):
    """Single entry with text and confidence (for LLM response)."""
    text: str = Field(description="The requirement text")
    confidence: float = Field(ge=0, le=1, description="Confidence that this is a real requirement from the posting")


class Requirements(BaseModel):
    """Structured requirements from job posting."""
    skills: List[str] = Field(default_factory=list, description="Technical skills and technologies")
    responsibilities: List[str] = Field(default_factory=list, description="Job responsibilities and duties")
    must_haves: List[str] = Field(default_factory=list, description="Must-have requirements")
    keywords: List[str] = Field(default_factory=list, description="Important keywords and phrases")

    def to_requirement_items(self) -> List[RequirementItem]:
        """Convert to list of RequirementItem objects (no confidence/validation)."""
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


class RequirementsWithConfidence(BaseModel):
    """Structured requirements with per-item confidence (LLM response)."""
    skills: List[RequirementEntry] = Field(default_factory=list)
    responsibilities: List[RequirementEntry] = Field(default_factory=list)
    must_haves: List[RequirementEntry] = Field(default_factory=list)
    keywords: List[RequirementEntry] = Field(default_factory=list)


def _count_tokens(text: str, encoding: tiktoken.Encoding) -> int:
    return len(encoding.encode(text))


class RequirementExtractor:
    """Extracts structured requirements from job postings."""

    def __init__(self) -> None:
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

        system_content = load_prompt("requirement_extract_system")
        template = load_prompt("requirement_extract_user")
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

    def extract_with_confidence_and_validation(self, job_text: str) -> List[RequirementItem]:
        """
        Extract requirements with per-item confidence and validate each against job_text.
        Returns list of RequirementItem with confidence, validated, and raw_snippet set.
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")
        if not job_text or not job_text.strip():
            raise ValueError("Job text is empty; cannot extract requirements.")

        t0 = time.perf_counter()
        logger.info("RequirementExtractor.extract_with_confidence_and_validation: calling LLM")

        system_content = load_prompt("requirement_extract_confidence_system")
        template = load_prompt("requirement_extract_confidence_user")
        prompt = template.format(job_text=job_text)
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ]
        total_tokens = sum(_count_tokens(m["content"], self._encoding) for m in messages)
        if total_tokens > MAX_PROMPT_TOKENS:
            raise ValueError(
                f"Prompt exceeds max token limit: {total_tokens} > {MAX_PROMPT_TOKENS}. "
                "Reduce job text or increase MAX_PROMPT_TOKENS."
            )

        response = self.client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        logger.info("RequirementExtractor.extract_with_confidence_and_validation: LLM done in %.2fs", time.perf_counter() - t0)
        result_dict = json.loads(response.choices[0].message.content or "{}")

        items: List[RequirementItem] = []
        raw_lower = (job_text or "").lower()

        def entries_with_confidence(key: str, priority: str) -> None:
            for entry in _parse_entries(result_dict.get(key) or []):
                if _should_exclude_requirement(entry["text"]):
                    continue
                conf = entry.get("confidence")
                if conf is None:
                    conf = 0.8
                validated = False
                raw_snippet: Optional[str] = None
                if not settings.skip_requirement_validation:
                    validated, raw_snippet = _validate_requirement_against_source(entry["text"], job_text)
                items.append(
                    RequirementItem(
                        text=entry["text"],
                        category=key,
                        priority=priority,
                        confidence=conf,
                        validated=validated if not settings.skip_requirement_validation else None,
                        raw_snippet=raw_snippet,
                    )
                )

        entries_with_confidence("skills", "must_have")
        entries_with_confidence("responsibilities", "nice_to_have")
        entries_with_confidence("must_haves", "must_have")
        entries_with_confidence("keywords", "nice_to_have")

        logger.info(
            "RequirementExtractor.extract_with_confidence_and_validation: done in %.2fs, %d items",
            time.perf_counter() - t0,
            len(items),
        )
        return items

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
