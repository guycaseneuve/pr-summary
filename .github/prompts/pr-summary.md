# PR Description & Changelog Composer — Prompt

Generate a PR description and changelog fragment for the pull request below.

## Repo Context

This repository contains:
- **demo-app/**: An Express.js application (Node.js) with intentional security vulnerabilities for testing
- **.github/workflows/**: CI/CD pipelines (CodeQL, security-autofix, PR summary, dependabot-autofix, incident postmortem)
- **.github/prompts/**: AI prompt templates for each workflow
- **.github/skills/**: AI skill/persona definitions for each workflow
- **.github/scripts/**: Utility scripts (aggregate_findings.py)

Key conventions:
- Security fixes go to `security/autofix-*` branches
- Commit messages follow conventional commits: `feat:`, `fix:`, `security:`, `deps:`
- PRs targeting `main` trigger CodeQL + PR summary

## Instructions

1. **Extract the CMT/JIRA ID** from the source branch name using the rules defined in SKILL.md.
2. **Output the `Title` line first**, formatted as: `Title: CMT-XXXXX: Short descriptive title`
   - The output MUST begin with `Title:` on the first line.
   - If no CMT ID is found in the branch, output the title without a prefix and add `(no CMT id found in branch)` on the next line.
3. **Then output each section** in this exact order:

## Summary

One-paragraph summary of the change and intent.

## Changes identified

Grouped list of changed files/areas with short bullet summaries. Use subheadings for files or components:

### `path/to/file.yml`

- Brief bullet describing the modification.

### `another/file`

- Bullet points showing specific edits.

## Why this matters

- Short bullets describing risk, benefits, and impact.

## Validation notes

- Summary of steps taken to validate the change (tests run, files reviewed, constraints checked).

---

## Changelog fragment

After the PR description sections above, output a changelog fragment block suitable for appending to `CHANGELOG.md`. Format:

```
### [Type] - YYYY-MM-DD

- CMT-XXXXX: Short description of the change.
```

Where `[Type]` is one of: `Added`, `Changed`, `Fixed`, `Removed`, `Security`.

---

## PR Context

The following data is provided for analysis:

- **Source branch**: `{BRANCH}`
- **PR Title**: `{PR_TITLE}`
- **Changed files**: see below
- **Commit messages**: see below
- **Code diff**: see below (may be truncated)
