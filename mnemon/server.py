from typing import Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from .db.connection import get_db
from .db.migrations import run_migrations
from .core.context import build_context
from .core.memory import (
    add_decision, add_session_log, add_task,
    update_task, upsert_branch_state, upsert_project_state,
)
from .core.graph import (
    upsert_entity, add_observation, add_relation,
    delete_entity, delete_observation, delete_relation,
    search_entities, get_full_graph, prune_entities,
    get_entity_by_name, get_observations, get_relations_for,
)
from .core.projects import list_projects, upsert_project

mcp = FastMCP("mnemon")


# ── Input models ──────────────────────────────────────────────────────────────

class DecisionInput(BaseModel):
    title: str
    rationale: str
    branch_scoped: bool = False

class TaskInput(BaseModel):
    title: str
    status: str = "todo"
    notes: Optional[str] = None
    is_global: bool = False


# ── Session memory tools ──────────────────────────────────────────────────────

@mcp.tool()
async def memory_read(project_id: str, branch: str) -> str:
    """
    Call at the START of every session — before anything else.
    Returns full context: global state, decisions, knowledge graph entities,
    branch focus, tasks, and recent session history.
    project_id: GitHub 'owner/repo' slug, e.g. 'bcgov/nr-waste-plus'
    branch: current git branch name
    """
    async with get_db() as db:
        await run_migrations(db)
        await upsert_project(db, project_id)
        return await build_context(db, project_id, branch)


@mcp.tool()
async def memory_summarize(
    project_id: str,
    branch: str,
    summary: str,
    current_focus: str,
    next_steps: str,
    decisions: list[DecisionInput] = [],
    tasks_done: list[str] = [],
    tasks_new: list[TaskInput] = [],
) -> str:
    """
    Call at the END of every session — always, even if the user doesn't ask.
    Persists focus, next steps, decisions, and task updates.
    summary:       What was accomplished this session.
    current_focus: What is actively being worked on right now.
    next_steps:    What comes next.
    decisions:     Architectural or design decisions made.
    tasks_done:    Task IDs (from memory_read) to mark done.
    tasks_new:     New tasks discovered this session.
    """
    async with get_db() as db:
        await run_migrations(db)
        await upsert_project(db, project_id)
        await upsert_branch_state(db, project_id, branch, current_focus, next_steps)
        await add_session_log(db, project_id, summary, branch=branch, source="ai")
        for d in decisions:
            await add_decision(db, project_id, d.title, d.rationale,
                               branch=branch if d.branch_scoped else None)
        for tid in tasks_done:
            await update_task(db, tid, "done")
        for t in tasks_new:
            await add_task(db, project_id, t.title,
                           branch=None if t.is_global else branch,
                           notes=t.notes, status=t.status)
    return "Memory updated."


@mcp.tool()
async def memory_task_update(
    task_id: str, status: str, notes: Optional[str] = None
) -> str:
    """
    Update a task status mid-session.
    status: 'todo' | 'in-progress' | 'done' | 'blocked'
    Use task IDs from memory_read (shown in backticks).
    """
    async with get_db() as db:
        await run_migrations(db)
        ok = await update_task(db, task_id, status, notes)
        return "Task updated." if ok else f"Task '{task_id}' not found."


@mcp.tool()
async def memory_project_set_context(project_id: str, context: str) -> str:
    """Set or update the global context for a project (stack, conventions, overview)."""
    async with get_db() as db:
        await run_migrations(db)
        await upsert_project(db, project_id)
        await upsert_project_state(db, project_id, context)
    return "Project context updated."


@mcp.tool()
async def memory_log_commit(
    project_id: str, branch: str, sha: str, message: str,
    author: str = "", files: list[str] = [],
) -> str:
    """Log a git commit to session history. Called by the git hook, not the AI."""
    async with get_db() as db:
        await run_migrations(db)
        await upsert_project(db, project_id)
        summary = (
            f"{message.splitlines()[0]}"
            + (f" ({len(files)} files)" if files else "")
            + (f" by {author}" if author else "")
        )
        await add_session_log(db, project_id, summary,
                              branch=branch, source="git-commit", sha=sha)
    return f"Commit {sha[:8]} logged."


@mcp.tool()
async def memory_project_list(parent_id: Optional[str] = None) -> str:
    """List all known projects, optionally filtered by parent."""
    async with get_db() as db:
        await run_migrations(db)
        projects = await list_projects(db, parent_id=parent_id)
        if not projects:
            return "No projects found."
        return "\n".join(
            f"- {p['id']}" + (f" (parent: {p['parent_id']})" if p.get("parent_id") else "")
            for p in projects
        )


# ── Knowledge graph tools ─────────────────────────────────────────────────────

