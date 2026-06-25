---
type: Process
title: Release Process
description: Automated release pipeline via git tags and Conventional Commits.
tags: [release, git, pypi, ci]
---

# Release Process

Project use [Conventional Commits](https://www.conventionalcommits.org/) + [git-cliff](https://github.com/orhun/git-cliff). Git tags drive release.

## Commit Convention

`main` commits require pattern:

```text
<type>[optional scope]: <short description>

[optional body]

[optional footer — use BREAKING CHANGE: <description> for breaking changes]
```

| Type | Meaning | Version Bump |
|---|---|---|
| `feat` | New feature | minor |
| `fix` | Bug fix | patch |
| `perf` | Perf improvement | patch |
| `refactor` | Code restructure | — |
| `docs` | Docs only | — |
| `test` | Tests only | — |
| `ci` | CI/CD | — |
| `chore` | Maintenance | — |
| `feat!` / `BREAKING CHANGE:` | Breaking API/CLI | **major** |

## Versioning

[Semantic Versioning 2.0](https://semver.org/): `MAJOR.MINOR.PATCH`.

## Prerequisites

### 1. Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install `git-cliff`

```bash
uv tool install git-cliff
```

### 3. Configure PyPI Trusted Publishing

See [Release Setup Guide](/guides/release-setup.md).

## Release Checklist

### 1. Verify `main`

```bash
git checkout main && git pull
```
Check CI pass.

### 2. Preview Changelog

```bash
git cliff --latest --strip header
```
Review output. Rebase + fix missing prefixes if needed.

### 3. Decide Version

Check `pyproject.toml` → `[project] version`. Use table → patch/minor/major.

### 4. Bump Version

Edit `pyproject.toml`. Commit.

```bash
sed -i 's/^version = .*/version = "1.2.0"/' pyproject.toml
git add pyproject.toml
git commit -m "chore: bump version to 1.2.0"
git push
```

### 5. Tag Release

```bash
git tag -a v1.2.0 -m "Release v1.2.0"
git push origin v1.2.0
```
Tag push → trigger `release.yml`:
- Generate changelog.
- Build binaries (Linux/macOS/Windows).
- Build wheel + sdist (`uv build`).
- Create GitHub Release + attach artifacts.

### 6. Monitor CI

**GitHub → Actions → Release**.
If fail: fix → delete tag → retag.

```bash
git tag -d v1.2.0
git push --delete origin v1.2.0
```

### 7. Publish GitHub Release

Workflow auto-create release.
Manual review: set `draft: true` in `release.yml` → publish via UI.

### 8. PyPI Publish

GitHub Release publish → trigger `publish-pypi.yml`.
Build + publish via OIDC. No tokens.
Monitor: **Actions → Publish to PyPI**.
Live: `https://pypi.org/project/mnemon-mcp/`

```bash
pip install mnemon-mcp
```

## Manual PyPI Publish

Hotfix without GitHub Release:

```bash
uv build
uv publish
```

TestPyPI:

```bash
uv build
uv publish --index https://test.pypi.org/legacy/
```

## Rollback

PyPI block delete. Yank instead:
**PyPI → project → [version] → Options → Yank this release**.
Fix bug → bump patch → release new.

## Pre-releases

Tag with suffix:

```bash
git tag -a v2.0.0-rc.1 -m "Release candidate v2.0.0-rc.1"
git push origin v2.0.0-rc.1
```
`release.yml` detect `-rc`/`-beta`/`-alpha` → mark GitHub Release pre-release.
PyPI show `2.0.0rc1`.

```bash
pip install --pre mnemon-mcp
```
