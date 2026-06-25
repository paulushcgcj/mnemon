"""
Pytest Configuration
====================
Shared fixtures and configuration for pytest.
"""

from collections.abc import Generator
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from mnemon.core.projects import upsert_project
from mnemon.db.connection import get_db
from mnemon.db.migrations import SCHEMA, run_migrations

# Root directory of the project
PROJECT_ROOT = Path(__file__).parent.parent

# Samples directory
SAMPLES_DIR = PROJECT_ROOT / "tests" / "samples"


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    import tempfile
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


@pytest.fixture
def samples_dir() -> Path:
    """Return the samples directory path."""
    return SAMPLES_DIR


@pytest.fixture
def empty_sql_file(samples_dir: Path) -> Path:
    """Return path to an empty SQL file."""
    return samples_dir / "empty.sql"


@pytest.fixture
def simple_session_file(samples_dir: Path) -> Path:
    """Return path to a simple session JSON file."""
    return samples_dir / "simple_session.json"


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Return a temporary database path."""
    return tmp_path / "test.db"


@pytest_asyncio.fixture
async def db_connection(tmp_db_path: Path) -> Generator[aiosqlite.Connection, None, None]:
    """
    Create a temporary database connection for testing.

    Yields:
        An aiosqlite connection to a temporary database
    """
    # Create the database file
    tmp_db_path.touch()

    # Connect to database
    db = await aiosqlite.connect(str(tmp_db_path))
    db.row_factory = aiosqlite.Row

    # Apply migrations
    await db.executescript(SCHEMA)
    await db.commit()

    yield db

    # Cleanup
    await db.close()
    if tmp_db_path.exists():
        tmp_db_path.unlink()


@pytest.fixture
def mock_db_path(mocker):
    """Mock the DB_PATH environment variable."""
    return ":memory:"


# Sample data fixtures

@pytest.fixture
def sample_session_data() -> dict:
    """Return sample session data."""
    return {
        "sessionId": "test-session-1",
        "projectId": "test/project",
        "createdAt": "2024-01-01T00:00:00Z",
        "lastUpdated": "2024-01-01T00:00:00Z",
        "context": "Test context",
        "entities": [],
        "decisions": [],
        "tasks": [],
    }


@pytest.fixture
def sample_entity_data() -> dict:
    """Return sample entity data."""
    return {
        "id": "entity-1",
        "project_id": "test/project",
        "name": "TestEntity",
        "entity_type": "component",
        "importance": 0.8,
        "content": "Test content",
    }


# Parametrized fixtures for edge cases

@pytest.fixture(params=[
    "",                           # Empty string
    "   ",                       # Whitespace only
    "SELECT * FROM",              # Incomplete SQL
    "DROP TABLE users;",          # Potentially dangerous
    "äöü",                       # Unicode
    "a" * 10000,                 # Very long string
])
def edge_case_input(request) -> str:
    """Parametrized fixture for edge case inputs."""
    return request.param


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
