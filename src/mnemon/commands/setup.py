"""Setup commands: ``init``.

``init`` writes a pre-filled ``.github/copilot-instructions.md``.
"""

import json
from pathlib import Path

import click

from ..commands._utils import CLIError, cli_guard, validate_format, write_output
from ..core import git

# ── Copilot instructions template ─────────────────────────────────────────────

_INSTRUCTIONS_TEMPLATE = """\
# Copilot Instructions

## Agent Memory — Mnemon

This project uses the Mnemon MCP server for persistent memory across sessions.

**Project:** `{project_id}`

### Session Start

Before doing anything else, call `memory_read` with:
- `project_id`: `{project_id}`
- `branch`: the current git branch (read from workspace context)

Use the returned context to orient yourself before responding to the first request.

### Session End

Always call `memory_summarize` before the session closes, even if the user
doesn't ask. Include what was done, current focus, next steps, any decisions
made, task IDs that are now done, and new tasks discovered.

### During the Session

- Call `memory_task_update` immediately when a task changes status.
- When the user says "remember this", "save this", or similar — store the
  information using the Mnemon MCP tools described in the bundled skill.
- Use `graph_entity_upsert` to record components, concepts, and people you
  learn about. Use `graph_relate` to connect them.
- Task IDs appear in backticks in the `memory_read` output — use them exactly.

### Goal

Zero context loss between sessions. The next session on this branch should
pick up exactly where this one left off without re-explanation.
"""


@click.command("init")
@click.option("--cwd", default=None, help="Repo path (default: current directory)")
@click.option("--force", is_flag=True, help="Overwrite existing file")
@click.option("--format", default="text", help="Output format (text or json)")
@click.option("--out", default=None, type=click.Path(), help="Output file path (default: stdout)")
@cli_guard
def init(cwd: str | None, force: bool, format: str, out: str | None) -> None:
    """
    Set up Mnemon for this repo.
    Detects the project_id from git remote and writes
    .github/copilot-instructions.md with everything pre-filled.

    Examples:
      mnemon init
      mnemon init --force
      mnemon init --format json
    """
    validate_format(format)

    _cwd = Path(cwd) if cwd else Path.cwd()

    try:
        project_id = git.get_project_id(str(_cwd))
    except Exception as e:
        raise CLIError(f"Could not detect project: {e}") from e

    github_dir = _cwd / ".github"
    target = github_dir / "copilot-instructions.md"
    github_dir.mkdir(exist_ok=True)

    if target.exists() and not force:
        if format == "json":
            output = json.dumps(
                {
                    "error": f"{target.relative_to(_cwd)} already exists. Use --force to overwrite.",
                    "projectId": None,
                    "fileCreated": False,
                },
                indent=2,
            )
        else:
            output = f"✗  {target.relative_to(_cwd)} already exists. Use --force to overwrite."
        write_output(output, Path(out) if out else None, format)
        return

    target.write_text(_INSTRUCTIONS_TEMPLATE.format(project_id=project_id))

    if format == "json":
        output = json.dumps(
            {
                "projectId": project_id,
                "fileCreated": str(target.relative_to(_cwd)),
                "nextStep": "connect the Mnemon MCP server to this workspace",
            },
            indent=2,
        )
    else:
        output = f"✓  Created {target.relative_to(_cwd)}\n   project_id: {project_id}\n\nNext: connect the Mnemon MCP server to this workspace."

    write_output(output, Path(out) if out else None, format)


def register(cli_group: click.Group) -> None:
    """Register the setup commands on the Click group."""
    cli_group.add_command(init)
