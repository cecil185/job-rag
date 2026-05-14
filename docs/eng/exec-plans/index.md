# Execution Plans

First-class plans for non-trivial work. Each plan is a short markdown file checked into the repo so agents have a durable, versioned record of intent and progress.

```
exec-plans/
├── index.md      (this file)
├── active/       (in-flight)
└── completed/    (merged; kept for reference)
```

## Lifecycle

1. **Create** in `active/<slug>.md` when starting non-trivial work.
2. **Update** as you make progress — append decisions, blockers, and discoveries.
3. **Move** to `completed/` when the PR merges.

## Template

```markdown
# <Title> — <Linear ID>

**Status:** Active | Blocked | Done
**Owner:** <name or agent>
**Linear:** https://linear.app/...

## Goal
One paragraph. What does "done" look like?

## Approach
Three to five bullets. The shape of the work, not the line-by-line plan.

## Decisions
- [date] decided X because Y.

## Open questions
- ...

## Progress
- [date] ...
```

## Index

_(empty — entries added automatically by linking from `active/` and `completed/`)_
