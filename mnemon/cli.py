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
def init(cwd: str | None, force: bool) -> None:
    """
    Set up Mnemon for this repo.
    Detects the project_id from git remote and writes
    .github/copilot-instructions.md with everything pre-filled.

    Examples:
      mnemon init
      mnemon init --force
    """
    _cwd = Path(cwd) if cwd else Path.cwd()

    try:
        project_id = get_project_id(str(_cwd))
    except Exception as e:
        click.echo(f"✗  Could not detect project: {e}", err=True)
        raise SystemExit(1)

    github_dir = _cwd / ".github"
    target     = github_dir / "copilot-instructions.md"
    github_dir.mkdir(exist_ok=True)

    if target.exists() and not force:
        click.echo(f"✗  {target.relative_to(_cwd)} already exists. Use --force to overwrite.")
        raise SystemExit(1)

    target.write_text(_INSTRUCTIONS_TEMPLATE.format(project_id=project_id))
    click.echo(f"✓  Created {target.relative_to(_cwd)}")
    click.echo(f"   project_id: {project_id}")
    click.echo("")
    click.echo("Next: run  mnemon install  to add the memory skill.")


# ── install ───────────────────────────────────────────────────────────────────

@cli.command("install")
@click.option("--cwd",   default=None, help="Repo path (default: current directory)")
@click.option("--force", is_flag=True, help="Overwrite existing skill file")
def install(cwd: str | None, force: bool) -> None:
    """
    Install the Mnemon skill into this repo.
    Copies SKILL.md to .github/skills/mnemon/SKILL.md so the AI knows
    how to handle 'remember this' and related memory requests.

    Examples:
      mnemon install
      mnemon install --force
    """
    _cwd      = Path(cwd) if cwd else Path.cwd()
    skill_dir = _cwd / ".github" / "skills" / "mnemon"
    target    = skill_dir / "SKILL.md"

    if target.exists() and not force:
        click.echo(f"✗  {target.relative_to(_cwd)} already exists. Use --force to overwrite.")
        raise SystemExit(1)

    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_src = Path(__file__).parent / "skill" / "SKILL.md"
    shutil.copy2(skill_src, target)

    click.echo(f"✓  Installed skill → {target.relative_to(_cwd)}")
    click.echo("")
    click.echo("The AI will follow this skill when you say 'remember this'.")
    click.echo("Tip: run  mnemon init  if you haven't set up copilot-instructions.md yet.")


# ── log-commit ────────────────────────────────────────────────────────────────

@cli.command("log-commit")
@click.option("--cwd", default=None)
def log_commit(cwd: str | None) -> None:
    """Log the latest commit. Called automatically by git hooks."""
    async def _run() -> None:
        _cwd = cwd or os.getcwd()
        try:
            project_id = get_project_id(_cwd)
            branch     = get_branch(_cwd)
            ctx        = get_commit_context(_cwd)
        except Exception as e:
            click.echo(f"[mnemon] Skipped: {e}", err=True)
            return

        summary = (
            f"{ctx['message'].splitlines()[0]}"
            f" ({len(ctx['files'])} files)"
            f" by {ctx['author']}"
        )
        async with get_db() as db:
            await run_migrations(db)
            await upsert_project(db, project_id)
            await add_session_log(db, project_id, summary,
                                  branch=branch, source="git-commit", sha=ctx["sha"])
        click.echo(f"[mnemon] {ctx['short_sha']} → {project_id}@{branch}")

    asyncio.run(_run())


# ── read ──────────────────────────────────────────────────────────────────────

@cli.command("read")
@click.option("--cwd",     default=None)
@click.option("--project", default=None, help="Override project_id (owner/repo)")
@click.option("--branch",  default=None, help="Override branch name")
def read(cwd: str | None, project: str | None, branch: str | None) -> None:
    """
    Print the full context block — what the AI sees at session start.

    Examples:
      mnemon read
      mnemon read --project bcgov/nr-waste-plus --branch main
    """
    async def _run() -> None:
        _cwd       = cwd or os.getcwd()
        project_id = project or get_project_id(_cwd)
        _branch    = branch  or get_branch(_cwd)
        async with get_db() as db:
            await run_migrations(db)
            await upsert_project(db, project_id)
            click.echo(await build_context(db, project_id, _branch))

    asyncio.run(_run())


