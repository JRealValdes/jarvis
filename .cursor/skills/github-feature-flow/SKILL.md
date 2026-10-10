---
name: github-feature-flow
description: >-
  Create and maintain Jarvis GitHub issues, feature branches named
  feature/X-slug, and PRs into main with titles ending in (#X). Use when
  starting work from main, creating or updating an issue for a feature,
  opening a feature branch, linking a PR to an issue, or when the user asks
  to start the issue/branch/PR workflow.
---

# GitHub feature flow (Jarvis)

Issue + feature branch + PR into `main`. All GitHub text in **English**.

## Start from `main` (propose first)

If the user asks for a change while on `main`, **propose** then wait for confirmation:

1. Create GitHub issue
2. Create branch `feature/<N>-<slug>` from up-to-date `main`
3. Develop on that branch

Do not create the issue or branch until they agree (unless they already ordered the full flow).

## 1. Create the issue

```bash
gh issue create --title "<English title>" --body-file <path-or-heredoc>
```

Body: short context, goal, checklist. English only.

Record the issue number `N` from the URL or `gh issue list`.

## 2. Create the branch

Slug: lowercase kebab-case from the issue title; drop punctuation; keep it short.

```bash
git fetch origin
git checkout main
git pull origin main
git checkout -b feature/<N>-<slug>
git push -u origin HEAD
```

Prefer linking development in GitHub when available:

```bash
gh issue develop <N> --name feature/<N>-<slug> --checkout
```

If `gh issue develop` is unavailable, the branch name + PR link is enough.

## 3. Develop

- Commit with Conventional Commits; only when the user asks to commit.
- If scope grows and it **materially** helps tracking, update the issue body (checklist / notes) via `gh issue edit <N> --body-file ...` **without asking**. Skip trivial or redundant edits.

## 4. Open a PR (only if the user asks)

```bash
gh pr create --title "<English summary> (#<N>)" --body-file <file>
```

**Title rule:** the title must end with a space and `(#N)` — e.g. `Unify MCP tool session lifecycle (#6)`.

**Body (English), include:**

```markdown
## Summary
- …

Closes #<N>.

## Test plan
- [ ] …
```

`Closes #<N>` associates the PR with the issue and closes it on merge. Use `Refs #<N>` instead if the PR is partial and must not close the issue.

Push with `-u` if the branch has no upstream yet.

## Checklist

```
- [ ] Issue exists (#N), English
- [ ] Branch name is feature/<N>-<slug>
- [ ] Work landed on that branch
- [ ] Issue body updated only when useful
- [ ] PR title ends with (#N); body links Closes/Refs #N
```
