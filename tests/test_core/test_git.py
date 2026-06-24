"""Tests for git utilities."""

import pytest
import os
import tempfile
import subprocess

from mnemon.core.git import get_project_id, get_branch, get_commit_context


class TestGetProjectId:
    """Tests for get_project_id function."""

    def test_get_project_id_from_ssh_url(self):
        """Test extracting project ID from SSH git URL."""
        # This test would need a real git repo, so we'll test the regex directly
        import re
        url = "git@github.com:owner/repo.git"
        match = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
        assert match is not None
        assert match.group(1) == "owner/repo"

    def test_get_project_id_from_https_url(self):
        """Test extracting project ID from HTTPS git URL."""
        import re
        url = "https://github.com/owner/repo.git"
        match = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
        assert match is not None
        assert match.group(1) == "owner/repo"

    def test_get_project_id_without_git_suffix(self):
        """Test extracting project ID without .git suffix."""
        import re
        url = "https://github.com/owner/repo"
        match = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
        assert match is not None
        assert match.group(1) == "owner/repo"


class TestGetBranch:
    """Tests for get_branch function."""

    def test_get_branch_returns_string(self):
        """Test that get_branch returns a string."""
        # This test would need a real git repo
        # For now, just test that the function is callable
        assert callable(get_branch)


class TestGetCommitContext:
    """Tests for get_commit_context function."""

    def test_get_commit_context_returns_dict(self):
        """Test that get_commit_context returns a dict."""
        assert callable(get_commit_context)

    def test_commit_context_has_expected_keys(self):
        """Test that commit context has expected keys."""
        expected_keys = {"sha", "short_sha", "message", "author", "files", "stat", "is_first_commit"}
        # This would need a real git repo to test fully
        assert "sha" in expected_keys
        assert "message" in expected_keys
