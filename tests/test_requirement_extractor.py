"""Unit tests for RequirementExtractor with mocked OpenAI."""
import json
from unittest.mock import MagicMock

import pytest

from src.requirement_extractor import MAX_PROMPT_TOKENS
from src.requirement_extractor import RequirementExtractor
from src.requirement_extractor import Requirements
from src.requirement_extractor import RequirementItem


def _make_mock_client(response_content: str):
    """Create a mock OpenAI client that returns the given message content."""
    mock = MagicMock()
    mock.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=response_content))]
    )
    return mock


def test_extract_prompt_shape_and_success():
    """extract() sends correct system/user prompts and returns parsed Requirements."""
    job_text = "We need a Go developer with AWS experience. You will build APIs."
    response_json = json.dumps({
        "skills": ["Go", "AWS"],
        "responsibilities": ["Build APIs"],
        "must_haves": [],
        "keywords": ["APIs"],
    })
    client = _make_mock_client(response_json)
    extractor = RequirementExtractor(client=client)

    result = extractor.extract(job_text)

    assert isinstance(result, Requirements)
    assert result.skills == ["Go", "AWS"]
    assert result.responsibilities == ["Build APIs"]
    assert result.keywords == ["APIs"]
    call = client.chat.completions.create.call_args
    assert call.kwargs["response_format"] == {"type": "json_object"}
    assert call.kwargs["temperature"] == 0.3
    messages = call.kwargs["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "requirement" in (messages[0]["content"] or "").lower() or "extract" in (messages[0]["content"] or "").lower()
    assert messages[1]["role"] == "user"
    assert job_text in (messages[1]["content"] or "")


def test_extract_empty_job_text_raises():
    """extract() raises ValueError when job text is empty."""
    extractor = RequirementExtractor(client=MagicMock())
    with pytest.raises(ValueError, match="Job text is empty"):
        extractor.extract("")
    with pytest.raises(ValueError, match="Job text is empty"):
        extractor.extract("   \n  ")


def test_extract_no_client_raises():
    """extract() raises ValueError when OpenAI client is not configured."""
    extractor = RequirementExtractor(client=None)
    with pytest.raises(ValueError, match="OpenAI API key not configured"):
        extractor.extract("Some job text")


def test_extract_token_limit_raises():
    """extract() raises ValueError when prompt exceeds MAX_PROMPT_TOKENS."""
    from src import requirement_extractor as re_mod
    original_count = re_mod._count_tokens
    try:
        re_mod._count_tokens = lambda text, enc: MAX_PROMPT_TOKENS + 1 if len(text) > 5000 else len(enc.encode(text))
        client = _make_mock_client("{}")
        extractor = RequirementExtractor(client=client)
        huge = "x" * 6000  # triggers mock to return over limit
        with pytest.raises(ValueError, match="exceeds max token limit"):
            extractor.extract(huge)
        client.chat.completions.create.assert_not_called()
    finally:
        re_mod._count_tokens = original_count


def test_extract_invalid_json_falls_back_to_heuristic():
    """extract() on invalid JSON response uses _fallback_extract (finds keywords from job text)."""
    client = _make_mock_client("not valid json at all")
    extractor = RequirementExtractor(client=client)
    job_text = "We need Python and AWS. You will use React."
    result = extractor.extract(job_text)
    assert isinstance(result, Requirements)
    # Fallback looks for skills_keywords: python, aws, react etc.
    assert "python" in [s.lower() for s in result.skills]
    assert "aws" in [s.lower() for s in result.skills]


def test_extract_with_confidence_and_validation_prompt_shape_and_success():
    """extract_with_confidence_and_validation sends correct prompts and returns RequirementItems."""
    job_text = "We need Go and Docker. You will deploy to AWS."
    response_json = json.dumps({
        "skills": [
            {"text": "Go", "confidence": 0.95},
            {"text": "Docker", "confidence": 0.9},
            {"text": "AWS", "confidence": 0.85},
        ],
        "responsibilities": [],
        "must_haves": [],
        "keywords": [],
    })
    client = _make_mock_client(response_json)
    extractor = RequirementExtractor(client=client)

    items = extractor.extract_with_confidence_and_validation(job_text)

    assert len(items) >= 3
    texts = [i.text for i in items]
    assert "Go" in texts
    assert "Docker" in texts
    assert "AWS" in texts
    call = client.chat.completions.create.call_args
    messages = call.kwargs["messages"]
    assert messages[1]["role"] == "user"
    assert job_text in (messages[1]["content"] or "")


def test_extract_with_confidence_empty_job_text_raises():
    """extract_with_confidence_and_validation raises when job text is empty."""
    extractor = RequirementExtractor(client=MagicMock())
    with pytest.raises(ValueError, match="Job text is empty"):
        extractor.extract_with_confidence_and_validation("")


def test_extract_with_confidence_no_client_raises():
    """extract_with_confidence_and_validation raises when client is None."""
    extractor = RequirementExtractor(client=None)
    with pytest.raises(ValueError, match="OpenAI API key not configured"):
        extractor.extract_with_confidence_and_validation("Some job text")


def test_extract_with_confidence_token_limit_raises():
    """extract_with_confidence_and_validation raises when prompt exceeds token limit."""
    from src import requirement_extractor as re_mod
    original_count = re_mod._count_tokens
    try:
        re_mod._count_tokens = lambda text, enc: MAX_PROMPT_TOKENS + 1 if len(text) > 5000 else len(enc.encode(text))
        client = _make_mock_client("{}")
        extractor = RequirementExtractor(client=client)
        huge = "x" * 6000
        with pytest.raises(ValueError, match="exceeds max token limit"):
            extractor.extract_with_confidence_and_validation(huge)
        client.chat.completions.create.assert_not_called()
    finally:
        re_mod._count_tokens = original_count


def test_extract_with_confidence_returns_requirement_items():
    """extract_with_confidence_and_validation returns list of RequirementItem with category/priority."""
    response_json = json.dumps({
        "skills": [{"text": "Go", "confidence": 0.9}],
        "responsibilities": [{"text": "Ship features", "confidence": 0.8}],
        "must_haves": [],
        "keywords": [],
    })
    client = _make_mock_client(response_json)
    extractor = RequirementExtractor(client=client)
    items = extractor.extract_with_confidence_and_validation("Go developer. Ship features.")
    assert all(isinstance(i, RequirementItem) for i in items)
    by_cat = {i.category: i for i in items}
    assert by_cat["skills"].text == "Go"
    assert by_cat["skills"].priority == "must_have"
    assert by_cat["responsibilities"].text == "Ship features"
    assert by_cat["responsibilities"].priority == "nice_to_have"
