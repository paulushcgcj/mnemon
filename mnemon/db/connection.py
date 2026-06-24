from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

DB_PATH = Path.home() / ".agent-memory" / "mnemon.db"


@asynccontextmanager
async def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        yield db
