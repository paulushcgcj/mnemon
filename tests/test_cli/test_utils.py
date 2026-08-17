"""Tests for the shared CLI utilities in :mod:`mnemon.commands._utils`."""

import asyncio

import pytest
from pydantic import BaseModel, Field

from mnemon.commands._utils import (
    CLIError,
    cli_guard,
    format_error,
    handle_cli_error,
    run_async,
    validate_format,
    write_output,
)


class TestRunAsync:
    """Tests for :func:`run_async`."""

    def test_no_running_loop(self):
        """Running a coroutine from a synchronous context uses asyncio.run."""

        async def hello() -> str:
            return "world"

        assert run_async(hello()) == "world"

    @pytest.mark.asyncio
    async def test_running_loop(self):
        """Running a coroutine while a loop is active uses a worker thread."""

        async def hello() -> str:
            return "threaded"

        assert run_async(hello()) == "threaded"

    @pytest.mark.asyncio
    async def test_running_loop_preserves_result(self):
        """The worker thread keeps the caller's loop responsive."""

        async def probe() -> str:
            # Confirm the coroutine actually runs on a separate loop.
            return f"running={asyncio.get_running_loop().is_running()}"

        assert run_async(probe()) == "running=True"


class TestWriteOutput:
    """Tests for :func:`write_output`."""

    def test_echo_to_stdout(self, capsys):
        """String output goes to stdout via Click."""
        write_output("hello")
        captured = capsys.readouterr()
        assert captured.out.strip() == "hello"

    def test_writes_text_file(self, tmp_path):
        """String output to a file."""
        target = tmp_path / "out" / "result.txt"
        write_output("content", target, format="text")
        assert target.read_text(encoding="utf-8") == "content"

    def test_model_to_json_file(self, tmp_path):
        """Pydantic model serialized with camelCase aliases to a JSON file."""

        class MockModel(BaseModel):
            project_id: str = Field(..., serialization_alias="projectId")

        target = tmp_path / "out.json"
        write_output(MockModel(project_id="owner/repo"), target, format="json")
        assert '"projectId":"owner/repo"' in target.read_text(encoding="utf-8")

    def test_write_failure_raises_cli_error(self, tmp_path):
        """An unwritable target surfaces as a CLIError."""
        # A regular file standing in for the output directory makes the
        # parent.mkdir(parents=True) call fail.
        blocker = tmp_path / "blocked.txt"
        blocker.write_text("occupied", encoding="utf-8")

        with pytest.raises(CLIError, match="Failed to write"):
            write_output("x", blocker / "out.txt")


class TestErrorHandling:
    """Tests for error helpers and the cli_guard decorator."""

    def test_format_error_goes_to_stderr(self, capsys):
        """Error messages are printed to stderr."""
        format_error("boom")
        captured = capsys.readouterr()
        assert captured.err.strip() == "Error: boom"
        assert captured.out == ""

    def test_handle_cli_error_exits(self):
        """A CLIError exits with code 1."""
        with pytest.raises(SystemExit) as excinfo:
            handle_cli_error(CLIError("user problem"))
        assert excinfo.value.code == 1

    def test_handle_cli_error_unexpected_exits(self, capsys):
        """A non-CLIError is reported as unexpected and exits with code 1."""
        with pytest.raises(SystemExit):
            handle_cli_error(ValueError("surprise"))
        captured = capsys.readouterr()
        assert "Unexpected error" in captured.err

    def test_cli_guard_swallows_cli_error(self, capsys):
        """A CLIError inside a guarded command exits cleanly."""

        @cli_guard
        def cmd() -> None:
            raise CLIError("known issue")

        with pytest.raises(SystemExit):
            cmd()
        assert "known issue" in capsys.readouterr().err

    def test_cli_guard_reports_unexpected(self, capsys):
        """An unexpected exception inside a guarded command is reported."""

        @cli_guard
        def cmd() -> None:
            raise ValueError("internal")

        with pytest.raises(SystemExit):
            cmd()
        assert "Unexpected error" in capsys.readouterr().err

    def test_cli_guard_preserves_signature(self):
        """functools.wraps keeps the wrapped function's name."""

        @cli_guard
        def my_command() -> None:  # pragma: no cover - never invoked
            """My command docstring."""

        assert my_command.__name__ == "my_command"
        assert my_command.__doc__ == "My command docstring."


class TestValidateFormat:
    """Tests for :func:`validate_format`."""

    def test_valid_formats(self):
        """text and json pass through."""
        assert validate_format("text") == "text"
        assert validate_format("json") == "json"

    def test_invalid_format(self):
        """Anything else raises CLIError."""
        with pytest.raises(CLIError, match="Invalid format"):
            validate_format("xml")