# ── graph ─────────────────────────────────────────────────────────────────────

@cli.command("graph")
@click.option("--cwd",     default=None)
@click.option("--project", default=None)
@click.option("--min",     "importance_min", default=0.0, type=float,
              help="Filter entities at or above this importance (0.0–1.0)")
@click.option("--type",    "entity_type", default=None,
              help="Filter by entity type: component, concept, person, file, system")
def graph(cwd: str | None, project: str | None,
          importance_min: float, entity_type: str | None) -> None:
    """
    Print the knowledge graph for a project.

    Examples:
      mnemon graph
      mnemon graph --min 0.6
      mnemon graph --type component
    """
    async def _run() -> None:
        _cwd       = cwd or os.getcwd()
        project_id = project or get_project_id(_cwd)

        async with get_db() as db:
            await run_migrations(db)
            entities = await list_entities(db, project_id, entity_type=entity_type)
            entities = [e for e in entities if e["importance"] >= importance_min]

            if not entities:
                click.echo("No entities found.")
                return

            from .core.graph import get_observations, get_relations_for
            by_type: dict[str, list] = {}
            for e in entities:
                by_type.setdefault(e["entity_type"], []).append(e)

            click.echo(f"\n Knowledge Graph: {project_id}\n")
            for etype, group in sorted(by_type.items()):
                click.echo(f"  {etype.upper()}S")
                for e in group:
                    imp  = f"  [{e['importance']:.1f}]"
                    scope = f" (branch: {e['branch']})" if e.get("branch") else ""
                    click.echo(f"  ● {e['name']}{imp}{scope}")
                    obs = await get_observations(db, e["id"])
                    for o in obs:
                        click.echo(f"    - {o['content']}")
                    rels = await get_relations_for(db, e["id"])
                    for r in [x for x in rels if x["direction"] == "out"]:
                        click.echo(f"    → {r['relation']}: {r['other_name']}")
                click.echo("")

    asyncio.run(_run())


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
def prune(cwd: str | None, project: str | None,
          below: float, days: int, dry_run: bool) -> None:
    """
    Remove stale low-importance entities from the knowledge graph.
    Only removes entities that are BOTH low-importance AND old.

    Examples:
      mnemon prune
      mnemon prune --below 0.3 --days 60
      mnemon prune --dry-run
    """
    async def _run() -> None:
        _cwd       = cwd or os.getcwd()
        project_id = project or get_project_id(_cwd)

        async with get_db() as db:
            await run_migrations(db)

            if dry_run:
                # Show what would be pruned
                entities = await list_entities(db, project_id)
                candidates = [
                    e for e in entities
                    if e["importance"] < below
                ]
                if not candidates:
                    click.echo("Nothing to prune.")
                    return
                click.echo(f"Would prune {len(candidates)} entities:")
                for e in candidates:
                    click.echo(f"  - {e['name']} [{e['entity_type']}] (importance: {e['importance']:.1f}, updated: {e['updated_at'][:10]})")
                return

            count = await prune_entities(db, project_id,
                                         importance_below=below,
                                         older_than_days=days)
            if count:
                click.echo(f"✓  Pruned {count} entit{'ies' if count != 1 else 'y'} "
                           f"(importance < {below}, not updated in {days}+ days)")
            else:
                click.echo("Nothing to prune.")

    asyncio.run(_run())


# ── projects ──────────────────────────────────────────────────────────────────

@cli.command("projects")
def projects() -> None:
    """List all projects in the memory store."""
    async def _run() -> None:
        async with get_db() as db:
            await run_migrations(db)
            rows = await list_projects(db)
            if not rows:
                click.echo("No projects found.")
                return
            for p in rows:
                parent = f"  (parent: {p['parent_id']})" if p.get("parent_id") else ""
                click.echo(f"  {p['id']}{parent}")

    asyncio.run(_run())
