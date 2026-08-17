"""Project hierarchy commands.

Provides ``projects`` (list), ``project-set-parent``, ``project-children``,
and ``project-tree``. The JSON output of ``projects`` is serialized through
the :class:`mnemon.contracts.project_contracts.ProjectList` contract model.
"""

from pathlib import Path
from typing import Any

import click

from ..commands._utils import CLIError, cli_guard, run_async, validate_format, write_output
from ..contracts.project_contracts import ProjectInfo, ProjectList
from ..core.projects import (
    get_project_children,
    get_project_tree,
    list_projects,
    set_project_parent,
)
from ..db.connection import get_db
from ..db.migrations import run_migrations


@click.command("projects")
@click.option(
    "--db-path",
    default=None,
    help="Database path (default: ~/.agent-memory/mnemon.db or MNEMON_DB_PATH env)",
)
@click.option("--format", default="text", help="Output format (text or json)")
@click.option("--out", default=None, type=click.Path(), help="Output file path (default: stdout)")
@cli_guard
def projects(db_path: str | None, format: str, out: str | None) -> None:
    """
    List all projects in the memory store.

    Examples:
      mnemon projects
      mnemon projects --format json
      mnemon projects --format json --out projects.json
    """
    validate_format(format)

    async def _run() -> None:
        async with get_db(path=db_path) as db:
            await run_migrations(db)
            rows = await list_projects(db)

            if format == "json":
                result = ProjectList(
                    projects=[
                        ProjectInfo.model_validate(
                            {
                                "id": p["id"],
                                "parentId": p.get("parent_id"),
                                "createdAt": p["created_at"],
                                "updatedAt": p.get("updated_at") or p["created_at"],
                            }
                        )
                        for p in rows
                    ],
                    total=len(rows),
                )
                output = result.model_dump_json(by_alias=True, indent=2)
            else:
                if not rows:
                    output = "No projects found."
                else:
                    lines = []
                    for p in rows:
                        parent = f"  (parent: {p['parent_id']})" if p.get("parent_id") else ""
                        lines.append(f"  {p['id']}{parent}")
                    output = "\n".join(lines) if lines else "No projects found."

            write_output(output, Path(out) if out else None, format)

    run_async(_run())


@click.command("project-set-parent")
@click.option("--project", required=True, help="Project ID (owner/repo)")
@click.option("--parent", default=None, help="Parent project ID (omit to remove parent)")
@click.option("--db-path", default=None, help="Database path")
@click.option("--format", default="text", type=click.Choice(["text", "json"]), help="Output format")
@click.option("--out", default=None, type=click.Path(), help="Output file path")
@cli_guard
def project_set_parent(
    project: str, parent: str | None, db_path: str | None, format: str, out: str | None
) -> None:
    """Set the parent project for a project."""

    async def _run() -> None:
        async with get_db(path=db_path) as db:
            await run_migrations(db)
            ok = await set_project_parent(db, project, parent)
            if ok:
                action = "set" if parent else "removed"
                output = f"Project '{project}' parent {action}."
            else:
                output = f"Project '{project}' not found."
                raise CLIError(output)

            write_output(output, Path(out) if out else None, format)

    run_async(_run())


@click.command("project-children")
@click.option("--project", required=True, help="Parent project ID")
@click.option("--recursive", is_flag=True, help="Include all descendants")
@click.option("--db-path", default=None, help="Database path")
@click.option("--format", default="text", type=click.Choice(["text", "json"]), help="Output format")
@click.option("--out", default=None, type=click.Path(), help="Output file path")
@cli_guard
def project_children(
    project: str, recursive: bool, db_path: str | None, format: str, out: str | None
) -> None:
    """List child projects of a project."""

    async def _run() -> None:
        async with get_db(path=db_path) as db:
            await run_migrations(db)
            children = await get_project_children(db, project, recursive=recursive)
            if not children:
                output = f"No children found for project '{project}'."
            else:
                output = "\n".join(f"  - {c['id']}" for c in children)

            write_output(output, Path(out) if out else None, format)

    run_async(_run())


@click.command("project-tree")
@click.option("--project", default=None, help="Root project ID (default: all root projects)")
@click.option("--db-path", default=None, help="Database path")
@click.option("--format", default="text", type=click.Choice(["text", "json"]), help="Output format")
@click.option("--out", default=None, type=click.Path(), help="Output file path")
@cli_guard
def project_tree(project: str | None, db_path: str | None, format: str, out: str | None) -> None:
    """Display the project hierarchy as a tree."""

    async def _run() -> None:
        async with get_db(path=db_path) as db:
            await run_migrations(db)
            tree = await get_project_tree(db, project)

            def print_tree(nodes: list[dict[str, Any]], indent: int = 0) -> list[str]:
                lines: list[str] = []
                for node in nodes:
                    prefix = "  " * indent
                    lines.append(f"{prefix}- {node['id']}")
                    if node.get("children"):
                        lines.extend(print_tree(node["children"], indent + 1))
                return lines

            if not tree:
                output = "No projects found."
            else:
                output = "\n".join(print_tree(tree))

            write_output(output, Path(out) if out else None, format)

    run_async(_run())


def register(cli_group: click.Group) -> None:
    """Register the project commands on the Click group."""
    cli_group.add_command(projects)
    cli_group.add_command(project_set_parent)
    cli_group.add_command(project_children)
    cli_group.add_command(project_tree)
