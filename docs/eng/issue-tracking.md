# Issue Tracking

All work is tracked in the **Linear project "Job RAG"**.

## Tools

Use the Linear MCP tools (`mcp__linear-server__*`). Reference skills: `linear`, `create-linear-ticket`.

## Conventions

- Every non-trivial change has a Linear ticket. Trivial = doc typo, lint baseline tweak, etc.
- Bugs discovered during work get a ticket of their own — don't fold unrelated fixes into an in-flight PR.
- Ticket statuses: `Backlog` → `Todo` → `In Progress` → `In Review` → `Done`.
- The PR description must reference the Linear ticket ID. The Linear ticket must link back to the PR.

## Branches

`<short-slug>` off `main`. Optional prefix `agent-<n>-` for parallel agent worktrees.