@mcp.tool()
async def graph_entity_upsert(
    project_id: str,
    name: str,
    entity_type: str,
    observations: list[str] = [],
    importance: float = 0.5,
    branch: Optional[str] = None,
) -> str:
    """
    Create or update a named entity and add observations to it.
    name:         Unique identifier for this entity within the project, e.g. 'WasteVolumeController'
    entity_type:  'component' | 'concept' | 'person' | 'file' | 'system' | 'custom'
    observations: List of facts to record, e.g. ["handles CRUD for waste volumes", "uses JPA"]
    importance:   0.0–1.0 — controls whether this entity surfaces in memory_read context.
                  Use 0.8+ for core architectural components, 0.3 for minor utilities.
    branch:       Omit for project-wide entities. Set for branch-specific knowledge.
    """
    async with get_db() as db:
        await run_migrations(db)
        await upsert_project(db, project_id)
        entity_id = await upsert_entity(db, project_id, name, entity_type, importance, branch)
        for obs in observations:
            await add_observation(db, entity_id, obs)
    obs_count = len(observations)
    return f"Entity '{name}' saved with {obs_count} observation{'s' if obs_count != 1 else ''}."


@mcp.tool()
async def graph_observe(
    project_id: str,
    entity_name: str,
    observation: str,
) -> str:
    """
    Add a single observation (fact) to an existing entity.
    Use this mid-session when you learn something new about a known entity.
    """
    async with get_db() as db:
        await run_migrations(db)
        entity = await get_entity_by_name(db, project_id, entity_name)
        if not entity:
            return f"Entity '{entity_name}' not found. Create it first with graph_entity_upsert."
        await add_observation(db, entity["id"], observation)
    return f"Observation added to '{entity_name}'."


@mcp.tool()
async def graph_relate(
    project_id: str,
    from_entity: str,
    relation: str,
    to_entity: str,
) -> str:
    """
    Add a typed directed relationship between two entities.
    Both entities must already exist. Common relation types:
    'calls', 'implements', 'depends_on', 'owns', 'uses', 'extends', 'triggers'
    Example: graph_relate('WasteVolumeForm', 'calls', 'WasteVolumeController')
    """
    async with get_db() as db:
        await run_migrations(db)
        from_e = await get_entity_by_name(db, project_id, from_entity)
        to_e   = await get_entity_by_name(db, project_id, to_entity)
        if not from_e:
            return f"Entity '{from_entity}' not found."
        if not to_e:
            return f"Entity '{to_entity}' not found."
        await add_relation(db, project_id, from_e["id"], to_e["id"], relation)
    return f"'{from_entity}' —[{relation}]→ '{to_entity}'"


@mcp.tool()
async def graph_search(
    project_id: str,
    query: str,
    entity_type: Optional[str] = None,
    limit: int = 10,
) -> str:
    """
    Search entities by name or observation content.
    Returns matching entities with their observations and relations.
    Useful when you want to find what Mnemon knows about a topic.
    """
    async with get_db() as db:
        await run_migrations(db)
        entities = await search_entities(db, project_id, query, entity_type, limit)
        if not entities:
            return f"No entities found matching '{query}'."

        lines = [f"Search results for '{query}':", ""]
        for e in entities:
            obs  = await get_observations(db, e["id"])
            rels = await get_relations_for(db, e["id"])
            lines.append(f"**{e['name']}** [{e['entity_type']}] (importance: {e['importance']:.1f})")
            for o in obs:
                lines.append(f"  - {o['content']}")
            for r in [x for x in rels if x["direction"] == "out"]:
                lines.append(f"  → {r['relation']}: {r['other_name']}")
            lines.append("")
        return "\n".join(lines)


@mcp.tool()
async def graph_read(
    project_id: str,
    branch: Optional[str] = None,
    importance_min: float = 0.0,
) -> str:
    """
    Read the full knowledge graph for a project.
    importance_min: Filter to entities at or above this importance (0.0 = all).
    Returns all entities with observations and relations, grouped by type.
    """
    async with get_db() as db:
        await run_migrations(db)
        entities = await get_full_graph(db, project_id, branch=branch,
                                        importance_min=importance_min, limit=100)
        if not entities:
            return "No entities in graph yet."

        by_type: dict[str, list] = {}
        for e in entities:
            by_type.setdefault(e["entity_type"], []).append(e)

        lines = [f"Knowledge graph: {project_id}", ""]
        for etype, group in sorted(by_type.items()):
            lines.append(f"### {etype.capitalize()}s")
            for e in group:
                lines.append(f"- **{e['name']}** (importance: {e['importance']:.1f})")
                for o in e["observations"]:
                    lines.append(f"  - {o['content']}")
                for r in [x for x in e["relations"] if x["direction"] == "out"]:
                    lines.append(f"  → {r['relation']}: {r['other_name']}")
            lines.append("")
        return "\n".join(lines)


@mcp.tool()
async def graph_forget(
    project_id: str,
    entity_name: str,
    observation_id: Optional[str] = None,
) -> str:
    """
    Remove an entity entirely, or remove a specific observation from it.
    observation_id: if provided, deletes only that observation. Otherwise deletes the whole entity.
    Observation IDs are visible in graph_search results.
    """
    async with get_db() as db:
        await run_migrations(db)
        if observation_id:
            ok = await delete_observation(db, observation_id)
            return "Observation deleted." if ok else f"Observation '{observation_id}' not found."
        ok = await delete_entity(db, project_id, entity_name)
        return f"Entity '{entity_name}' deleted." if ok else f"Entity '{entity_name}' not found."


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    mcp.run()
