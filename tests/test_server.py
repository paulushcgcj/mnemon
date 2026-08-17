"""Tests for MCP server tool wrappers."""

import pytest

from mnemon import server
from mnemon.core.graph import get_entity_by_name, get_observations
from mnemon.core.memory import add_session_log, add_task, get_recent_sessions, get_tasks
from mnemon.core.projects import upsert_project
from mnemon.db.connection import get_db
from mnemon.db.migrations import run_migrations


@pytest.fixture
def server_db(tmp_path, monkeypatch):
    db_path = tmp_path / "server.db"
    monkeypatch.setenv("MNEMON_DB_PATH", str(db_path))
    return db_path


async def test_memory_tools_persist_context_tasks_and_commits(server_db):
    project_id = "owner/repo"
    branch = "main"

    empty = await server.memory_read(project_id, branch)
    assert project_id in empty

    async with get_db(path=server_db) as db:
        await run_migrations(db)
        task_id = await add_task(db, project_id, "Existing task", branch=branch)

    result = await server.memory_summarize(
        project_id,
        branch,
        "Finished useful work",
        "Current focus",
        "Next step",
        decisions=[
            server.DecisionInput(
                title="Use sqlite", rationale="Small local store", branch_scoped=True
            )
        ],
        tasks_done=[task_id],
        tasks_new=[
            server.TaskInput(
                title="Global follow-up", status="blocked", notes="waiting", is_global=True
            )
        ],
    )
    assert result == "Memory updated."

    updated = await server.memory_task_update(task_id, "in-progress", notes="reopened")
    assert updated == "Task updated."
    missing = await server.memory_task_update("missing", "done")
    assert missing == "Task 'missing' not found."

    assert (
        await server.memory_project_set_context(project_id, "Project overview")
        == "Project context updated."
    )
    assert await server.memory_log_commit(
        project_id, branch, "abcdef123456", "Commit subject", "Ada", ["a.py"]
    )

    async with get_db(path=server_db) as db:
        await run_migrations(db)
        tasks = await get_tasks(db, project_id, branch=branch)
        sessions = await get_recent_sessions(db, project_id, branch=branch, limit=5)

    assert tasks[0]["status"] == "in-progress"
    assert any("Commit subject" in session["summary"] for session in sessions)


async def test_project_tools_list_parent_children_and_tree(server_db):
    async with get_db(path=server_db) as db:
        await run_migrations(db)
        await upsert_project(db, "root/app")
        await upsert_project(db, "root/api")

    no_projects = await server.memory_project_list(parent_id="missing/root")
    assert no_projects == "No projects found."

    assert (
        await server.project_set_parent("root/api", "root/app") == "Project 'root/api' parent set."
    )
    assert (
        await server.project_set_parent("missing/project", "root/app")
        == "Project 'missing/project' not found."
    )

    projects = await server.memory_project_list()
    assert "- root/api (parent: root/app)" in projects

    children = await server.project_list_children("root/app")
    assert "- root/api" in children

    no_children = await server.project_list_children("root/api")
    assert no_children == "No children found for project 'root/api'."

    tree = await server.project_list_tree()
    assert "- root/app" in tree
    assert "  - root/api" in tree

    assert await server.project_set_parent("root/api") == "Project 'root/api' parent removed."


