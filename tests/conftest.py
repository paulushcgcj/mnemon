"""
Pytest fixtures for Mnemon tests.

All tests should use these fixtures for database access.
"""

import asyncio
from pathlib import Path
import tempfile

import pytest
import pytest_asyncio

from mnemon.db.connection import get_db
from mnemon.db.migrations import run_migrations
from mnemon.core.projects import upsert_project


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    # Cleanup after test
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def in_memory_db_path():
    """Return :memory: path for in-memory database."""
    return ":memory:"


@pytest.fixture
def project_id():
    """A test project ID."""
    return "test-owner/test-repo"


@pytest.fixture
def branch():
    """A test branch name."""
    return "test-branch"


async def _setup_project(db, project_id):
    """Helper to create a project in the database."""
    await upsert_project(db, project_id)


@pytest_asyncio.fixture
async def db(temp_db_path, project_id):
    """
    Provide a database connection with migrations run and a test project created.
    
    This fixture:
    1. Creates a temporary database file
    2. Runs all migrations
    3. Creates a test project
    4. Yields the connection
    5. Closes the connection after the test
    """
    async with get_db(path=temp_db_path) as conn:
        await run_migrations(conn)
        await _setup_project(conn, project_id)
        yield conn


@pytest_asyncio.fixture
async def in_memory_db(in_memory_db_path, project_id):
    """
    Provide an in-memory database connection with migrations run and a test project created.
    
    Use this for tests that don't need persistence between runs.
    """
    async with get_db(path=in_memory_db_path) as conn:
        await run_migrations(conn)
        await _setup_project(conn, project_id)
        yield conn
