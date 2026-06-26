# Branch protection & repository security settings

The workflows in `.github/workflows/` only *report* status. They become real **merge
gates** once the branch is protected and the checks are marked **required**. Configure the
following once, in the GitHub UI or via API. (These are repo-admin settings; they live
here as documentation because they cannot be set from a workflow file.)

## 1. Protect the default branch (`master`, and `develop` if used)

**Settings → Branches → Add branch ruleset** (or *Add classic branch protection rule*):

- ✅ **Require a pull request before merging**
  - ✅ Require at least **1 approval**
  - ✅ Dismiss stale approvals on new commits
  - ✅ Require review from **Code Owners** (see `CODEOWNERS`, optional)
- ✅ **Require status checks to pass before merging**
  - ✅ Require branches to be **up to date** before merging
  - Mark these checks as **required** (names come from the job `name:` fields):
    - `tests (py3.11)`, `tests (py3.12)`
    - `build (sdist + wheel)`
    - `ruff`
    - `mypy`
    - `eslint`
    - `dependency review`
    - `gitleaks`
    - `pip-audit`
    - `npm-audit`
    - `analyze (python)`, `analyze (javascript)`  *(CodeQL)*
- ✅ **Require conversation resolution before merging**
- ✅ **Require linear history** (no merge commits / force-pushes to the branch)
- ✅ **Do not allow bypassing the above** (applies to admins too)
- ✅ **Block force pushes**

> Status-check names appear in the "Require status checks" picker only **after** each
> workflow has run at least once (open a throwaway PR to populate the list).

## 2. Native code-security features

**Settings → Code security and analysis** — enable:

- ✅ **Dependency graph** (required for Dependabot + `dependency-review-action`)
- ✅ **Dependabot alerts** and **Dependabot security updates** (config in `.github/dependabot.yml`)
- ✅ **Secret scanning**
- ✅ **Push protection** — blocks commits containing detected secrets *before* they land,
  complementing the historical `gitleaks` job in `security.yml`
- ✅ **CodeQL / code scanning** (the `codeql.yml` workflow feeds this)

## 3. Secrets used by CI

No secrets are required for the current pipelines (everything runs on the built-in
`GITHUB_TOKEN`). If SonarCloud/Codecov are added later, store their tokens under
**Settings → Secrets and variables → Actions**, never in the repo.

## 4. Action pinning policy

All third-party actions are pinned to a full commit **SHA** (with the tag in a trailing
comment) for supply-chain safety. Dependabot's `github-actions` ecosystem opens PRs that
bump the SHA + comment together; review and merge those like any other dependency update.