async def test_graph_tools_cover_success_empty_and_missing_paths(server_db):
    project_id = "owner/repo"

    empty_read = await server.graph_read(project_id)
    assert empty_read == "No entities in graph yet."

    saved = await server.graph_entity_upsert(
        project_id,
        "Api",
        "component",
        observations=["Handles requests", "Calls database"],
        importance=0.9,
        branch="main",
    )
    assert saved == "Entity 'Api' saved with 2 observations."

    saved_without_observations = await server.graph_entity_upsert(project_id, "Db", "system")
    assert saved_without_observations == "Entity 'Db' saved with 0 observations."

    assert await server.graph_observe(project_id, "Missing", "Fact") == (
        "Entity 'Missing' not found. Create it first with graph_entity_upsert."
    )
    assert (
        await server.graph_observe(project_id, "Api", "New fact") == "Observation added to 'Api'."
    )

    assert (
        await server.graph_relate(project_id, "Missing", "uses", "Db")
        == "Entity 'Missing' not found."
    )
    assert (
        await server.graph_relate(project_id, "Api", "uses", "Missing")
        == "Entity 'Missing' not found."
    )
    assert await server.graph_relate(project_id, "Api", "uses", "Db") == "'Api' —[uses]→ 'Db'"

    empty_search = await server.graph_search(project_id, "none")
    assert empty_search == "No entities found matching 'none'."
    search = await server.graph_search(project_id, "Api", limit=5)
    assert "Search results for 'Api'" in search
    assert "Handles requests" in search
    assert "uses: Db" in search

    graph = await server.graph_read(project_id, branch="main", importance_min=0.5)
    assert "### Components" in graph
    assert "**Api**" in graph

    async with get_db(path=server_db) as db:
        await run_migrations(db)
        entity = await get_entity_by_name(db, project_id, "Api")
        observations = await get_observations(db, entity["id"])

    assert (
        await server.graph_forget(project_id, "Api", observation_id=observations[0]["id"])
        == "Observation deleted."
    )
    assert (
        await server.graph_forget(project_id, "Api", observation_id="missing")
        == "Observation 'missing' not found."
    )
    assert await server.graph_forget(project_id, "Api") == "Entity 'Api' deleted."
    assert await server.graph_forget(project_id, "Api") == "Entity 'Api' not found."


def test_input_validation_and_main(monkeypatch):
    assert server.TaskInput(title="Task", status="todo").status == "todo"
    with pytest.raises(ValueError):
        server.TaskInput(title="Task", status="invalid")

    called = []
    monkeypatch.setattr(server.mcp, "run", lambda: called.append(True))
    server.main()
    assert called == [True]


async def test_memory_task_create_persists_task(server_db):
    project_id = "owner/repo"
    branch = "main"

    result = await server.memory_task_create(
        project_id, "Add logging", branch=branch, notes="structlog"
    )
    assert "Task created (id: `" in result
    task_id = result.split("`")[1]

    async with get_db(path=server_db) as db:
        await run_migrations(db)
        tasks = await get_tasks(db, project_id, branch=branch)

    assert len(tasks) == 1
    assert tasks[0]["id"] == task_id
    assert tasks[0]["title"] == "Add logging"
    assert tasks[0]["status"] == "todo"
    assert tasks[0]["notes"] == "structlog"


async def test_memory_task_create_branch_and_status(server_db):
    project_id = "owner/repo"

    await server.memory_task_create(project_id, "Global task", status="blocked")
    await server.memory_task_create(project_id, "Branch task", branch="feature-x")

    async with get_db(path=server_db) as db:
        await run_migrations(db)
        global_tasks = await get_tasks(db, project_id, branch=None)
        branch_tasks = await get_tasks(db, project_id, branch="feature-x")

    assert len(global_tasks) == 1
    assert global_tasks[0]["title"] == "Global task"
    assert global_tasks[0]["status"] == "blocked"
    assert global_tasks[0]["branch"] is None
    branch_task = next(t for t in branch_tasks if t["title"] == "Branch task")
    assert branch_task["branch"] == "feature-x"


async def test_memory_task_create_invalid_status_raises(server_db):
    with pytest.raises(ValueError):
        await server.memory_task_create("owner/repo", "Bad task", status="invalid")


async def _backdate_entity(db, name: str, days: int = 60) -> None:
    """Backdate an entity's updated_at so it counts as stale."""
    await db.execute(
        "UPDATE entities SET updated_at = datetime('now', ? || ' days') WHERE name = ?",
        (f"-{days}", name),
    )
    await db.commit()


async def test_graph_prune_dry_run_previews_without_deleting(server_db):
    project_id = "owner/repo"
    await server.graph_entity_upsert(project_id, "Stale", "component", importance=0.1)
    async with get_db(path=server_db) as db:
        await run_migrations(db)
        await _backdate_entity(db, "Stale")

    result = await server.graph_prune(
        project_id, importance_below=0.2, older_than_days=30, dry_run=True
    )
    assert "Would prune 1 stale entity:" in result
    assert "- Stale [component]" in result

    async with get_db(path=server_db) as db:
        await run_migrations(db)
        entity = await get_entity_by_name(db, project_id, "Stale")
    assert entity is not None


