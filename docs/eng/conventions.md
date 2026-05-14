# Conventions

Golden principles for this repo. The hard rules are **mechanically enforced** by `scripts/lint_conventions.py` (run via `just lint` and pre-commit). Each rule has a stable ID — the lint error message references it so agents can self-correct without a human.

## Hard rules (lint-enforced)

### `no-top-docstring`
**Rule:** `.py` files must not begin with a `"""..."""` string literal.
**Why:** Module-level docstring banners add visual noise without conveying information that the code itself doesn't already. Use a one-line `#` comment if the *why* is non-obvious. The function/class docstrings inside the module are unaffected.
**Fix:** Delete the leading triple-quoted string. If the content is genuinely useful, move it to a `#`-prefixed comment under the imports, or to a doc in `docs/eng/`.
**Baseline:** Existing violators are listed in `.lint-baseline.txt`. New code must pass clean.

### `no-compound-cd`
**Rule:** Shell scripts, Makefile, and justfile recipes must not chain `cd` with `&&`, `;`, `|`, or any other operator. Each `cd` is its own command.
**Why:** Compound `cd` chains hide working-directory bugs that only surface in CI or fresh worktrees. Isolated `cd` calls are explicit and reviewable.
**Fix:** Split the chain into separate lines, or use a shell `pushd`/`popd` block, or invoke the target with an absolute path.

### `file-size-cap`
**Rule:** No `.py` file in `src/`, `app.py`, or `cli.py` may exceed **800 lines**.
**Why:** Long files are agent-hostile: hard to load fully into context, hard to refactor without unrelated diffs, often a sign that responsibilities should be split.
**Fix:** Split the file along clear seams (e.g. one class per file, or one logical step of the pipeline per file).
**Baseline:** Existing violators are listed in `.lint-baseline.txt`.

### `no-print-in-src`
**Rule:** `src/` code must not call `print(`. Use `logging` instead.
**Why:** `print` bypasses the configured logger, makes output unstructured, and tends to be left behind from debugging.
**Fix:** Replace with `logging.getLogger(__name__).info(...)` (or `.debug`/`.warning` as appropriate).

## Soft rules (style)

These are conventions, not gates. Follow them; reviewers may push back if not.

- Comment sparingly — prefer code that expresses intent on its own.
- Don't repeat the same point twice in a response or in a comment.
- Never reformat whitespace or style in existing code unless the change requires it.
- Never delete or modify tests without explicit per-file approval.
- When working a Linear ticket, only modify files related to that ticket; revert unrelated drift.

## Why we enforce mechanically

Per the *Humans steer, agents execute* model: rules that exist only in prose rot, get pattern-matched into oblivion, and don't survive context resets. Rules encoded in `scripts/lint_conventions.py` survive every agent run because they fail CI with a remediation message pointing right back here.

When you add a new rule:

1. Pick a stable kebab-case ID.
2. Implement the check in `scripts/lint_conventions.py`.
3. Have the lint error message print the rule ID and a one-line fix.
4. Document it in this file under "Hard rules" with the same ID.
5. If there are existing violators that can't be cleaned in the same PR, add them to `.lint-baseline.txt`.
