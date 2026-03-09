"""Tests for eval suite: metrics and fixture loading."""
import json
from pathlib import Path

import pytest

from src.evals.metrics import overlap_expected_in_extracted
from src.evals.metrics import precision_recall_f1
from src.evals.metrics import requirement_sets


def test_requirement_sets_normalizes() -> None:
    exp, ext = requirement_sets(["  Java  ", "AWS"], ["java", "  AWS  "])
    assert exp == {"java", "aws"}
    assert ext == {"java", "aws"}
    assert exp == ext


def test_precision_recall_f1_perfect() -> None:
    p, r, f1 = precision_recall_f1(["a", "b"], ["a", "b"])
    assert p == 1.0
    assert r == 1.0
    assert f1 == 1.0


def test_precision_recall_f1_partial() -> None:
    p, r, f1 = precision_recall_f1(["a", "b", "c"], ["a", "b"])
    assert r == 2 / 3  # 2 of 3 expected found
    assert p == 1.0  # 2 extracted, both in expected
    assert f1 == 4 / 5  # 2 * 1 * 2/3 / (1 + 2/3)


def test_precision_recall_f1_empty_expected() -> None:
    p, r, f1 = precision_recall_f1([], ["a"])
    assert (p, r, f1) == (0.0, 0.0, 0.0)


def test_overlap_expected_in_extracted() -> None:
    assert overlap_expected_in_extracted(["a", "b"], ["a", "b", "c"]) == 1.0
    assert overlap_expected_in_extracted(["a", "b"], ["a"]) == 0.5


def test_fixtures_load_and_have_expected() -> None:
    path = Path(__file__).resolve().parent / "fixtures" / "job_postings.json"
    assert path.is_file()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) >= 5
    for case_id, case in data.items():
        assert "raw_text" in case
        assert "expected_requirements" in case
        assert isinstance(case["expected_requirements"], list)
