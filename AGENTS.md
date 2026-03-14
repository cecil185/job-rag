# Agent Instructions

This project uses **bd** (beads) for issue tracking. Run `bd onboard` to get started.

## Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work atomically
bd close <id>         # Complete work
```

**Before ending a session:** You MUST push and create a PR. See [Landing the Plane](#landing-the-plane-session-completion) — work is NOT complete until `git push` and `gh pr create` succeed.

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var

<!-- BEGIN BEADS INTEGRATION -->
## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- Dependency-aware: Track blockers and relationships between issues
- Version-controlled: Built on Dolt with cell-level merge
- Agent-optimized: JSON output, ready work detection, discovered-from links
- Prevents duplicate tracking systems and confusion

### Quick Start

**Check for ready work:**

```bash
bd ready --json
```

**Create new issues:**

```bash
bd create "Issue title" -d "Description" -t bug|feature|task -p 0-4 --json
# Or: --description="Detailed context"
# Types: bug, feature, task, epic, chore. Priority: 0 (critical) to 4 (backlog).
# Output includes "id" (e.g. job-rag-qmz); note it for linking dependencies.
```

**Dependencies** (blocker must exist first; add links after creating the blocked issue):

```bash
bd dep add <blocked-id> <blocker-id>   # <blocked-id> is blocked by <blocker-id>
bd dep tree <id>                       # Show dependency tree
bd dep cycles                          # Detect circular dependencies
```

Create parent issues first, then create children, then run `bd dep add` for each (blocked, blocker) pair.

**Claim and update:**

```bash
bd update <id> --claim --json
bd update bd-42 --priority 1 --json
```

**Complete work:**

```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task atomically**: `bd update <id> --claim`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   - `bd create "Found bug" --description="Details about what was found" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`

### Auto-Sync

bd automatically syncs with git:

- Exports to `.beads/issues.jsonl` after changes (5s debounce)
- Imports from JSONL when newer (e.g., after `git pull`)
- No manual export/import needed!

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` to get new work
- ❌ Do NOT work on an issue if claiming it failed
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems

For more details, see README.md and docs/QUICKSTART.md.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until **both** `git push` and **PR creation** succeed.

**Session-end checklist (run in order):**

1. **File issues for remaining work** — Create issues for anything that needs follow-up.
2. **Run quality gates** (if code changed) — Tests, linters, builds.
3. **Update issue status** — Close finished work, update in-progress items.
4. **Push to remote** (required):
   ```bash
   git pull --rebase
   git push
   git status   # MUST show "up to date with origin"
   ```
5. **Create PR** (required): After push succeeds, open a PR so the work is reviewable.
   ```bash
   gh pr create --base main --head "$(git branch --show-current)" --title "Your PR title" --body "Summary of changes (see below)"
   ```
   PR body must include:
   - **What was done** — max 3 bullets.
   - **Verification** — tests run, new tests added (if any).
6. **Clean up** — Clear stashes, prune remote branches.
7. **Verify** — All changes committed, pushed, and PR created.
8. **Hand off** — Brief context for next session.

**CRITICAL RULES:**
- Work is NOT complete until **both** `git push` and `gh pr create` have been run successfully.
- NEVER stop after closing a bead without pushing and creating the PR.
- NEVER say "ready to push when you are" — you must push and create the PR.
- If push or PR fails, fix and retry until both succeed.

<!-- END BEADS INTEGRATION -->
Use 'bd' for task tracking
Develop in docker containers using Makfile commands