import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional

import click

from .db.connection import get_db
from .db.migrations import run_migrations
from .core.context import build_context
from .core.git import get_branch, get_commit_context, get_project_id
from .core.memory import add_session_log
from .core.graph import get_full_graph, prune_entities, list_entities
from .core.projects import upsert_project, list_projects
from .commands._utils import (
    CLIError, load_file, write_output, format_error, handle_cli_error,
    get_project_id_from_cwd, get_branch_from_cwd, validate_format
)

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
- When the user says "remember this", "save this", or similar — read and
  follow `.github/skills/mnemon/SKILL.md`.
- Use `graph_entity_upsert` to record components, concepts, and people you
  learn about. Use `graph_relate` to connect them.
- Task IDs appear in backticks in the `memory_read` output — use them exactly.

### Goal

Zero context loss between sessions. The next session on this branch should
pick up exactly where this one left off without re-explanation.
"""


@click.group()
def cli() -> None:
    """Mnemon — persistent project memory and knowledge graph for AI agents."""
    pass


# ── serve ─────────────────────────────────────────────────────────────────────

@cli.command("serve")
def serve() -> None:
    """Start the Mnemon MCP server (stdio). Referenced by AI client configs."""
    from .server import main
    main()


# ── init ──────────────────────────────────────────────────────────────────────

@cli.command("init")
@click.option("--cwd",   default=None, help="Repo path (default: current directory)")
@click.option("--force", is_flag=True, help="Overwrite existing file")
@click.option("--format", default="text", help="Output format (text or json)")
@click.option("--out",    default=None, type=click.Path(), help="Output file path (default: stdout)")
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
    try:
        # Validate format
        validate_format(format)
        
        _cwd = Path(cwd) if cwd else Path.cwd()

        try:
            project_id = get_project_id(str(_cwd))
        except Exception as e:
            raise CLIError(f"Could not detect project: {e}")

        github_dir = _cwd / ".github"
        target     = github_dir / "copilot-instructions.md"
        github_dir.mkdir(exist_ok=True)

        if target.exists() and not force:
            if format == "json":
                import json
                output = json.dumps({
                    "error": f"{target.relative_to(_cwd)} already exists. Use --force to overwrite.",
                    "projectId": None,
                    "fileCreated": False
                }, indent=2)
            else:
                output = f"✗  {target.relative_to(_cwd)} already exists. Use --force to overwrite."
            write_output(output, Path(out) if out else None, format)
            return

        target.write_text(_INSTRUCTIONS_TEMPLATE.format(project_id=project_id))
        
        if format == "json":
            import json
            output = json.dumps({
                "projectId": project_id,
                "fileCreated": str(target.relative_to(_cwd)),
                "nextStep": "run mnemon install to add the memory skill"
            }, indent=2)
        else:
            output = f"✓  Created {target.relative_to(_cwd)}\n   project_id: {project_id}\n\nNext: run  mnemon install  to add the memory skill."
        
        write_output(output, Path(out) if out else None, format)
        
    except CLIError as e:
        handle_cli_error(e)
    except Exception as e:
        handle_cli_error(e)


# ── install ───────────────────────────────────────────────────────────────────

@cli.command("install")
@click.option("--cwd",   default=None, help="Repo path (default: current directory)")
@click.option("--force", is_flag=True, help="Overwrite existing skill file")
@click.option("--format", default="text", help="Output format (text or json)")
@click.option("--out",    default=None, type=click.Path(), help="Output file path (default: stdout)")
def install(cwd: str | None, force: bool, format: str, out: str | None) -> None:
    """
    Install the Mnemon skill into this repo.
    Copies SKILL.md to .github/skills/mnemon/SKILL.md so the AI knows
    how to handle 'remember this' and related memory requests.

    Examples:
      mnemon install
      mnemon install --force
      mnemon install --format json
    """
    try:
        # Validate format
        validate_format(format)
        
        _cwd      = Path(cwd) if cwd else Path.cwd()
        skill_dir = _cwd / ".github" / "skills" / "mnemon"
        target    = skill_dir / "SKILL.md"

        if target.exists() and not force:
            if format == "json":
                import json
                output = json.dumps({
                    "error": f"{target.relative_to(_cwd)} already exists. Use --force to overwrite.",
                    "skillInstalled": False
                }, indent=2)
            else:
                output = f"✗  {target.relative_to(_cwd)} already exists. Use --force to overwrite."
            write_output(output, Path(out) if out else None, format)
            return

        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_src = Path(__file__).parent / "skill" / "SKILL.md"
        shutil.copy2(skill_src, target)

        if format == "json":
            import json
            output = json.dumps({
                "skillInstalled": True,
                "filePath": str(target.relative_to(_cwd)),
                "message": "The AI will follow this skill when you say 'remember this'.",
                "tip": "run mnemon init if you haven't set up copilot-instructions.md yet"
            }, indent=2)
        else:
            output = f"✓  Installed skill → {target.relative_to(_cwd)}\n\nThe AI will follow this skill when you say 'remember this'.\nTip: run  mnemon init  if you haven't set up copilot-instructions.md yet."
        
        write_output(output, Path(out) if out else None, format)
        
    except CLIError as e:
        handle_cli_error(e)
    except Exception as e:
        handle_cli_error(e)


# ── log-commit ────────────────────────────────────────────────────────────────

@cli.command("log-commit")
@click.option("--cwd", default=None)
@click.option("--db-path", default=None, help="Database path (default: ~/.agent-memory/mnemon.db or MNEMON_DB_PATH env)")
@click.option("--format", default="text", help="Output format (text or json)")
@click.option("--out",    default=None, type=click.Path(), help="Output file path (default: stdout)")
def log_commit(cwd: str | None, db_path: str | None, format: str, out: str | None) -> None:
    """
    Log the latest commit. Called automatically by git hooks.

    Examples:
      mnemon log-commit
      mnemon log-commit --format json
    """
    try:
        # Validate format
        validate_format(format)
        
        async def _run() -> None:
            _cwd = cwd or os.getcwd()
            try:
                project_id = get_project_id(_cwd)
                branch     = get_branch(_cwd)
                ctx        = get_commit_context(_cwd)
            except Exception as e:
                if format == "json":
                    import json
                    output = json.dumps({
                        "error": f"Skipped: {e}",
                        "projectId": None,
                        "branch": None,
                        "commitSha": None
                    }, indent=2)
                else:
                    output = f"[mnemon] Skipped: {e}"
                write_output(output, Path(out) if out else None, format)
                return

            summary = (
                f"{ctx['message'].splitlines()[0]}"
                f" ({len(ctx['files'])} files)"
                f" by {ctx['author']}"
            )
            async with get_db(path=db_path) as db:
                await run_migrations(db)
                await upsert_project(db, project_id)
                await add_session_log(db, project_id, summary,
                                      branch=branch, source="git-commit", sha=ctx["sha"])
            
            if format == "json":
                import json
                output = json.dumps({
                    "projectId": project_id,
                    "branch": branch,
                    "commitSha": ctx["short_sha"],
                    "message": summary,
                    "filesCount": len(ctx["files"]),
                    "author": ctx["author"]
                }, indent=2)
            else:
                output = f"[mnemon] {ctx['short_sha']} → {project_id}@{branch}"
            
            write_output(output, Path(out) if out else None, format)

        asyncio.run(_run())
    except CLIError as e:
        handle_cli_error(e)
    except Exception as e:
        handle_cli_error(e)


# ── read ──────────────────────────────────────────────────────────────────────

@cli.command("read")
@click.option("--cwd",     default=None)
@click.option("--project", default=None, help="Override project_id (owner/repo)")
@click.option("--branch",  default=None, help="Override branch name")
@click.option("--db-path", default=None, help="Database path (default: ~/.agent-memory/mnemon.db or MNEMON_DB_PATH env)")
@click.option("--format",  default="text", help="Output format (text or json)")
@click.option("--out",     default=None, type=click.Path(), help="Output file path (default: stdout)")
def read(cwd: str | None, project: str | None, branch: str | None, 
         db_path: str | None, format: str, out: str | None) -> None:
    """
    Print the full context block — what the AI sees at session start.

    Examples:
      mnemon read
      mnemon read --project bcgov/nr-waste-plus --branch main
      mnemon read --format json
      mnemon read --format json --out context.json
    """
    try:
        # Validate format
        validate_format(format)
        
        async def _run() -> None:
            _cwd       = cwd or os.getcwd()
            project_id = project or get_project_id(_cwd)
            _branch    = branch  or get_branch(_cwd)
            async with get_db(path=db_path) as db:
                await run_migrations(db)
                await upsert_project(db, project_id)
                context = await build_context(db, project_id, _branch)
                
                if format == "json":
                    # For now, return as simple dict - TODO: Use proper contract model
                    import json
                    output = json.dumps({"context": context}, indent=2)
                else:
                    output = context
                    
                write_output(output, Path(out) if out else None, format)

        asyncio.run(_run())
    except CLIError as e:
        handle_cli_error(e)
    except Exception as e:
        handle_cli_error(e)


# ── graph ─────────────────────────────────────────────────────────────────────

@cli.command("graph")
@click.option("--cwd",     default=None)
@click.option("--project", default=None)
@click.option("--min",     "importance_min", default=0.0, type=float,
              help="Filter entities at or above this importance (0.0–1.0)")
@click.option("--type",    "entity_type", default=None,
              help="Filter by entity type: component, concept, person, file, system")
@click.option("--db-path", default=None, help="Database path (default: ~/.agent-memory/mnemon.db or MNEMON_DB_PATH env)")
@click.option("--format",  default="text", help="Output format (text or json)")
@click.option("--out",     default=None, type=click.Path(), help="Output file path (default: stdout)")
def graph(cwd: str | None, project: str | None,
          importance_min: float, entity_type: str | None,
          db_path: str | None, format: str, out: str | None) -> None:
    """
    Print the knowledge graph for a project.

    Examples:
      mnemon graph
      mnemon graph --min 0.6
      mnemon graph --type component
      mnemon graph --format json
      mnemon graph --format json --out graph.json
    """
    try:
        # Validate format
        validate_format(format)
        
        async def _run() -> None:
            _cwd       = cwd or os.getcwd()
            project_id = project or get_project_id(_cwd)

            async with get_db(path=db_path) as db:
                await run_migrations(db)
                entities = await list_entities(db, project_id, entity_type=entity_type)
                entities = [e for e in entities if e["importance"] >= importance_min]

                if not entities:
                    output = "No entities found."
                elif format == "json":
                    # Convert to JSON format
                    import json
                    output_data = {
                        "projectId": project_id,
                        "entities": entities,
                        "total": len(entities),
                        "filteredBy": {
                            "importanceMin": importance_min,
                            "entityType": entity_type
                        }
                    }
                    output = json.dumps(output_data, indent=2, default=str)
                else:
                    from .core.graph import get_observations, get_relations_for
                    lines = [f"\n Knowledge Graph: {project_id}\n"]
                    by_type: dict[str, list] = {}
                    for e in entities:
                        by_type.setdefault(e["entity_type"], []).append(e)

                    for etype, group in sorted(by_type.items()):
                        lines.append(f"  {etype.upper()}S")
                        for e in group:
                            imp  = f"  [{e['importance']:.1f}]"
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

        asyncio.run(_run())
    except CLIError as e:
        handle_cli_error(e)
    except Exception as e:
        handle_cli_error(e)


# ── prune ─────────────────────────────────────────────────────────────────────

@cli.command("prune")
@click.option("--cwd",      default=None)
@click.option("--project",  default=None)
@click.option("--below",    default=0.2, type=float,
              help="Remove entities with importance below this value (default: 0.2)")
@click.option("--days",     default=30,  type=int,
              help="Only remove entities not updated in this many days (default: 30)")
@click.option("--dry-run",  is_flag=True,
              help="Preview what would be removed without deleting")
@click.option("--db-path",  default=None, help="Database path (default: ~/.agent-memory/mnemon.db or MNEMON_DB_PATH env)")
@click.option("--format",   default="text", help="Output format (text or json)")
@click.option("--out",      default=None, type=click.Path(), help="Output file path (default: stdout)")
def prune(cwd: str | None, project: str | None,
          below: float, days: int, dry_run: bool,
          db_path: str | None, format: str, out: str | None) -> None:
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
    try:
        # Validate format
        validate_format(format)
        
        async def _run() -> None:
            _cwd       = cwd or os.getcwd()
            project_id = project or get_project_id(_cwd)

            async with get_db(path=db_path) as db:
                await run_migrations(db)

                if dry_run:
                    # Show what would be pruned
                    entities = await list_entities(db, project_id)
                    candidates = [
                        e for e in entities
                        if e["importance"] < below
                    ]
                    
                    if not candidates:
                        output = "Nothing to prune."
                    elif format == "json":
                        import json
                        output_data = {
                            "projectId": project_id,
                            "dryRun": True,
                            "belowImportance": below,
                            "olderThanDays": days,
                            "candidates": [
                                {
                                    "name": e["name"],
                                    "entityType": e["entity_type"],
                                    "importance": e["importance"],
                                    "updatedAt": e["updated_at"][:10] if e.get("updated_at") else None
                                } for e in candidates
                            ],
                            "count": len(candidates)
                        }
                        output = json.dumps(output_data, indent=2, default=str)
                    else:
                        lines = [f"Would prune {len(candidates)} entities:"]
                        for e in candidates:
                            lines.append(f"  - {e['name']} [{e['entity_type']}] (importance: {e['importance']:.1f}, updated: {e['updated_at'][:10]})")
                        output = "\n".join(lines)
                else:
                    count = await prune_entities(db, project_id,
                                             importance_below=below,
                                             older_than_days=days)
                    
                    if format == "json":
                        import json
                        output_data = {
                            "projectId": project_id,
                            "dryRun": False,
                            "belowImportance": below,
                            "olderThanDays": days,
                            "prunedCount": count
                        }
                        output = json.dumps(output_data, indent=2)
                    else:
                        if count:
                            output = f"✓  Pruned {count} entit{'ies' if count != 1 else 'y'} " \
                                   f"(importance < {below}, not updated in {days}+ days)"
                        else:
                            output = "Nothing to prune."
                
                write_output(output, Path(out) if out else None, format)

        asyncio.run(_run())
    except CLIError as e:
        handle_cli_error(e)
    except Exception as e:
        handle_cli_error(e)


# ── projects ──────────────────────────────────────────────────────────────────

@cli.command("projects")
@click.option("--db-path", default=None, help="Database path (default: ~/.agent-memory/mnemon.db or MNEMON_DB_PATH env)")
@click.option("--format", default="text", help="Output format (text or json)")
@click.option("--out",    default=None, type=click.Path(), help="Output file path (default: stdout)")
def projects(db_path: str | None, format: str, out: str | None) -> None:
    """
    List all projects in the memory store.

    Examples:
      mnemon projects
      mnemon projects --format json
      mnemon projects --format json --out projects.json
    """
    try:
        # Validate format
        validate_format(format)
        
        async def _run() -> None:
            async with get_db(path=db_path) as db:
                await run_migrations(db)
                rows = await list_projects(db)
                
                if format == "json":
                    import json
                    if not rows:
                        output = json.dumps({"projects": [], "total": 0}, indent=2)
                    else:
                        output_data = {
                            "projects": [
                                {
                                    "id": p["id"],
                                    "parentId": p.get("parent_id")
                                } for p in rows
                            ],
                            "total": len(rows)
                        }
                        output = json.dumps(output_data, indent=2)
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

        asyncio.run(_run())
    except CLIError as e:
        handle_cli_error(e)
    except Exception as e:
        handle_cli_error(e)
