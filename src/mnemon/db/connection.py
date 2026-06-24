import os
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

# Default database path
DEFAULT_DB_PATH = Path.home() / ".agent-memory" / "mnemon.db"


def get_db_path() -> Path:
    """
    Get the database path from environment or use default.

    The path can be configured via:
    - MNEMON_DB_PATH environment variable
    - Default: ~/.agent-memory/mnemon.db

    For in-memory database (useful for testing), set:
    - MNEMON_DB_PATH=:memory:

    Returns:
        Path to the SQLite database file, or ":memory:" for in-memory
    """
    env_path = os.environ.get("MNEMON_DB_PATH")
    if env_path:
        # Handle empty string
        if not env_path.strip():
            return DEFAULT_DB_PATH
        # Handle in-memory database
        if env_path in (":memory:", "memory"):
            return Path(":memory:")
        return Path(env_path)
    return DEFAULT_DB_PATH


@asynccontextmanager
async def get_db(path: str | Path | None = None):
    """
    Get a database connection.

    Args:
        path: Optional path override. If None, uses get_db_path().
              Can be a string path or ":memory:" for in-memory database.

    Yields:
        aiosqlite.Connection with WAL mode and foreign keys enabled
    """
    db_path = Path(path) if path else get_db_path()

    # For in-memory databases, don't try to create parent directories
    if str(db_path) != ":memory:":
        db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        yield db
