"""Shared utilities for CLI commands.

Provides error handling, output formatting, and async execution helpers used
by the individual command modules under :mod:`mnemon.commands`.
"""

import asyncio
import functools
import sys
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any, TypeVar

import click
from pydantic import BaseModel

T = TypeVar("T")


class CLIError(Exception):
    """Base exception for CLI errors.

    When raised inside a Click command, the CLI exits with code 1 and displays
    the message.
    """


def cli_guard(func: Callable[..., None]) -> Callable[..., None]:
    """Wrap a Click command so errors exit cleanly with code 1.

    ``CLIError`` is printed as-is; any other exception is reported as an
    unexpected error. Both exit with code 1 via :func:`handle_cli_error`.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        try:
            func(*args, **kwargs)
        except CLIError as e:
            handle_cli_error(e)
        except Exception as e:
            handle_cli_error(e)

    return wrapper


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine from a synchronous Click command.

    Uses :func:`asyncio.run` when no event loop is running. When a loop is
    already running (e.g. inside pytest-asyncio), the coroutine is executed on
    a fresh loop in a worker thread, since :func:`asyncio.run` cannot be called
    from a running loop.

    Args:
        coro: The coroutine to run.

    Returns:
        The coroutine result.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import concurrent.futures

    def run_in_new_loop() -> T:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(run_in_new_loop).result()


def write_output(
    data: str | BaseModel,
    output_path: Path | None = None,
    format: str = "text",
) -> None:
    """Write output to stdout or a file.

    Args:
        data: Data to write (string or Pydantic model).
        output_path: Path to output file (None for stdout).
        format: Output format ('text' or 'json').

    Raises:
        CLIError: If file cannot be written.
    """
    # Convert Pydantic models to the appropriate format.
    if isinstance(data, BaseModel):
        if format == "json":
            data = data.model_dump_json(by_alias=True)
        else:
            data = str(data.model_dump())

    if output_path:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(str(data), encoding="utf-8")
        except Exception as e:
            raise CLIError(f"Failed to write {output_path}: {e}") from e
    else:
        # For click, use echo to ensure proper output.
        click.echo(data)


def format_error(message: str) -> None:
    """Print an error message to stderr.

    Args:
        message: Error message to display.
    """
    click.echo(f"Error: {message}", file=sys.stderr, err=True)


def handle_cli_error(e: Exception, exit_code: int = 1) -> None:
    """Handle a CLI error by printing to stderr and exiting.

    Args:
        e: Exception that occurred.
        exit_code: Exit code to use (default: 1).
    """
    if isinstance(e, CLIError):
        format_error(str(e))
    else:
        format_error(f"Unexpected error: {e}")
    sys.exit(exit_code)


def validate_format(format: str) -> str:
    """Validate the output format.

    Args:
        format: Format string to validate.

    Returns:
        Validated format string.

    Raises:
        CLIError: If format is invalid.
    """
    valid_formats = ["text", "json"]
    if format not in valid_formats:
        raise CLIError(f"Invalid format: {format}. Must be one of: {valid_formats}")
    return format
