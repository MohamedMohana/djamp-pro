# DJAMP PRO Maintainer Playbook

This playbook defines how to run DJAMP PRO as a professional open-source project focused on strong macOS developer experience and steady contributor growth.

## Core Operating Rules

- Use branch + PR workflow for all changes; avoid direct commits to `main`.
- Keep PRs small, scoped, and linked to issues.
- Require green CI and CodeQL before merge.
- Preserve contributor momentum with fast triage and clear labels.

## Weekly Rhythm

1. Triage open issues (apply priority + area labels).
2. Review open PRs and unblock contributors quickly.
3. Merge ready PRs and update docs in the same cycle.
4. Check release draft and ship a version on cadence.
5. Open a weekly maintainer checklist issue from template and track completion.

## Label Taxonomy

- Type: `bug`, `feature`, `enhancement`, `chore`, `documentation`
- Area: `area:desktop`, `area:controller`, `area:helper`, `area:ci`
- Priority: `priority:p0`, `priority:p1`, `priority:p2`
- Queue state: `needs-triage`, `help wanted`, `good first issue`, `release`

## Release Management

- Keep Release Drafter enabled on every `main` push.
- Use semantic version tags only: `vMAJOR.MINOR.PATCH`.
- Publish regularly (target every 2-3 weeks for active development).
- Include short, user-focused release notes with install and upgrade notes.
- Keep one monthly roadmap issue open (`roadmap: YYYY-MM`) as execution anchor.

## Contributor Growth Tactics

- Keep at least 5 active `good first issue` items.
- Add reproduction steps and acceptance criteria to issues.
- Thank and review first-time contributors quickly.
- Convert repeated questions into docs updates.

## GitHub Achievements Strategy

Current profile achievements can grow naturally through healthy project operations:

- `Pull Shark`: merge more PRs (including external contributions). Use PR-first workflow for all work.
- `Quickdraw`: resolve clearly invalid/duplicate issues quickly with good explanations.
- `YOLO`: avoid force-pushes and direct production-like actions unless required.

Best practice: treat achievements as a side effect of good maintainer habits, not the primary goal.

## Security and Privacy

- Never commit local machine-specific scripts, certs, or absolute private paths.
- Rotate any secret/cert if it was ever committed.
- If sensitive data was previously tracked, purge history and contact GitHub Support for cached object purge.
