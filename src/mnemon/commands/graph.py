"""Knowledge graph commands: ``graph`` and ``prune``.

``graph`` prints the knowledge graph for a project; ``prune`` removes stale
low-importance entities. Both the dry-run preview and the real deletion use
:func:`mnemon.core.graph.list_prunable_entities` so they never diverge.
"""

import json
import os
from pathlib import Path
from typing import Any

import click

from ..commands._utils import cli_guard, run_async, validate_format, write_output
from ..contracts.graph_contracts import GraphPruneResult
from ..core import git
from ..core.graph import (
    get_observations,
    get_relations_for,
    list_entities,
    list_prunable_entities,
    prune_entities,
)
from ..db.connection import get_db
from ..db.migrations import run_migrations


@click.command("graph")
@click.option("--cwd", default=None)
@click.option("--project", default=None)
@click.option(
    "--min",
    "importance_min",
    default=0.0,
    type=float,
    help="Filter entities at or above this importance (0.0–1.0)",
)
@click.option(
    "--type",
    "entity_type",
    default=None,
    help="Filter by entity type: component, concept, person, file, system",
)
@click.option(
    "--db-path",
    default=None,
    help="Database path (default: ~/.agent-memory/mnemon.db or MNEMON_DB_PATH env)",
)
@click.option("--format", default="text", help="Output format (text or json)")
@click.option("--out", default=None, type=click.Path(), help="Output file path (default: stdout)")
@cli_guard
def graph(
    cwd: str | None,
    project: str | None,
    importance_min: float,
    entity_type: str | None,
    db_path: str | None,
    format: str,
    out: str | None,
) -> None:
    """
    Print the knowledge graph for a project.

    Examples:
      mnemon graph
      mnemon graph --min 0.6
      mnemon graph --type component
      mnemon graph --format json
      mnemon graph --format json --out graph.json
    """
    validate_format(format)

    async def _run() -> None:
        _cwd = cwd or os.getcwd()
        project_id = project or git.get_project_id(_cwd)

        async with get_db(path=db_path) as db:
            await run_migrations(db)
            entities = await list_entities(db, project_id, entity_type=entity_type)
            entities = [e for e in entities if e["importance"] >= importance_min]

            if not entities:
                output = "No entities found."
            elif format == "json":
                # Kept as an ad-hoc dict: GraphResult does not model the filter
                # metadata (importanceMin/entityType) that makes this output
                # useful for the CLI, so we include it explicitly.
                output = json.dumps(
                    {
                        "projectId": project_id,
                        "entities": entities,
                        "total": len(entities),
                        "filteredBy": {"importanceMin": importance_min, "entityType": entity_type},
                    },
                    indent=2,
                    default=str,
                )
            else:
                lines = [f"\n Knowledge Graph: {project_id}\n"]
                by_type: dict[str, list[dict[str, Any]]] = {}
                for e in entities:
                    by_type.setdefault(e["entity_type"], []).append(e)

                for etype, group in sorted(by_type.items()):
                    lines.append(f"  {etype.upper()}S")
                    for e in group:
                        imp = f"  [{e['importance']:.1f}]"
                        scope = f" (branch: {e['branch']})" if e.get("branch") else ""
                        lines.append(f"  ● {e['name']}{imp}{scope}")
                        obs = await get_observations(db, e["id"])
                        for o in obs:
                            lines.append(f"    - {o['content']}")
                        rels = await get_relations_for(db, e["id"])
                        for r in [x for x in rels if x["direction"] == "out"]:
                            lines.append(f"    → {r['relation']}: {r['other_name']}")
                    lines.append("")
                output = "".join(lines)

            write_output(output, Path(out) if out else None, format)

    run_async(_run())


@click.command("prune")
@click.option("--cwd", default=None)
@click.option("--project", default=None)
@click.option(
    "--below",
    default=0.2,
    type=float,
    help="Remove entities with importance below this value (default: 0.2)",
)
@click.option(
    "--days",
    default=30,
    type=int,
    help="Only remove entities not updated in this many days (default: 30)",
)
@click.option("--dry-run", is_flag=True, help="Preview what would be removed without deleting")
@click.option(
    "--db-path",
    default=None,
    help="Database path (default: ~/.agent-memory/mnemon.db or MNEMON_DB_PATH env)",
)
@click.option("--format", default="text", help="Output format (text or json)")
@click.option("--out", default=None, type=click.Path(), help="Output file path (default: stdout)")
@cli_guard
def prune(
    cwd: str | None,
    project: str | None,
    below: float,
    days: int,
    dry_run: bool,
    db_path: str | None,
    format: str,
    out: str | None,
) -> None:
    """
    Remove stale low-importance entities from the knowledge graph.
    Only removes entities that are BOTH low-importance AND old.

    Examples:
      mnemon prune
      mnemon prune --below 0.3 --days 60
      mnemon prune --dry-run
      mnemon prune --format json
      mnemon prune --dry-run --format json --out prune-preview.json
    """
    validate_format(format)

    async def _run() -> None:
        _cwd = cwd or os.getcwd()
        project_id = project or git.get_project_id(_cwd)

        async with get_db(path=db_path) as db:
            await run_migrations(db)

            if dry_run:
                # Preview uses the same shared helper as the MCP graph_prune
                # tool so the preview and the real deletion never diverge.
                candidates = await list_prunable_entities(
                    db, project_id, importance_below=below, older_than_days=days
                )

                if not candidates:
                    output = "Nothing to prune."
                elif format == "json":
                    result = GraphPruneResult(
                        projectId=project_id,
                        prunedCount=len(candidates),
                        belowImportance=below,
                        olderThanDays=days,
                        dryRun=True,
                        candidates=[
                            {
                                "name": e["name"],
                                "entityType": e["entity_type"],
                                "importance": e["importance"],
                                "updatedAt": e["updated_at"][:10] if e.get("updated_at") else None,
                            }
                            for e in candidates
                        ],
                    )
                    output = result.model_dump_json(by_alias=True, indent=2)
                else:
                    lines = [
                        f"Would prune {len(candidates)} entit{'y' if len(candidates) == 1 else 'ies'}:"
                    ]
                    for e in candidates:
                        lines.append(
                            f"  - {e['name']} [{e['entity_type']}] (importance: {e['importance']:.1f}, updated: {e['updated_at'][:10]})"
                        )
                    output = "\n".join(lines)
            else:
                count = await prune_entities(
                    db, project_id, importance_below=below, older_than_days=days
                )

                if format == "json":
                    result = GraphPruneResult(
                        projectId=project_id,
                        prunedCount=count,
                        belowImportance=below,
                        olderThanDays=days,
                        dryRun=False,
                    )
                    output = result.model_dump_json(by_alias=True, indent=2)
                else:
                    if count:
                        output = (
                            f"✓  Pruned {count} entit{'ies' if count != 1 else 'y'} "
                            f"(importance < {below}, not updated in {days}+ days)"
                        )
                    else:
                        output = "Nothing to prune."

            write_output(output, Path(out) if out else None, format)

    run_async(_run())


def register(cli_group: click.Group) -> None:
    """Register the graph commands on the Click group."""
    cli_group.add_command(graph)
    cli_group.add_command(prune)
