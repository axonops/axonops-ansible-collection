---
name: create-github-issue
description: Create a GitHub issue for Ansible work. Only use when the target repo is hosted on GitHub. Runs the issue-writer agent first to produce a complete, implementation-ready issue, then files it via `gh issue create`.
model: sonnet
---

# Create GitHub Issue — Ansible

> **Important**: Only use this for repos hosted on GitHub. For Bitbucket repos, use `/create-jira-ticket` instead.

## Workflow

1. **Run the issue-writer agent** first. Pass the user's description as input. The agent will:
   - Draft a complete issue with: summary, background, requirements, acceptance criteria, testing requirements, documentation requirements, dependencies, and labels
   - Ask one round of clarifying questions if the request is ambiguous
   - Show the full draft and wait for user approval

2. **Check for duplicates** — search existing open issues in the target repo:
   ```
   gh issue list --state open --search "<keywords from summary>"
   ```
   If potential duplicates exist, show them and ask the user to confirm before proceeding.

3. **Create the issue** using `gh issue create`:
   - Title: the Summary line from the issue-writer output
   - Body: the full issue-writer output (Background through Labels)
   - Labels: from the Labels line (create missing labels if needed)

4. **Show the issue URL** to the user.

## Ansible-specific requirements

The issue-writer agent enforces these for Ansible work:
- Testing requirements must name molecule scenarios and all six platforms (`rockylinux9`, `rockylinux10`, `ubuntu2204`, `ubuntu2404`, `debian12`, `debian13`)
- Documentation requirements must name specific files (role README, CHANGELOG)
- New role issues must specify target OS, service management, defaults variables, and galaxy dependencies
- Bug reports must include reproduction steps, expected vs actual behaviour, and environment details

## Rules

- Never create an issue without running the issue-writer agent first
- Never create an issue without user approval of the draft
- Never skip the duplicate check
- The issue must be complete enough for a mid-level engineer to implement without follow-up questions