async def test_graph_prune_deletes_stale_entities(server_db):
    project_id = "owner/repo"
    await server.graph_entity_upsert(project_id, "Stale", "component", importance=0.1)
    async with get_db(path=server_db) as db:
        await run_migrations(db)
        await _backdate_entity(db, "Stale")

    result = await server.graph_prune(project_id, importance_below=0.2, older_than_days=30)
    assert result == "Pruned 1 stale entity."

    async with get_db(path=server_db) as db:
        await run_migrations(db)
        entity = await get_entity_by_name(db, project_id, "Stale")
    assert entity is None


async def test_graph_prune_nothing_to_prune(server_db):
    project_id = "owner/repo"
    await server.graph_entity_upsert(project_id, "Core", "system", importance=0.9)

    result = await server.graph_prune(project_id, importance_below=0.2, older_than_days=30)
    assert result == "Nothing to prune."


async def test_memory_search_returns_cross_category_results(server_db):
    project_id = "owner/repo"
    branch = "main"
    await server.graph_entity_upsert(
        project_id, "AuthService", "component", importance=0.8, branch=branch
    )
    async with get_db(path=server_db) as db:
        await run_migrations(db)
        await add_task(db, project_id, "Add auth middleware", branch=branch)
        await add_session_log(db, project_id, "Worked on auth flows", branch=branch)

    result = await server.memory_search(project_id, "auth", branch=branch)
    assert "Search results for 'auth':" in result
    assert "Entities:" in result
    assert "**AuthService**" in result
    assert "Tasks:" in result
    assert "Worked on auth flows" in result


async def test_memory_search_no_matches(server_db):
    result = await server.memory_search("owner/repo", "nonexistent")
    assert "Search results for 'nonexistent':" in result
    assert "Entities:" not in result


async def test_memory_summarize_completed_tasks_alias(server_db):
    project_id = "owner/repo"
    branch = "main"
    async with get_db(path=server_db) as db:
        await run_migrations(db)
        await upsert_project(db, project_id)
        task_id = await add_task(db, project_id, "Task to finish", branch=branch)

    result = await server.memory_summarize(
        project_id, branch, "Summary", "Focus", "Next", completed_tasks=[task_id]
    )
    assert result == "Memory updated."

    async with get_db(path=server_db) as db:
        await run_migrations(db)
        tasks = await get_tasks(db, project_id, branch=branch)
    assert tasks[0]["status"] == "done"


async def test_memory_summarize_new_tasks_alias(server_db):
    project_id = "owner/repo"
    branch = "main"

    result = await server.memory_summarize(
        project_id,
        branch,
        "Summary",
        "Focus",
        "Next",
        new_tasks=[server.TaskInput(title="Created via alias")],
    )
    assert result == "Memory updated."

    async with get_db(path=server_db) as db:
        await run_migrations(db)
        tasks = await get_tasks(db, project_id, branch=branch)
    assert any(t["title"] == "Created via alias" for t in tasks)


async def test_memory_summarize_canonical_wins_over_alias(server_db):
    project_id = "owner/repo"
    branch = "main"
    async with get_db(path=server_db) as db:
        await run_migrations(db)
        await upsert_project(db, project_id)
        alias_id = await add_task(db, project_id, "Alias task", branch=branch)
        canonical_id = await add_task(db, project_id, "Canonical task", branch=branch)

    await server.memory_summarize(
        project_id,
        branch,
        "Summary",
        "Focus",
        "Next",
        tasks_done=[canonical_id],
        completed_tasks=[alias_id],
    )

    async with get_db(path=server_db) as db:
        await run_migrations(db)
        tasks = await get_tasks(db, project_id, branch=branch)
    by_title = {t["title"]: t for t in tasks}
    assert by_title["Canonical task"]["status"] == "done"
    assert by_title["Alias task"]["status"] == "todo"
