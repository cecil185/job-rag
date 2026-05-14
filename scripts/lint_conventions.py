#!/usr/bin/env python3
# Custom conventions linter for Job RAG.
# Each rule has a stable ID referenced from docs/eng/conventions.md.
# Errors print rule ID + a one-line fix so agents can self-correct.
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_URL = "docs/eng/conventions.md"
BASELINE_FILE = ROOT / ".lint-baseline.txt"

# --- Targets ---------------------------------------------------------------

PY_ROOTS = ["src", "app.py", "cli.py", "scripts"]
SHELL_TARGETS = ["Makefile", "justfile"]
SHELL_EXTS = {".sh", ".bash"}

# --- Limits ----------------------------------------------------------------

MAX_PY_LINES = 800

# --- Helpers ---------------------------------------------------------------


def _iter_python_files() -> list[Path]:
    out: list[Path] = []
    for entry in PY_ROOTS:
        p = ROOT / entry
        if p.is_file() and p.suffix == ".py":
            out.append(p)
        elif p.is_dir():
            out.extend(sorted(p.rglob("*.py")))
    return [p for p in out if "__pycache__" not in p.parts]


def _iter_shell_files() -> list[Path]:
    out: list[Path] = []
    for name in SHELL_TARGETS:
        p = ROOT / name
        if p.exists():
            out.append(p)
    for sub in ["scripts", "."]:
        base = ROOT / sub
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in SHELL_EXTS:
                out.append(p)
    return out


def _load_baseline() -> set[tuple[str, str]]:
    if not BASELINE_FILE.exists():
        return set()
    pairs: set[tuple[str, str]] = set()
    for line in BASELINE_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rule, _, path = line.partition(" ")
        if rule and path:
            pairs.add((rule, path))
    return pairs


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


# --- Rules -----------------------------------------------------------------


def check_no_top_docstring(py_files: list[Path]) -> list[tuple[str, str, str]]:
    # Rule no-top-docstring: forbid module-level triple-quoted banners at top of .py files.
    out: list[tuple[str, str, str]] = []
    for p in py_files:
        try:
            tree = ast.parse(p.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        if (
            tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            out.append(
                (
                    "no-top-docstring",
                    _rel(p),
                    "delete the leading triple-quoted string; if useful, move it to a `#` comment",
                )
            )
    return out


def check_file_size_cap(py_files: list[Path]) -> list[tuple[str, str, str]]:
    # Rule file-size-cap: no .py file in src/, app.py, cli.py > MAX_PY_LINES.
    out: list[tuple[str, str, str]] = []
    for p in py_files:
        rel = _rel(p)
        if not (rel.startswith("src/") or rel == "app.py" or rel == "cli.py"):
            continue
        n = len(p.read_text().splitlines())
        if n > MAX_PY_LINES:
            out.append(
                (
                    "file-size-cap",
                    rel,
                    f"file is {n} lines (cap {MAX_PY_LINES}); split along clear seams",
                )
            )
    return out


def check_no_print_in_src(py_files: list[Path]) -> list[tuple[str, str, str]]:
    # Rule no-print-in-src: src/ must not call print(...). Use logging.
    out: list[tuple[str, str, str]] = []
    for p in py_files:
        if not _rel(p).startswith("src/"):
            continue
        try:
            tree = ast.parse(p.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                out.append(
                    (
                        "no-print-in-src",
                        f"{_rel(p)}:{node.lineno}",
                        "replace print(...) with logging.getLogger(__name__).info(...)",
                    )
                )
                break  # one finding per file is enough to drive a fix
    return out


def check_no_compound_cd(shell_files: list[Path]) -> list[tuple[str, str, str]]:
    # Rule no-compound-cd: `cd` must not be chained with &&, ;, |.
    out: list[tuple[str, str, str]] = []
    for p in shell_files:
        try:
            text = p.read_text()
        except UnicodeDecodeError:
            continue
        for i, raw in enumerate(text.splitlines(), start=1):
            line = raw.strip()
            if line.startswith("#") or "cd " not in line:
                continue
            # Look for a `cd ...` followed by &&, ;, | on the same line.
            idx = line.find("cd ")
            tail = line[idx + 3 :]
            if any(op in tail for op in ("&&", ";", "|")):
                out.append(
                    (
                        "no-compound-cd",
                        f"{_rel(p)}:{i}",
                        "split the chain into separate commands; never chain `cd` with `&&`, `;`, or `|`",
                    )
                )
    return out


# --- Main ------------------------------------------------------------------


def main() -> int:
    py_files = _iter_python_files()
    shell_files = _iter_shell_files()

    findings: list[tuple[str, str, str]] = []
    findings += check_no_top_docstring(py_files)
    findings += check_file_size_cap(py_files)
    findings += check_no_print_in_src(py_files)
    findings += check_no_compound_cd(shell_files)

    baseline = _load_baseline()
    live: list[tuple[str, str, str]] = []
    for rule, location, hint in findings:
        # Match on (rule, file-path-without-line-suffix).
        path_only = location.split(":", 1)[0]
        if (rule, path_only) in baseline:
            continue
        live.append((rule, location, hint))

    if not live:
        print("conventions lint: clean")
        return 0

    print(f"conventions lint: {len(live)} violation(s) (see {DOCS_URL})\n")
    for rule, location, hint in live:
        print(f"  [{rule}] {location}")
        print(f"    fix: {hint}")
        print(f"    rule: {DOCS_URL}#{rule}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
