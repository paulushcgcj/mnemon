---
type: Guide
title: Release Setup Guide
description: One-time setup for PyPI OIDC Trusted Publishing and GitHub Actions.
tags: [release, pypi, oidc, setup]
---

# Release Setup Guide

One-time setup per project. Day-to-day release → [Release Process](/processes/release.md).

## Setup Scope

| Component | Purpose |
|---|---|
| PyPI Account + 2FA | Own `mnemon-mcp` package. |
| PyPI Trusted Publishing | GitHub Actions publish via OIDC. No API keys. |
| GitHub Actions Environment | Scope workflow. Add approval gates. |
| TestPyPI Account | Sandbox E2E dry run. |
| Tag Protection | Block non-maintainer tag push. |

## 1. PyPI Account

1. Open [pypi.org/account/register](https://pypi.org/account/register/).
2. Fill details.
3. Verify email.

## 2. PyPI 2FA

PyPI require 2FA for Trusted Publishing.

1. **Account settings** → **Two factor authentication**.
2. **Add 2FA with authentication application**.
3. Scan QR. Enter code.
4. Save recovery codes.

## 3. TestPyPI Account (Optional)

Isolated staging.

1. Open [test.pypi.org/account/register](https://test.pypi.org/account/register/).
2. Repeat account + 2FA setup.

## 4. PyPI Trusted Publishing

Trust GitHub Actions `publish-pypi.yml` in `paulushcgcj/mnemon`.

### New Project (No PyPI package yet)

1. [pypi.org](https://pypi.org) → **Your projects** → **Publishing**.
2. **Add a new pending publisher**.
3. Exact values:
   - PyPI Project Name: `mnemon-mcp`
   - Owner: `paulushcgcj`
   - Repository name: `mnemon`
   - Workflow name: `publish-pypi.yml`
   - Environment name: `pypi`
4. **Add**. Active on first publish.

### Existing Project

1. [pypi.org](https://pypi.org) → **Your projects** → `mnemon-mcp` → **Publishing**.
2. **Add a new publisher**.
3. Exact values:
   - Owner: `paulushcgcj`
   - Repository name: `mnemon`
   - Workflow name: `publish-pypi.yml`
   - Environment name: `pypi`
4. **Add**.

## 5. TestPyPI Trusted Publishing (Optional)

Repeat Step 4 on [test.pypi.org](https://test.pypi.org).
Workflow name: `publish-testpypi.yml` (if exist).

## 6. GitHub Actions Environment

`publish-pypi.yml` require `pypi` environment.

1. GitHub → **Settings** → **Environments**.
2. **New environment** → `pypi`.
3. **Configure environment**.
4. (Optional) **Required reviewers** → Add maintainer.
5. **Save**.
6. NO secrets. OIDC handle auth.

## 7. Tag Protection (Optional)

Block accidental `v*` push.

1. GitHub → **Settings** → **Rules** → **Rulesets**.
2. **New branch ruleset** → Name: `Release tags`.
3. Target: **Tags**.
4. Target tags: **Include by pattern** → `v*`.
5. Rules: **Restrict deletions**, **Restrict creations**.
6. Bypass list: Add maintainers + CI.
7. **Create**.

## 8. Verify Setup (Dry Run)

```bash
git clone https://github.com/paulushcgcj/mnemon.git
cd mnemon
uv sync
uv run mnemon --help

uv build
uv tool install check-wheel-contents
uv tool run check-wheel-contents dist/*.whl

uv publish --dry-run
```
No errors → ready.

## 9. First Release

See [Release Process](/processes/release.md).

```bash
git checkout main && git pull
git add pyproject.toml
git commit -m "chore: bump version to 0.1.0"
git push

git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| 403 Forbidden | PyPI Trusted Publisher mismatch | Match Owner/Repo/Workflow/Env exactly. |
| Environment 'pypi' not found | Missing GitHub Env | Create `pypi` in GitHub Settings. |
| Workflow trigger, no publish | GitHub Release draft | Publish release in GitHub UI. |
| Missing files in wheel | `pyproject.toml` missing includes | Add to `[tool.hatch.build.targets.wheel]`. |
| PyInstaller crash | Missing hidden imports | Add `--hidden-import` to `release.yml`. |
| Name taken | PyPI name conflict | Change `[project] name` in `pyproject.toml`. |
