---
name: git-pushing
description: "Stage all changes, create a conventional commit, and push to the remote branch. Use when explicitly asks to push changes (\"push this\", \"commit and push\"), mentions saving work to remote (\"save to github\", \"push to remote\"), or completes a feature and wants to share it."
risk: critical
source: community
date_added: "2026-02-27"
---

# Git Push Workflow

Stage all changes, create a conventional commit, and push to the remote branch.

## When to Use
Automatically activate when the user:

- Explicitly asks to push changes ("push this", "commit and push")
- Mentions saving work to remote ("save to github", "push to remote")
- Completes a feature and wants to share it
- Says phrases like "let's push this up" or "commit these changes"

## Workflow

**ALWAYS use the script** - do NOT use manual git commands:

```bash
bash skills/git-pushing/scripts/smart_commit.sh
```

With custom message:

```bash
bash skills/git-pushing/scripts/smart_commit.sh "feat: add feature"
```

## Commit Generation Process

Before running the script:

1. Analyze code changes (git diff)
2. Identify:
   - feature / fix / refactor
   - affected module (e.g., IDE, curriculum, agent)
   - intent of change
3. Generate commit message based on analysis
4. Then run script with generated message

### Scope Rules (Project-Specific)

- ide: Monaco editor / coding environment
- curriculum: AI curriculum generation
- agent: LangChain / analysis logic
- rag: retrieval system
- dashboard: teacher analytics

## AI Collaboration Logging

For each commit:

- Save:
  - generated commit message
  - user correction (if any)
  - final message

Path:
docs/ai-review-log.md
Script handles: staging, conventional commit message, Claude footer, push with -u flag.