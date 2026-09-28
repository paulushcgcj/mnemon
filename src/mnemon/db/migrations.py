import aiosqlite

from ..core.constants import FTS_MIGRATION_VERSION, FTS_TABLES, prepare_fts_text

SCHEMA = """
-- ── Project hierarchy ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS projects (
    id         TEXT PRIMARY KEY,           -- 'owner/repo' from GitHub URL
    parent_id  TEXT REFERENCES projects(id),
    name       TEXT,
    git_url    TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- ── Project memory (session layer) ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS project_state (
    project_id TEXT PRIMARY KEY REFERENCES projects(id),
    context    TEXT,                       -- stack, conventions, overview
    updated_at TEXT DEFAULT (datetime('now'))
);

-- One active row per project+branch, overwritten each session
CREATE TABLE IF NOT EXISTS branch_state (
    project_id    TEXT NOT NULL REFERENCES projects(id),
    branch        TEXT NOT NULL,
    current_focus TEXT,
    next_steps    TEXT,
    updated_at    TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (project_id, branch)
);

-- Decisions: global (branch IS NULL) or branch-scoped
CREATE TABLE IF NOT EXISTS decisions (
    id         TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    project_id TEXT NOT NULL REFERENCES projects(id),
    branch     TEXT,
    title      TEXT NOT NULL,
    rationale  TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Tasks: global or branch-scoped
CREATE TABLE IF NOT EXISTS tasks (
    id         TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    project_id TEXT NOT NULL REFERENCES projects(id),
    branch     TEXT,
    title      TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'todo'
               CHECK(status IN ('todo','in-progress','done','blocked')),
    source     TEXT NOT NULL DEFAULT 'ai',
    notes      TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Append-only session history
CREATE TABLE IF NOT EXISTS session_log (
    id         TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    project_id TEXT NOT NULL REFERENCES projects(id),
    branch     TEXT,
    summary    TEXT,
    source     TEXT NOT NULL DEFAULT 'ai',  -- 'ai' | 'git-commit'
    sha        TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- ── Knowledge graph (entity layer) ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS entities (
    id          TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    project_id  TEXT NOT NULL REFERENCES projects(id),
    branch      TEXT,                      -- NULL = project-wide entity
    name        TEXT NOT NULL,             -- unique per project, e.g. 'WasteVolumeController'
    entity_type TEXT NOT NULL DEFAULT 'concept',
                                           -- 'component' | 'concept' | 'person' | 'file' | 'system' | 'custom'
    importance  REAL NOT NULL DEFAULT 0.5, -- 0.0–1.0, controls context injection priority
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(project_id, name)
);

-- Facts about entities — append-only, never updated in place
CREATE TABLE IF NOT EXISTS observations (
    id         TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    entity_id  TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    content    TEXT NOT NULL,
    source     TEXT NOT NULL DEFAULT 'ai',  -- 'ai' | 'git-commit' | 'manual'
    created_at TEXT DEFAULT (datetime('now'))
);

-- Typed directed edges between entities
CREATE TABLE IF NOT EXISTS relations (
    id         TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    project_id TEXT NOT NULL REFERENCES projects(id),
    from_id    TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    to_id      TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation   TEXT NOT NULL,              -- 'calls' | 'implements' | 'depends_on' | 'owns' | 'uses' | custom
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(from_id, to_id, relation)
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_decisions_project  ON decisions(project_id, branch);
CREATE INDEX IF NOT EXISTS idx_tasks_project      ON tasks(project_id, branch, status);
CREATE INDEX IF NOT EXISTS idx_session_project    ON session_log(project_id, branch, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_entities_project   ON entities(project_id, entity_type, importance DESC);
CREATE INDEX IF NOT EXISTS idx_observations_entity ON observations(entity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_relations_from     ON relations(from_id);
CREATE INDEX IF NOT EXISTS idx_relations_to       ON relations(to_id);

-- ── Full-text search (FTS5) ──────────────────────────────────────────────────

-- Mirror tables for hybrid search, synced on every write and populated once
-- by the backfill migration below. `ref` links a row back to its source table
-- id; entities_fts keeps observation rows under the same ref so scores for
-- an entity fold together.
CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(ref UNINDEXED, obs_ref UNINDEXED, content);
CREATE VIRTUAL TABLE IF NOT EXISTS decisions_fts USING fts5(ref UNINDEXED, title, rationale);
CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(ref UNINDEXED, title, notes);
CREATE VIRTUAL TABLE IF NOT EXISTS sessions_fts USING fts5(ref UNINDEXED, summary);
"""


async def backfill_fts(db: aiosqlite.Connection) -> None:
    """
    Populate the FTS mirror tables from their source tables.

    Gated on the PRAGMA user_version marker so it runs once per database.
    A concurrent double-run deletes and re-inserts every row inside one
    transaction, so it cannot produce duplicates.
    """
    async with db.execute("PRAGMA user_version") as cursor:
        row = await cursor.fetchone()
    if row is not None and row[0] >= FTS_MIGRATION_VERSION:
        return

    for table in FTS_TABLES.values():
        await db.execute(f"DELETE FROM {table}")

    async with db.execute("SELECT id, name FROM entities") as cursor:
        entity_rows = await cursor.fetchall()
    await db.executemany(
        "INSERT INTO entities_fts (ref, obs_ref, content) VALUES (?, NULL, ?)",
        [(r["id"], prepare_fts_text(r["name"])) for r in entity_rows],
    )

    async with db.execute("SELECT id, entity_id, content FROM observations") as cursor:
        observation_rows = await cursor.fetchall()
    await db.executemany(
        "INSERT INTO entities_fts (ref, obs_ref, content) VALUES (?, ?, ?)",
        [(r["entity_id"], r["id"], prepare_fts_text(r["content"])) for r in observation_rows],
    )

    async with db.execute("SELECT id, title, rationale FROM decisions") as cursor:
        decision_rows = await cursor.fetchall()
    await db.executemany(
        "INSERT INTO decisions_fts (ref, title, rationale) VALUES (?, ?, ?)",
        [
            (r["id"], prepare_fts_text(r["title"]), prepare_fts_text(r["rationale"]))
            for r in decision_rows
        ],
    )

    async with db.execute("SELECT id, title, notes FROM tasks") as cursor:
        task_rows = await cursor.fetchall()
    await db.executemany(
        "INSERT INTO tasks_fts (ref, title, notes) VALUES (?, ?, ?)",
        [(r["id"], prepare_fts_text(r["title"]), prepare_fts_text(r["notes"])) for r in task_rows],
    )

    async with db.execute("SELECT id, summary FROM session_log") as cursor:
        session_rows = await cursor.fetchall()
    await db.executemany(
        "INSERT INTO sessions_fts (ref, summary) VALUES (?, ?)",
        [(r["id"], prepare_fts_text(r["summary"])) for r in session_rows],
    )

    await db.execute(f"PRAGMA user_version = {FTS_MIGRATION_VERSION}")


async def run_migrations(db: aiosqlite.Connection) -> None:
    await db.executescript(SCHEMA)
    await backfill_fts(db)
    await db.commit()
