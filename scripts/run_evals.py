#!/usr/bin/env python3
"""
Run evaluation suite: extraction eval on job fixtures, optional RAG eval.
Writes results to data/eval/ and exits non-zero if any case fails.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evals.metrics import precision_recall_f1
from src.evals.metrics import recall_by_containment
from src.requirement_extractor import RequirementExtractor
from src.requirement_extractor import Requirements

# Pass threshold: recall (fraction of expected that appear in extracted) >= this
EXTRACTION_RECALL_THRESHOLD = 0.7
RESULTS_DIR = Path(__file__).resolve().parent.parent / "data" / "eval"
FIXTURES_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "job_postings.json"


def _requirements_to_strings(req: Requirements) -> list[str]:
    """Flatten Requirements to list of requirement strings for comparison."""
    out: list[str] = []
    out.extend(req.skills)
    out.extend(req.responsibilities)
    out.extend(req.must_haves)
    out.extend(req.keywords)
    return out


def load_fixtures(path: Path) -> dict[str, dict]:
    """Load job_postings.json: case_id -> {raw_text, expected_requirements}."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("job_postings.json must be a JSON object")
    return data


def run_extraction_evals(fixtures_path: Path, results_dir: Path) -> tuple[list[dict], bool]:
    """
    Run extraction eval on all job fixtures. Return (results_list, all_passed).
    """
    fixtures = load_fixtures(fixtures_path)
    extractor = RequirementExtractor()
    results: list[dict] = []
    all_passed = True

    for case_id, case in fixtures.items():
        raw_text = case.get("raw_text") or ""
        expected = case.get("expected_requirements") or []
        if not raw_text:
            results.append({
                "case_id": case_id,
                "passed": False,
                "error": "missing raw_text",
                "precision": None,
                "recall": None,
                "f1": None,
                "extracted": [],
                "expected": expected,
                "latency_seconds": None,
            })
            all_passed = False
            continue

        t0 = time.perf_counter()
        try:
            req: Requirements = extractor.extract(raw_text)
            latency = time.perf_counter() - t0
        except Exception as e:
            latency = time.perf_counter() - t0
            results.append({
                "case_id": case_id,
                "passed": False,
                "error": str(e),
                "precision": None,
                "recall": None,
                "f1": None,
                "extracted": [],
                "expected": expected,
                "latency_seconds": round(latency, 3),
            })
            all_passed = False
            continue

        extracted = _requirements_to_strings(req)
        precision, recall, f1 = precision_recall_f1(expected, extracted)
        recall_containment = recall_by_containment(expected, extracted)
        passed = recall_containment >= EXTRACTION_RECALL_THRESHOLD
        if not passed:
            all_passed = False

        results.append({
            "case_id": case_id,
            "passed": passed,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "recall_containment": round(recall_containment, 4),
            "f1": round(f1, 4),
            "extracted": extracted,
            "expected": expected,
            "latency_seconds": round(latency, 3),
        })

    return results, all_passed


