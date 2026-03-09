"""Metrics for comparing extracted requirements to expected (golden) sets."""


def _normalize(s: str) -> str:
    """Normalize requirement text for comparison: lowercase, strip, collapse whitespace."""
    return " ".join((s or "").strip().lower().split())


def requirement_sets(
    expected: list[str],
    extracted: list[str],
) -> tuple[set[str], set[str]]:
    """Return (expected_set, extracted_set) of normalized requirement strings."""
    exp_set = {_normalize(x) for x in expected if x and str(x).strip()}
    ext_set = {_normalize(x) for x in extracted if x and str(x).strip()}
    return exp_set, ext_set


def precision_recall_f1(
    expected: list[str],
    extracted: list[str],
) -> tuple[float, float, float]:
    """
    Compute precision, recall, F1 over sets of requirement strings.
    - Precision: fraction of extracted that appear in expected.
    - Recall: fraction of expected that appear in extracted.
    - F1: harmonic mean of precision and recall.
    """
    exp_set, ext_set = requirement_sets(expected, extracted)
    if not ext_set:
        return 0.0, 0.0, 0.0
    if not exp_set:
        return 0.0, 0.0, 0.0
    true_pos = len(exp_set & ext_set)
    precision = true_pos / len(ext_set)
    recall = true_pos / len(exp_set)
    if precision + recall == 0:
        return precision, recall, 0.0
    f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def overlap_expected_in_extracted(expected: list[str], extracted: list[str]) -> float:
    """Fraction of expected items that have a matching extracted item (recall)."""
    exp_set, ext_set = requirement_sets(expected, extracted)
    if not exp_set:
        return 1.0
    return len(exp_set & ext_set) / len(exp_set)


def recall_by_containment(expected: list[str], extracted: list[str]) -> float:
    """
    Recall where an expected item counts as matched if any extracted string
    contains it (or is contained in it) after normalization. Handles LLM output
    that expands e.g. "Linux" to "Linux system administration".
    """
    if not expected:
        return 1.0
    ext_norm = [_normalize(x) for x in extracted if x and str(x).strip()]
    matched = 0
    for e in expected:
        if not e or not str(e).strip():
            continue
        ne = _normalize(e)
        for ex in ext_norm:
            if ne in ex or ex in ne:
                matched += 1
                break
    return matched / len(expected)
