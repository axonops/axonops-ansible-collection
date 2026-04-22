---
name: create-jira-ticket
description: Create a Jira ticket for Ansible work. This is the default for Bitbucket-hosted repos. Runs the issue-writer agent first to produce a complete, implementation-ready ticket, checks for duplicates via atlassian:triage-issue, then files via Atlassian MCP tools.
model: sonnet
---

# Create Jira Ticket — Ansible

> **Default tracker**: Bitbucket repos use Jira for issue tracking. Use this command for all Bitbucket-hosted projects.

## Workflow

1. **Run the issue-writer agent** first. Pass the user's description as input. The agent will:
   - Draft a complete ticket with: summary, background, requirements, acceptance criteria, testing requirements, documentation requirements, dependencies, and labels
   - Ask one round of clarifying questions if the request is ambiguous
   - Show the full draft and wait for user approval

2. **Check for duplicates** — run the `atlassian:triage-issue` skill with the summary and key terms. If potential duplicates exist, show them and ask the user to confirm before proceeding.

3. **Identify the Jira project** — ask the user for the project key if not obvious from context (e.g. BOOT for bootstrap).

4. **Create the ticket** using the Atlassian MCP tools:
   - Use `mcp__atlassian__createJiraIssue` to create the ticket
   - Summary: the Summary line from the issue-writer output
   - Description: the full issue-writer output (Background through Labels), formatted in Jira markup
   - Issue type: Task, Bug, or Story as appropriate
   - Labels: from the Labels line

5. **Show the ticket key and URL** to the user (e.g. `BOOT-42`).

## Ansible-specific requirements

The issue-writer agent enforces these for Ansible work:
- Testing requirements must name molecule scenarios and all six platforms (`rockylinux9`, `rockylinux10`, `ubuntu2204`, `ubuntu2404`, `debian12`, `debian13`)
- Documentation requirements must name specific files (role README, CHANGELOG)
- New role issues must specify target OS, service management, defaults variables, and galaxy dependencies
- Bug reports must include reproduction steps, expected vs actual behaviour, and environment details
- Security findings must include vulnerability class, affected file, severity, and specific remediation

## Rules

- Never create a ticket without running the issue-writer agent first
- Never create a ticket without user approval of the draft
- Never skip the duplicate check via `atlassian:triage-issue`
- The ticket must be complete enough for a mid-level engineer to implement without follow-up questions
- Never create GitHub issues for Bitbucket-hosted repos — always use Jira