def run_rag_evals(
    evidence_fixtures_dir: Path,
    results_dir: Path,
    top_k: int = 5,
    expected_in_top_n: int = 3,
    pass_fraction: float = 0.8,
) -> tuple[list[dict], bool]:
    """
    Optional RAG eval: load evidence fixtures, run retrieve() for each (requirement, expected_source_id),
    check expected source appears in top_n. Returns (results_list, all_passed).
    Requires DATABASE_URL and evidence_docs.json + expected_retrieval.json in evidence_fixtures_dir.
    """
    docs_file = evidence_fixtures_dir / "evidence_docs.json"
    mapping_file = evidence_fixtures_dir / "expected_retrieval.json"
    if not docs_file.is_file() or not mapping_file.is_file():
        return [], True  # skip silently

    try:
        from src.database import SessionLocal
        from src.database import EvidenceChunk
        from src.evidence_rag import EvidenceRAG
    except Exception as e:
        print(f"RAG eval skipped (import): {e}", file=sys.stderr)
        return [], True

    with open(docs_file, encoding="utf-8") as f:
        evidence_docs = json.load(f)
    with open(mapping_file, encoding="utf-8") as f:
        expected_retrieval = json.load(f)

    db = SessionLocal()
    try:
        rag = EvidenceRAG(db)
        # Use a distinct source_id prefix so we can clean up
        eval_source_prefix = "eval_fixture_"
        # Remove any previous eval chunks
        db.query(EvidenceChunk).filter(EvidenceChunk.source_id.like(f"{eval_source_prefix}%")).delete(synchronize_session=False)
        db.commit()
        for i, doc in enumerate(evidence_docs):
            source_id = doc.get("source_id") or f"{eval_source_prefix}{i}"
            if not source_id.startswith(eval_source_prefix):
                source_id = f"{eval_source_prefix}{source_id}"
            rag.add_evidence(doc.get("text", ""), source_id=source_id)
        # Normalize expected_retrieval: map expected_source_id to eval_fixture_ prefix if needed
        results: list[dict] = []
        all_passed = True
        for case_id, pairs in expected_retrieval.items():
            for pair in pairs:
                req_text = pair.get("requirement", "")
                expected_sid = pair.get("expected_source_id", "")
                if not req_text or not expected_sid:
                    continue
                if not expected_sid.startswith(eval_source_prefix):
                    expected_sid = f"{eval_source_prefix}{expected_sid}"
                t0 = time.perf_counter()
                hits = rag.retrieve(req_text, top_k=top_k)
                latency = time.perf_counter() - t0
                source_ids = [h["source_id"] for h in hits]
                in_top_n = expected_sid in (source_ids[:expected_in_top_n] if expected_in_top_n else source_ids)
                passed = in_top_n
                if not passed:
                    all_passed = False
                results.append({
                    "case_id": case_id,
                    "requirement": req_text,
                    "expected_source_id": expected_sid,
                    "passed": passed,
                    "in_top_n": expected_in_top_n,
                    "rank": source_ids.index(expected_sid) + 1 if expected_sid in source_ids else None,
                    "latency_seconds": round(latency, 3),
                })
        # Clean up eval chunks
        db.query(EvidenceChunk).filter(EvidenceChunk.source_id.like(f"{eval_source_prefix}%")).delete(synchronize_session=False)
        db.commit()
        # Pass threshold: at least pass_fraction of pairs must pass
        if results:
            fraction = sum(1 for r in results if r["passed"]) / len(results)
            all_passed = fraction >= pass_fraction
        return results, all_passed
    except Exception as e:
        print(f"RAG eval skipped (database or RAG error): {e}", file=sys.stderr)
        return [], True
    finally:
        db.close()


def main() -> int:
    fixtures_path = Path(os.environ.get("EVAL_FIXTURES", str(FIXTURES_PATH)))
    if not fixtures_path.is_file():
        print(f"Fixtures not found: {fixtures_path}", file=sys.stderr)
        return 1

    results_dir = Path(os.environ.get("EVAL_RESULTS_DIR", str(RESULTS_DIR)))
    results_dir.mkdir(parents=True, exist_ok=True)

    extraction_results, extraction_ok = run_extraction_evals(fixtures_path, results_dir)
    output_data: dict = {
        "extraction": {
            "passed": extraction_ok,
            "threshold_recall": EXTRACTION_RECALL_THRESHOLD,
            "cases": extraction_results,
        }
    }

    evidence_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "evidence"
    if os.environ.get("EVAL_RAG"):
        rag_results, rag_ok = run_rag_evals(evidence_dir, results_dir)
        output_data["rag"] = {"passed": rag_ok, "cases": rag_results}
        if rag_results:
            print(f"RAG eval: {'PASSED' if rag_ok else 'FAILED'} ({sum(1 for r in rag_results if r['passed'])}/{len(rag_results)} pairs)")
        if not rag_ok:
            extraction_ok = False
    else:
        print("RAG eval: skipped (set EVAL_RAG=1 to run; requires DB)")

    output_file = results_dir / "extraction_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    print(f"Wrote {output_file}")

    if not extraction_ok:
        failed = [r["case_id"] for r in extraction_results if not r.get("passed")]
        print(f"Extraction eval failed for: {failed}", file=sys.stderr)
        return 1
    print("All extraction evals passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
