"""Session commands: ``serve`` and ``read``.

``serve`` starts the MCP server over stdio; ``read`` prints the context block
an AI agent sees at session start.
"""

import json
import os
from pathlib import Path

import click

from ..commands._utils import CLIError, cli_guard, run_async, validate_format, write_output
from ..core import git
from ..core.context import build_context
from ..core.projects import upsert_project
from ..db.connection import get_db
from ..db.migrations import run_migrations


@click.command("serve")
@cli_guard
def serve() -> None:
    """Start the Mnemon MCP server (stdio). Referenced by AI client configs."""
    from ..server import main

    main()


@click.command("read")
@click.option("--cwd", default=None)
@click.option("--project", default=None, help="Override project_id (owner/repo)")
@click.option(
    "--branch",
    default=None,
    help="Override branch name (also useful when HEAD is detached)",
)
@click.option(
    "--db-path",
    default=None,
    help="Database path (default: ~/.agent-memory/mnemon.db or MNEMON_DB_PATH env)",
)
@click.option("--format", default="text", help="Output format (text or json)")
@click.option("--out", default=None, type=click.Path(), help="Output file path (default: stdout)")
@cli_guard
def read(
    cwd: str | None,
    project: str | None,
    branch: str | None,
    db_path: str | None,
    format: str,
    out: str | None,
) -> None:
    """
    Print the full context block — what the AI sees at session start.

    Examples:
      mnemon read
      mnemon read --project bcgov/nr-waste-plus --branch main
      mnemon read --format json
      mnemon read --format json --out context.json
    """
    validate_format(format)

    async def _run() -> None:
        _cwd = cwd or os.getcwd()
        project_id = project or git.get_project_id(_cwd)
        try:
            _branch = branch or git.get_branch(_cwd)
        except git.DetachedHeadError as e:
            raise CLIError(f"{e} Use --branch <name> to read a specific branch.") from e
        async with get_db(path=db_path) as db:
            await run_migrations(db)
            await upsert_project(db, project_id)
            context = await build_context(db, project_id, _branch)

            if format == "json":
                # The context block is a rendered markdown document; the JSON
                # shape wraps it as-is (structured breakdowns live in the
                # memory_read MCP tool's contract models).
                output = json.dumps({"context": context}, indent=2)
            else:
                output = context

            write_output(output, Path(out) if out else None, format)

    run_async(_run())


def register(cli_group: click.Group) -> None:
    """Register the session commands on the Click group."""
    cli_group.add_command(serve)
    cli_group.add_command(read)
