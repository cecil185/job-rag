# Engineering Knowledge Base

The system of record for how this repo is built and how agents work in it. Optimized for **agent legibility**: anything not captured here effectively does not exist to an agent in a fresh session.

Structure:

```
docs/eng/
├── README.md             # this file
├── architecture.md       # modules, data flow, layers
├── conventions.md        # golden principles + style rules (mechanically enforced)
├── quality-gates.md      # just/ruff/mypy/pre-commit/CI
├── agents.md             # how Codex/Claude agents work in this repo
├── issue-tracking.md     # Linear conventions
├── design-docs/
│   └── index.md          # ADRs, design notes
└── exec-plans/
    ├── index.md
    ├── active/
    └── completed/
```

## Rules for this directory

- Every file is short, scoped, and cross-linked. No monoliths.
- Prefer adding a new short file over growing an existing one past ~300 lines.
- Knowledge that becomes false must be corrected or deleted, never left to rot. The doc-gardener (`scripts/gardening/garden_docs.sh`) opens PRs against stale docs.
- If a convention is important enough to enforce, encode it in `scripts/lint_conventions.py` and reference the rule ID from `conventions.md`.
