import aiosqlite

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
"""


async def run_migrations(db: aiosqlite.Connection) -> None:
    await db.executescript(SCHEMA)
    await db.commit()
