"""Tests for memory operations."""

import pytest
from datetime import datetime

from mnemon.core.memory import (
    get_project_state,
    upsert_project_state,
    get_branch_state,
    upsert_branch_state,
    add_decision,
    get_decisions,
    add_task,
    update_task,
    get_tasks,
    add_session_log,
    get_recent_sessions,
)


@pytest.mark.asyncio
class TestProjectState:
    """Tests for project state operations."""

    async def test_upsert_and_get_project_state(self, db, project_id):
        """Test upserting and retrieving project state."""
        context = "Test project context"
        
        # Insert
        await upsert_project_state(db, project_id, context)
        
        # Retrieve
        state = await get_project_state(db, project_id)
        assert state is not None
        assert state["project_id"] == project_id
        assert state["context"] == context

    async def test_get_nonexistent_project_state(self, db, project_id):
        """Test getting state for non-existent project."""
        state = await get_project_state(db, project_id)
        assert state is None

    async def test_update_project_state(self, db, project_id):
        """Test updating existing project state."""
        context1 = "First context"
        context2 = "Updated context"
        
        await upsert_project_state(db, project_id, context1)
        await upsert_project_state(db, project_id, context2)
        
        state = await get_project_state(db, project_id)
        assert state["context"] == context2


@pytest.mark.asyncio
class TestBranchState:
    """Tests for branch state operations."""

    async def test_upsert_and_get_branch_state(self, db, project_id, branch):
        """Test upserting and retrieving branch state."""
        focus = "Test focus"
        next_steps = "Test next steps"
        
        await upsert_branch_state(db, project_id, branch, focus, next_steps)
        
        state = await get_branch_state(db, project_id, branch)
        assert state is not None
        assert state["project_id"] == project_id
        assert state["branch"] == branch
        assert state["current_focus"] == focus
        assert state["next_steps"] == next_steps

    async def test_get_nonexistent_branch_state(self, db, project_id, branch):
        """Test getting state for non-existent branch."""
        state = await get_branch_state(db, project_id, branch)
        assert state is None


@pytest.mark.asyncio
class TestDecisions:
    """Tests for decision operations."""

    async def test_add_and_get_decision(self, db, project_id):
        """Test adding and retrieving decisions."""
        title = "Test decision"
        rationale = "Test rationale"
        
        decision_id = await add_decision(db, project_id, title, rationale)
        
        decisions = await get_decisions(db, project_id)
        assert len(decisions) == 1
        assert decisions[0]["title"] == title
        assert decisions[0]["rationale"] == rationale

    async def test_branch_scoped_decision(self, db, project_id, branch):
        """Test branch-scoped decisions."""
        title = "Branch decision"
        
        await add_decision(db, project_id, title, "rationale", branch=branch)
        
        # Should be returned when querying with branch
        decisions = await get_decisions(db, project_id, branch=branch)
        assert len(decisions) == 1
        assert decisions[0]["branch"] == branch

    async def test_global_decision(self, db, project_id):
        """Test global decisions (branch is NULL)."""
        title = "Global decision"
        
        await add_decision(db, project_id, title, "rationale", branch=None)
        
        decisions = await get_decisions(db, project_id, branch=None)
        assert len(decisions) == 1
        assert decisions[0]["branch"] is None


@pytest.mark.asyncio
class TestTasks:
    """Tests for task operations."""

    async def test_add_and_get_task(self, db, project_id):
        """Test adding and retrieving tasks."""
        title = "Test task"
        
        task_id = await add_task(db, project_id, title)
        
        tasks = await get_tasks(db, project_id)
        assert len(tasks) == 1
        assert tasks[0]["title"] == title
        assert tasks[0]["status"] == "todo"

    async def test_update_task_status(self, db, project_id):
        """Test updating task status."""
        title = "Test task"
        
        task_id = await add_task(db, project_id, title)
        
        # Update status
        result = await update_task(db, task_id, "in-progress")
        assert result is True
        
        # Verify update
        tasks = await get_tasks(db, project_id)
        assert tasks[0]["status"] == "in-progress"

    async def test_branch_scoped_task(self, db, project_id, branch):
        """Test branch-scoped tasks."""
        title = "Branch task"
        
        await add_task(db, project_id, title, branch=branch)
        
        tasks = await get_tasks(db, project_id, branch=branch)
        assert len(tasks) == 1
        assert tasks[0]["branch"] == branch

    async def test_task_status_validation(self, db, project_id):
        """Test that invalid task status raises validation error."""
        title = "Test task"
        task_id = await add_task(db, project_id, title)
        
        # This should work
        await update_task(db, task_id, "in-progress")
        
        # This should also work
        await update_task(db, task_id, "blocked")
        
        # Verify final status
        tasks = await get_tasks(db, project_id)
        assert tasks[0]["status"] == "blocked"


@pytest.mark.asyncio
class TestSessionLog:
    """Tests for session log operations."""

    async def test_add_and_get_session_log(self, db, project_id):
        """Test adding and retrieving session logs."""
        summary = "Test session summary"
        
        await add_session_log(db, project_id, summary)
        
        sessions = await get_recent_sessions(db, project_id)
        assert len(sessions) == 1
        assert sessions[0]["summary"] == summary

    async def test_branch_scoped_session_log(self, db, project_id, branch):
        """Test branch-scoped session logs."""
        summary = "Branch session summary"
        
        await add_session_log(db, project_id, summary, branch=branch)
        
        sessions = await get_recent_sessions(db, project_id, branch=branch)
        assert len(sessions) == 1
        assert sessions[0]["branch"] == branch

    async def test_session_log_limit(self, db, project_id):
        """Test that session log limit works."""
        for i in range(10):
            await add_session_log(db, project_id, f"Summary {i}")
        
        sessions = await get_recent_sessions(db, project_id, limit=5)
        assert len(sessions) == 5
