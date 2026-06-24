"""Tests for context building operations."""

import pytest

from mnemon.core.context import build_context
from mnemon.core.memory import (
    upsert_project_state,
    upsert_branch_state,
    add_decision,
    add_task,
    add_session_log,
)
from mnemon.core.graph import upsert_entity, add_observation


@pytest.mark.asyncio
class TestBuildContext:
    """Tests for context building."""

    async def test_empty_context(self, db, project_id, branch):
        """Test building context with no data."""
        context = await build_context(db, project_id, branch)
        
        assert f"## {project_id}  |  branch: {branch}" in context
        assert "No session recorded for this branch yet" in context

    async def test_context_with_project_state(self, db, project_id, branch):
        """Test context includes project state."""
        await upsert_project_state(db, project_id, "Test project context")
        
        context = await build_context(db, project_id, branch)
        
        assert "### Project (Global)" in context
        assert "Test project context" in context

    async def test_context_with_branch_state(self, db, project_id, branch):
        """Test context includes branch state."""
        await upsert_branch_state(db, project_id, branch, "Test focus", "Test next steps")
        
        context = await build_context(db, project_id, branch)
        
        assert f"### Branch: `{branch}`" in context
        assert "**Focus:** Test focus" in context
        assert "**Next Steps:**" in context
        assert "Test next steps" in context

    async def test_context_with_decisions(self, db, project_id, branch):
        """Test context includes decisions."""
        await add_decision(db, project_id, "Test decision", "Test rationale", branch=branch)
        
        context = await build_context(db, project_id, branch)
        
        assert "**Branch Decisions:**" in context
        assert "Test decision" in context
        assert "Test rationale" in context

    async def test_context_with_tasks(self, db, project_id, branch):
        """Test context includes tasks."""
        await add_task(db, project_id, "Test task", branch=branch)
        
        context = await build_context(db, project_id, branch)
        
        assert "**Tasks:**" in context
        assert "Test task" in context

    async def test_context_with_session_log(self, db, project_id, branch):
        """Test context includes session log."""
        await add_session_log(db, project_id, "Test session summary", branch=branch)
        
        context = await build_context(db, project_id, branch)
        
        assert "**Recent Sessions:**" in context
        assert "Test session summary" in context

    async def test_context_with_graph_entities(self, db, project_id, branch):
        """Test context includes graph entities above threshold."""
        entity_id = await upsert_entity(db, project_id, "ImportantComponent", "component", importance=0.8, branch=branch)
        await add_observation(db, entity_id, "Important observation")
        
        context = await build_context(db, project_id, branch)
        
        assert "### Knowledge Graph" in context
        assert "ImportantComponent" in context
        assert "Important observation" in context

    async def test_context_excludes_low_importance_entities(self, db, project_id, branch):
        """Test that low importance entities are excluded from context."""
        # Add entity with importance below threshold (0.4)
        await upsert_entity(db, project_id, "LowImportance", "component", importance=0.3, branch=branch)
        
        context = await build_context(db, project_id, branch)
        
        # Low importance entities should not appear in context
        assert "LowImportance" not in context
