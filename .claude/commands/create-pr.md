---
name: create-pr
description: Create a pull request for the current branch. Runs all mandatory agent gates (secrets-auditor, ansible-specialist, docs-quality-reviewer) before opening the PR. Ensures CHANGELOG is updated, molecule tests exist, and CI covers all six distros.
model: sonnet
---

# Create Pull Request — Ansible

## Pre-flight checks

Before creating the PR, run these mandatory gates in order. Stop if any gate fails.

1. **Verify branch name** includes a Jira ticket key (e.g. `feat/BOOT-42-add-prometheus-role`). If missing, ask the user for the ticket key before proceeding.

2. **Run `pre-commit run --all-files`** in the `ansible/` directory. Fix any failures before continuing.

3. **Run the secrets-auditor agent** on all changed files. Verdict must be SAFE TO COMMIT. If BLOCKED, stop and fix.

4. **Run the ansible-specialist agent** on all changed Ansible files. All ❌ issues must be resolved.

5. **Run the docs-quality-reviewer agent** on any changed README or documentation files. Verify branding matches (axonops-* = AxonOps, otherwise Digitalis.io).

6. **Verify CHANGELOG.md** has an entry under `[Unreleased]` covering all changes in this branch.

7. **Verify molecule tests** exist for any new or modified role behaviour.

8. **Verify CI pipeline** covers all six required platforms: `rockylinux9`, `rockylinux10`, `ubuntu2204`, `ubuntu2404`, `debian12`, `debian13`.

## Create the PR

Once all gates pass:

1. Determine the VCS hosting from the git remote:
   - If Bitbucket: use `git push` + Bitbucket API or direct URL
   - If GitHub: use `gh pr create`

2. **PR title** must include the Jira ticket key: `feat(BOOT-42): <short description>`

3. **PR body** must include:
   - Summary of changes (2-3 bullet points)
   - Link to the Jira ticket
   - Test plan: which molecule scenarios were run, on which platforms
   - Checklist:
     - [ ] `pre-commit run --all-files` passes
     - [ ] `ansible-lint` passes (production profile)
     - [ ] Molecule tests pass on all six platforms
     - [ ] CHANGELOG.md updated
     - [ ] README updated (if applicable)
     - [ ] secrets-auditor: SAFE TO COMMIT

4. Show the PR URL to the user when done.
