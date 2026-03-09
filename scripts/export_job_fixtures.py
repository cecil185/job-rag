#!/usr/bin/env python3
"""
Export job raw_text from the jobs table to tests/fixtures/job_postings.json.
Run from project root. You must manually add expected_requirements to each case.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import SessionLocal
from src.database import Job


def main() -> int:
    out_path = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "job_postings.json"
    db = SessionLocal()
    try:
        jobs = db.query(Job).filter(Job.raw_text.isnot(None)).limit(20).all()
        fixtures: dict[str, dict] = {}
        for i, job in enumerate(jobs, start=1):
            case_id = f"job_{i:02d}"
            fixtures[case_id] = {
                "raw_text": (job.raw_text or "").strip(),
                "expected_requirements": [],  # Add golden list manually
            }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(fixtures, f, indent=2)
        print(f"Exported {len(fixtures)} jobs to {out_path}")
        print("Add expected_requirements to each case for eval.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
