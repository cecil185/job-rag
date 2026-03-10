"""Load prompt templates from the prompts directory (one file per prompt)."""
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt template by name (without .txt). Returns trimmed string."""
    path = _PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8").strip()
