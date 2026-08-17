"""Tests for git utilities."""

import subprocess
from pathlib import Path

import pytest

from mnemon.core.git import DetachedHeadError, get_branch, get_commit_context, get_project_id


def _run_git(repo: Path, *args: str) -> str:
    """Run a git command inside a repo and return trimmed stdout."""
    return subprocess.check_output(
        ["git", *args], cwd=repo, text=True, stderr=subprocess.DEVNULL
    ).strip()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a real git repository with one commit and an origin remote."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test User")
    _run_git(repo, "remote", "add", "origin", "git@github.com:owner/repo.git")
    (repo / "file.txt").write_text("hello\n")
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-q", "-m", "Initial commit")
    return repo


class TestGetProjectId:
    """Tests for get_project_id function."""

    def test_from_ssh_url(self, git_repo: Path) -> None:
        """Extract project ID from an SSH remote URL."""
        assert get_project_id(str(git_repo)) == "owner/repo"

    def test_from_https_url(self, tmp_path: Path) -> None:
        """Extract project ID from an HTTPS remote URL."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _run_git(repo, "init", "-q", "-b", "main")
        _run_git(repo, "remote", "add", "origin", "https://github.com/owner/repo.git")
        assert get_project_id(str(repo)) == "owner/repo"

    def test_raises_when_not_a_repo(self, tmp_path: Path) -> None:
        """Non-repo directory raises RuntimeError."""
        with pytest.raises(RuntimeError):
            get_project_id(str(tmp_path))

    def test_raises_on_unparseable_remote(self, tmp_path: Path) -> None:
        """Repo without a parseable origin raises ValueError."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _run_git(repo, "init", "-q", "-b", "main")
        _run_git(repo, "remote", "add", "origin", "just-a-name")
        with pytest.raises(ValueError):
            get_project_id(str(repo))


class TestGetBranch:
    """Tests for get_branch function."""

    def test_returns_branch_name(self, git_repo: Path) -> None:
        """Returns the current branch name."""
        assert get_branch(str(git_repo)) == "main"

    def test_detached_head_raises(self, git_repo: Path) -> None:
        """Detached HEAD raises DetachedHeadError with actionable guidance."""
        _run_git(git_repo, "checkout", "-q", "--detach")
        with pytest.raises(DetachedHeadError, match="Detached HEAD"):
            get_branch(str(git_repo))

    def test_non_repo_propagates_original_error(self, tmp_path: Path) -> None:
        """Non-repo directory still raises the original subprocess error."""
        with pytest.raises(subprocess.CalledProcessError):
            get_branch(str(tmp_path))


class TestGetCommitContext:
    """Tests for get_commit_context function."""

    def test_returns_expected_keys(self, git_repo: Path) -> None:
        """Commit context contains the full expected key set."""
        expected = {
            "sha",
            "short_sha",
            "message",
            "author",
            "files",
            "stat",
            "is_first_commit",
        }
        ctx = get_commit_context(str(git_repo))
        assert expected <= set(ctx)

    def test_single_commit_detected(self, git_repo: Path) -> None:
        """First commit is flagged and message/sha are populated."""
        ctx = get_commit_context(str(git_repo))
        assert ctx["is_first_commit"] is True
        assert ctx["message"] == "Initial commit"
        assert ctx["short_sha"] == ctx["sha"][:8]
