# Repository workflow

This repository uses one canonical Git branch: `main`.

- Do not create local or remote feature branches.
- Do not open pull requests for repository work.
- Make scoped commits directly on `main`.
- After the relevant checks pass, push commits directly to `origin/main`.
- Stage files explicitly and never include unrelated working-tree changes in a
  commit.
- If branch protection or permissions reject a direct push, report the blocker;
  do not work around it by creating a branch or pull request.

These rules apply to all automated agents and repository maintenance sessions.
