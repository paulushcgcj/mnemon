"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner

from mnemon.cli import cli


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


class TestCLI:
    """Tests for CLI commands."""

    def test_help_command(self, runner):
        """Test that --help works."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Mnemon" in result.output or "Usage" in result.output

    # Note: --version option is not implemented in the CLI, skipping this test

    def test_serve_command_help(self, runner):
        """Test that serve command help works."""
        result = runner.invoke(cli, ["serve", "--help"])
        assert result.exit_code == 0

    def test_read_command_help(self, runner):
        """Test that read command help works."""
        result = runner.invoke(cli, ["read", "--help"])
        assert result.exit_code == 0

    def test_graph_command_help(self, runner):
        """Test that graph command help works."""
        result = runner.invoke(cli, ["graph", "--help"])
        assert result.exit_code == 0

    def test_prune_command_help(self, runner):
        """Test that prune command help works."""
        result = runner.invoke(cli, ["prune", "--help"])
        assert result.exit_code == 0

    def test_projects_command_help(self, runner):
        """Test that projects command help works."""
        result = runner.invoke(cli, ["projects", "--help"])
        assert result.exit_code == 0

    def test_init_command_help(self, runner):
        """Test that init command help works."""
        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0

    def test_install_command_help(self, runner):
        """Test that install command help works."""
        result = runner.invoke(cli, ["install", "--help"])
        assert result.exit_code == 0

    def test_log_commit_command_help(self, runner):
        """Test that log-commit command help works."""
        result = runner.invoke(cli, ["log-commit", "--help"])
        assert result.exit_code == 0

    def test_db_path_option(self, runner):
        """Test that --db-path option is available on commands."""
        result = runner.invoke(cli, ["read", "--help"])
        assert result.exit_code == 0
        assert "--db-path" in result.output

    def test_format_option(self, runner):
        """Test that --format option is available on commands."""
        result = runner.invoke(cli, ["read", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.output

    def test_out_option(self, runner):
        """Test that --out option is available on commands."""
        result = runner.invoke(cli, ["read", "--help"])
        assert result.exit_code == 0
        assert "--out" in result.output
