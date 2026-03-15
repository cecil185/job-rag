"""Shared helpers for formatting requirements and evidence in prompts."""
from typing import Any
from typing import List

from src.database import Requirement


def format_requirements(
    requirements: List[Requirement],
    include_priority: bool = False,
) -> str:
    """Format requirements as bullet lines for prompts."""
    lines = []
    for req in requirements:
        line = f"- [{req.category}] {req.text}"
        if include_priority:
            line += f" (Priority: {req.priority})"
        lines.append(line)
    return "\n".join(lines)


def build_evidence_context_brief(
    requirements: List[Requirement],
    evidence_map: dict[int, List[dict[str, Any]]],
    max_content_len: int = 250,
) -> str:
    """Build a short evidence context string (Re: requirement, then #n: content snippet)."""
    parts = []
    for req in requirements:
        evidence = evidence_map.get(req.id, [])
        if evidence:
            parts.append(f"\nRe: {req.text}")
            for i, ev in enumerate(evidence, 1):
                content = (ev.get("content") or "")[:max_content_len]
                if len(ev.get("content") or "") > max_content_len:
                    content += "..."
                parts.append(f"  #{i}: {content}")
    return "\n".join(parts) if parts else "No evidence matches yet."
