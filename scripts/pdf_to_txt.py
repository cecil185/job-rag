#!/usr/bin/env python3
"""Create .txt versions of each PDF in docs/ (saved alongside in docs/)."""
from pathlib import Path
from typing import BinaryIO

import pdfplumber

DOCS = Path(__file__).resolve().parent.parent / "docs"


def pdf_to_text(source: Path | str | bytes | BinaryIO) -> str:
    """Extract text from a PDF (path or bytes). Returns text string."""
    with pdfplumber.open(source) as pdf:
        parts = [p.extract_text() or "" for p in pdf.pages]
    return "\n\n".join(parts)


def pdf_to_txt(pdf_path: Path) -> Path | None:
    """Extract text from PDF and save as .txt in same dir. Returns txt path or None."""
    try:
        text = pdf_to_text(pdf_path)
        txt_path = pdf_path.with_suffix(".txt")
        txt_path.write_text(text, encoding="utf-8")
        return txt_path
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
        return None


def main() -> None:
    docs = DOCS
    if not docs.is_dir():
        print(f"Docs dir not found: {docs}")
        return
    pdfs = list(docs.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {docs}")
        return
    for pdf_path in sorted(pdfs):
        out = pdf_to_txt(pdf_path)
        if out:
            print(f"  {pdf_path.name} -> {out.name}")


if __name__ == "__main__":
    main()
