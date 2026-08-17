"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner

from mnemon import update
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

    def test_version_option(self, runner):
        """The CLI exposes the installed package version."""
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert result.output == "mnemon, version 0.1.0\n"

    def test_help_includes_version_option(self, runner):
        """Root help documents the version option."""
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "--version" in result.output
        assert "Version: 0.1.0" in result.output

    def test_normal_command_reports_available_update(self, runner, monkeypatch):
        """Normal commands report an available update on stderr."""
        status = update.UpdateStatus("1.0.0", "1.1.0", True)
        monkeypatch.setattr("mnemon.cli.check_for_update", lambda: status)

        result = runner.invoke(cli, ["projects"])

        assert result.exit_code == 0
        assert "Update available: 1.0.0 → 1.1.0" in result.stderr

    @pytest.mark.parametrize(
        "status",
        [
            update.UpdateStatus("1.0.0", None, False, error="offline"),
            update.UpdateStatus("1.0.0", None, False, skipped=True),
        ],
        ids=["offline", "opt-out"],
    )
    def test_normal_command_silences_unavailable_update(self, runner, monkeypatch, status):
        """Offline and opt-out checks do not add noise to normal commands."""
        monkeypatch.setattr("mnemon.cli.check_for_update", lambda: status)

        result = runner.invoke(cli, ["projects"])

        assert result.exit_code == 0
        assert result.stderr == ""

    def test_help_does_not_trigger_update_notification(self, runner, monkeypatch):
        """Help output does not perform an update check."""
        monkeypatch.setattr(
            "mnemon.cli.check_for_update",
            lambda: pytest.fail("root notification should be skipped"),
        )

        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0

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

    def test_removed_commands_not_registered(self, runner):
        """Removed commands (install, log-commit) are no longer registered."""
        for command in ["install", "log-commit"]:
            result = runner.invoke(cli, [command, "--help"])
            assert result.exit_code != 0

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
