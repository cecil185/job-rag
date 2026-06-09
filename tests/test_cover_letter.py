"""Unit tests for cover letter pipeline: Generator, Critic, Reviser with mocked client."""
from unittest.mock import MagicMock

import pytest

from src.cover_letter_critic import CoverLetterCritic
from src.cover_letter_generator import CoverLetterGenerator
from src.cover_letter_reviser import CoverLetterReviser


def _make_mock_client(response_content: str):
    """Create a mock OpenAI client that returns the given message content."""
    mock = MagicMock()
    mock.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=response_content))]
    )
    return mock


def _make_mock_job(url: str = "https://example.com/job/1"):
    """Minimal job-like object for prompts."""
    job = MagicMock()
    job.url = url
    job.id = 1
    return job


def _make_mock_requirement(req_id: int, text: str, category: str = "skills", priority: str = "must_have"):
    """Minimal requirement-like object for prompts."""
    req = MagicMock()
    req.id = req_id
    req.text = text
    req.category = category
    req.priority = priority
    return req


# --- CoverLetterGenerator ---


def test_cover_letter_generator_prompt_shape_and_success():
    """CoverLetterGenerator.generate sends system + user prompt with job_url, requirements, evidence, style."""
    mock_style = MagicMock()
    mock_style.retrieve_style_examples.return_value = [{"content": "Be concise."}]
    mock_evidence_rag = MagicMock()
    client = _make_mock_client("Generated cover letter body.")
    job = _make_mock_job("https://company.com/role")
    reqs = [_make_mock_requirement(1, "Python"), _make_mock_requirement(2, "AWS")]
    evidence_map = {1: [{"content": "I used Python at Acme."}], 2: []}
    generator = CoverLetterGenerator(
        evidence_rag=mock_evidence_rag,
        style_rag=mock_style,
        client=client,
    )

    result = generator.generate(job, reqs, evidence_map)

    assert result == "Generated cover letter body."
    call = client.chat.completions.create.call_args
    messages = call.kwargs["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    user_content = messages[1]["content"] or ""
    assert "https://company.com/role" in user_content or "Job" in user_content
    assert "Python" in user_content
    assert "AWS" in user_content
    assert "I used Python" in user_content or "evidence" in user_content.lower()
    assert "Be concise" in user_content
    mock_style.retrieve_style_examples.assert_called_once()


def test_cover_letter_generator_no_client_raises():
    """CoverLetterGenerator.generate raises when client is not configured."""
    generator = CoverLetterGenerator(
        evidence_rag=MagicMock(),
        style_rag=MagicMock(),
        client=None,
    )
    job = _make_mock_job()
    with pytest.raises(ValueError, match="OpenAI API key not configured"):
        generator.generate(job, [], {})


# --- CoverLetterCritic ---


def test_cover_letter_critic_prompt_shape_and_success():
    """CoverLetterCritic.critique sends system + user prompt with job_url, requirements, evidence, draft."""
    client = _make_mock_client("Tone is good. Add more on AWS.")
    critic = CoverLetterCritic(client=client)
    job = _make_mock_job("https://co.com/job")
    reqs = [_make_mock_requirement(1, "Python")]
    evidence_map = {1: [{"content": "Python at X."}]}
    draft = "Dear Hiring Manager, I have Python experience."

    result = critic.critique(draft, job, reqs, evidence_map)

    assert result == "Tone is good. Add more on AWS."
    call = client.chat.completions.create.call_args
    messages = call.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    user_content = messages[1]["content"] or ""
    assert "https://co.com/job" in user_content or "Job" in user_content
    assert "Python" in user_content
    assert draft in user_content
    assert call.kwargs["temperature"] == 0.3


def test_cover_letter_critic_no_client_raises():
    """CoverLetterCritic.critique raises when client is not configured."""
    critic = CoverLetterCritic(client=None)
    with pytest.raises(ValueError, match="OpenAI API key not configured"):
        critic.critique("draft", _make_mock_job(), [], {})


# --- CoverLetterReviser ---


def test_cover_letter_reviser_prompt_shape_and_success():
    """CoverLetterReviser.revise sends system + user prompt with job_url, requirements, evidence, critique, draft."""
    client = _make_mock_client("Revised cover letter with AWS added.")
    reviser = CoverLetterReviser(client=client)
    job = _make_mock_job()
    reqs = [_make_mock_requirement(1, "AWS")]
    evidence_map = {1: [{"content": "Deployed to AWS."}]}
    draft = "Original draft."
    critique = "Add more about AWS experience."

    result = reviser.revise(draft, critique, job, reqs, evidence_map)

    assert result == "Revised cover letter with AWS added."
    call = client.chat.completions.create.call_args
    messages = call.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    user_content = messages[1]["content"] or ""
    assert draft in user_content
    assert critique in user_content
    assert "AWS" in user_content
    assert call.kwargs["temperature"] == 0.5


def test_cover_letter_reviser_no_client_raises():
    """CoverLetterReviser.revise raises when client is not configured."""
    reviser = CoverLetterReviser(client=None)
    with pytest.raises(ValueError, match="OpenAI API key not configured"):
        reviser.revise("draft", "critique", _make_mock_job(), [], {})
