#!/usr/bin/env bash
# Doc-gardener: scans docs/eng/ for drift against the actual repo and opens a PR
# if anything is stale. Idempotent and safe to run unattended.
#
# Drift signals checked:
#   1. CLAUDE.md or docs/eng/ links to a path that no longer exists.
#   2. docs/eng/quality-gates.md references `just` recipes that no longer exist.
#   3. docs/eng/architecture.md "Layout" table mentions a top-level path that no
#      longer exists.
#
# When drift is found the script:
#   - writes a report to gardening-report.md (gitignored, recreated each run),
#   - if $GARDEN_OPEN_PR=1, prompts an LLM (claude or codex CLI) to fix the docs
#     and opens a PR via gh.
#
# Run locally:  bash scripts/gardening/garden_docs.sh
# Run in CI:    GARDEN_OPEN_PR=1 bash scripts/gardening/garden_docs.sh
set -euo pipefail

cd "$(dirname "$0")/../.."
ROOT="$(pwd)"
REPORT="$ROOT/gardening-report.md"
: > "$REPORT"

note() { printf -- "- %s\n" "$1" >> "$REPORT"; }

section() { printf "\n## %s\n\n" "$1" >> "$REPORT"; }

drift_found=0

# --- 1. Broken markdown links to local paths -------------------------------

section "Broken local links in CLAUDE.md and docs/eng/"

scan_links() {
  local file="$1"
  python3 - "$file" <<'PY' >> "$REPORT" || true
import re, sys, pathlib
p = pathlib.Path(sys.argv[1])
root = pathlib.Path(".").resolve()
text = p.read_text()
# Match markdown links like (path/to/file.md) or (path/to/file.md#anchor)
# Skip URLs (http, mailto) and pure anchors.
for m in re.finditer(r"\]\((?!https?:|mailto:|#)([^)#\s]+)(#[^)]*)?\)", text):
    target = m.group(1)
    # Resolve relative to the file's directory.
    resolved = (p.parent / target).resolve()
    if not resolved.exists():
        rel = resolved.relative_to(root) if resolved.is_relative_to(root) else resolved
        print(f"- {p.relative_to(root)} → missing `{target}` (resolved {rel})")
PY
}

scan_links "$ROOT/CLAUDE.md"
for f in $(find "$ROOT/docs/eng" -name "*.md"); do
  scan_links "$f"
done

if grep -q "^- " "$REPORT" 2>/dev/null; then drift_found=1; fi

# --- 2. just recipe references in quality-gates.md -------------------------

section "Stale \`just\` recipe references in docs/eng/quality-gates.md"

if command -v just >/dev/null 2>&1; then
  RECIPES=$(just --summary --justfile "$ROOT/justfile" 2>/dev/null | tr ' ' '\n' | sort -u || true)
  python3 - "$RECIPES" <<'PY' >> "$REPORT" || true
import re, sys, pathlib
recipes = set(sys.argv[1].split())
doc = pathlib.Path("docs/eng/quality-gates.md").read_text()
mentioned = set(re.findall(r"`just\s+([a-z][a-z0-9-]*)`", doc))
missing = sorted(mentioned - recipes)
for r in missing:
    print(f"- quality-gates.md references `just {r}` but no such recipe exists")
PY
fi

# --- 3. Top-level paths in architecture.md ---------------------------------

section "Missing top-level paths referenced in docs/eng/architecture.md"

python3 - <<'PY' >> "$REPORT" || true
import re, pathlib
arch = pathlib.Path("docs/eng/architecture.md").read_text()
# Heuristic: any backticked path-looking token in the Layout table.
for m in re.finditer(r"\| `([^`]+)` \|", arch):
    token = m.group(1).split()[0].rstrip("/")
    # Skip parenthetical notes like "(rest)" or "(legacy)".
    if token.startswith("("):
        continue
    if not pathlib.Path(token).exists():
        print(f"- architecture.md mentions `{token}` which no longer exists")
PY

# --- Summary ---------------------------------------------------------------

if grep -q "^- " "$REPORT"; then
  echo "doc-gardener: drift detected — see $REPORT"
  cat "$REPORT"
  drift_found=1
else
  echo "doc-gardener: docs/eng/ is in sync with the repo"
  exit 0
fi

# --- Optional: open a PR ---------------------------------------------------

if [[ "${GARDEN_OPEN_PR:-0}" != "1" ]]; then
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "doc-gardener: gh CLI not available; skipping PR creation"
  exit 1
fi

BRANCH="gardener/docs-$(date +%Y%m%d-%H%M%S)"
git checkout -b "$BRANCH"

# Hand the report to whichever agent CLI is available and let it fix docs.
if command -v claude >/dev/null 2>&1; then
  AGENT="claude"
  PROMPT="The doc-gardener detected the drift below. Fix only docs/eng/ and CLAUDE.md. Do not modify code. Make minimal, targeted edits.\n\n$(cat "$REPORT")"
  printf "%b" "$PROMPT" | claude -p "$PROMPT" || true
elif command -v codex >/dev/null 2>&1; then
  AGENT="codex"
  codex exec "Fix the documentation drift listed in gardening-report.md. Only edit docs/eng/ and CLAUDE.md." || true
else
  echo "doc-gardener: no agent CLI (claude/codex) available; opening PR with report only"
  AGENT="manual"
fi

git add -A
if git diff --cached --quiet; then
  echo "doc-gardener: no edits were produced; aborting PR"
  exit 1
fi

git commit -m "docs: gardener cleanup ($AGENT)

$(cat "$REPORT")
"
git push -u origin "$BRANCH"
gh pr create \
  --title "docs: gardener cleanup" \
  --body "$(cat "$REPORT")"
