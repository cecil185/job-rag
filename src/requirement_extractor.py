"""Requirement extractor using LLM."""
from pydantic import BaseModel, Field
from typing import List, Optional
from openai import OpenAI
from src.config import settings
import json


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


class RequirementExtractor:
    """Extracts structured requirements from job postings."""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
    
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
        
        prompt = f"""Extract structured requirements from this job posting. Be thorough and specific.

Job Posting:
{job_text[:8000]}  # Limit to avoid token limits

Extract:
1. Technical skills and technologies (programming languages, frameworks, tools)
2. Job responsibilities and duties
3. Must-have requirements (non-negotiable qualifications)
4. Important keywords and phrases

Return a JSON object with these fields: skills, responsibilities, must_haves, keywords.
Each field should be a list of strings. Be specific and comprehensive."""

        response = self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You are an expert at analyzing job postings and extracting structured requirements. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        result_text = response.choices[0].message.content
        
        try:
            result_dict = json.loads(result_text)
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
