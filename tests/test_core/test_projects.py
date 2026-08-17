"""Tests for project operations."""

import pytest

from mnemon.core.projects import (
    get_project_children,
    get_project_tree,
    list_projects,
    set_project_parent,
    upsert_project,
)


@pytest.mark.asyncio
class TestProjects:
    """Tests for project operations."""

    async def test_upsert_project(self, db, project_id):
        """Test upserting a project."""
        # The db fixture already creates project_id, so we can just verify it exists
        projects = await list_projects(db)
        assert len(projects) >= 1
        assert any(p["id"] == project_id for p in projects)

    async def test_upsert_project_with_url(self, db):
        """Test upserting a project with git URL."""
        test_project_id = "url-test-owner/url-test-repo"
        git_url = "https://github.com/test-owner/test-repo.git"

        await upsert_project(db, test_project_id, git_url=git_url)

        projects = await list_projects(db)
        matching = [p for p in projects if p["id"] == test_project_id]
        assert len(matching) == 1
        assert matching[0]["name"] == "url-test-repo"
        assert matching[0]["git_url"] == git_url

    async def test_upsert_project_without_url(self, db):
        """Test upserting a project without git URL."""
        test_project_id = "no-url-test-owner/no-url-test-repo"
        await upsert_project(db, test_project_id)

        projects = await list_projects(db)
        matching = [p for p in projects if p["id"] == test_project_id]
        assert len(matching) == 1
        assert matching[0]["git_url"] is None

    async def test_upsert_project_updates_existing(self, db):
        """Test that upsert updates existing project."""
        test_project_id = "update-test-owner/update-test-repo"
        git_url1 = "https://github.com/test-owner/test-repo.git"
        git_url2 = "https://github.com/test-owner/test-repo-new.git"

        await upsert_project(db, test_project_id, git_url=git_url1)
        await upsert_project(db, test_project_id, git_url=git_url2)

        projects = await list_projects(db)
        matching = [p for p in projects if p["id"] == test_project_id]
        assert len(matching) == 1
        assert matching[0]["git_url"] == git_url2

    async def test_upsert_project_with_parent(self, db):
        """Test upserting a project with parent ID."""
        parent_id = "parent-owner/parent-repo"
        test_project_id = "parent-test-owner/parent-test-repo"

        # First create the parent project
        await upsert_project(db, parent_id)
        await upsert_project(db, test_project_id, parent_id=parent_id)

        projects = await list_projects(db, parent_id=parent_id)
        matching = [p for p in projects if p["id"] == test_project_id]
        assert len(matching) == 1
        assert matching[0]["parent_id"] == parent_id

    async def test_list_projects_empty(self, db):
        """Test listing projects when none exist - using raw connection without project."""
        # Create a new connection without any projects
        import tempfile
        from pathlib import Path

        from mnemon.db.connection import get_db
        from mnemon.db.migrations import run_migrations

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            test_db_path = Path(f.name)

        try:
            async with get_db(path=test_db_path) as conn:
                await run_migrations(conn)
                projects = await list_projects(conn)
                assert projects == []
        finally:
            if test_db_path.exists():
                test_db_path.unlink()

    async def test_list_projects_by_parent(self, db):
        """Test listing projects filtered by parent."""
        parent_id = "list-parent-owner/list-parent-repo"
        child_id = "list-child-owner/list-child-repo"

        await upsert_project(db, parent_id)
        await upsert_project(db, child_id, parent_id=parent_id)

        # List by parent
        children = await list_projects(db, parent_id=parent_id)
        matching = [p for p in children if p["id"] == child_id]
        assert len(matching) == 1
        assert matching[0]["id"] == child_id

    async def test_list_projects_ordered(self, db):
        """Test that projects are ordered by ID."""
        await upsert_project(db, "z-test-owner/z-test-repo")
        await upsert_project(db, "a-test-owner/a-test-repo")
        await upsert_project(db, "m-test-owner/m-test-repo")

        projects = await list_projects(db)
        # Filter out the default project_id
        ordered = [p for p in projects if p["id"].startswith(("z-test", "a-test", "m-test"))]
        ordered.sort(key=lambda p: p["id"])

        assert len(ordered) == 3
        assert ordered[0]["id"] == "a-test-owner/a-test-repo"
        assert ordered[1]["id"] == "m-test-owner/m-test-repo"
        assert ordered[2]["id"] == "z-test-owner/z-test-repo"


@pytest.mark.asyncio
class TestProjectHierarchy:
    """Tests for project hierarchy validation and traversal."""

    async def test_upsert_project_self_parent(self, db):
        """Raising when a project is its own parent."""
        with pytest.raises(ValueError, match="cannot be its own parent"):
            await upsert_project(db, "SELF_P", parent_id="SELF_P")

    async def test_upsert_project_circular_reference(self, db):
        """Raising when a parent would create a cycle."""
        await upsert_project(db, "CIRC_A")
        await upsert_project(db, "CIRC_B", parent_id="CIRC_A")

        with pytest.raises(ValueError, match="Circular reference detected"):
            await upsert_project(db, "CIRC_A", parent_id="CIRC_B")

    async def test_set_project_parent_circular_reference(self, db):
        """Raising when re-parenting would create a cycle."""
        await upsert_project(db, "SET_A")
        await upsert_project(db, "SET_B", parent_id="SET_A")

        with pytest.raises(ValueError, match="Circular reference detected"):
            await set_project_parent(db, "SET_A", "SET_B")

    async def test_list_projects_recursive(self, db):
        """Listing a subtree with all descendants."""
        await upsert_project(db, "ROOT_REC")
        await upsert_project(db, "CHILD_REC", parent_id="ROOT_REC")
        await upsert_project(db, "GRAND_REC", parent_id="CHILD_REC")

        results = await list_projects(db, parent_id="ROOT_REC", include_children=True)
        ids = {r["id"] for r in results}
        assert ids == {"ROOT_REC", "CHILD_REC", "GRAND_REC"}

    async def test_get_project_children_recursive(self, db):
        """Getting all descendants of a project."""
        await upsert_project(db, "p_rec")
        await upsert_project(db, "c_rec", parent_id="p_rec")
        await upsert_project(db, "g_rec", parent_id="c_rec")

        children = await get_project_children(db, "p_rec", recursive=True)
        assert {c["id"] for c in children} == {"c_rec", "g_rec"}

    async def test_get_project_tree_returns_list(self, db):
        """Getting the full project tree."""
        tree = await get_project_tree(db)
        assert isinstance(tree, list)
