"""Tests for database migrations."""

import pytest

from mnemon.db.migrations import run_migrations


@pytest.mark.asyncio
class TestMigrations:
    """Tests for database migrations."""

    async def test_migrations_create_all_tables(self, in_memory_db):
        """Test that all expected tables are created."""
        expected_tables = {
            "projects",
            "project_state", 
            "branch_state",
            "decisions",
            "tasks",
            "session_log",
            "entities",
            "observations",
            "relations",
        }
        
        async with in_memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ) as cur:
            rows = await cur.fetchall()
            actual_tables = {row[0] for row in rows}
        
        assert expected_tables.issubset(actual_tables)

    async def test_migrations_are_idempotent(self, in_memory_db):
        """Test that running migrations multiple times doesn't cause errors."""
        # Run migrations again on the same connection
        await run_migrations(in_memory_db)
        
        # Should not raise any errors
        async with in_memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ) as cur:
            rows = await cur.fetchall()
            assert len(rows) > 0

    async def test_migrations_create_indexes(self, in_memory_db):
        """Test that indexes are created."""
        expected_indexes = {
            "idx_decisions_project",
            "idx_tasks_project",
            "idx_session_project",
            "idx_entities_project",
            "idx_observations_entity",
            "idx_relations_from",
            "idx_relations_to",
        }
        
        async with in_memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ) as cur:
            rows = await cur.fetchall()
            actual_indexes = {row[0] for row in rows}
        
        assert expected_indexes.issubset(actual_indexes)
