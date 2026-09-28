"""
Tests for the hybrid search layer.

Covers FTS query building, camelCase text preparation, reciprocal rank
fusion, FTS sync on write paths, the idempotent backfill migration, and the
relevance behaviour of hybrid cross-category search.
"""

import aiosqlite

from mnemon.core.graph import (
    add_observation,
    delete_entity,
    delete_observation,
    upsert_entity,
)
from mnemon.core.memory import add_decision, add_session_log, add_task, update_task
from mnemon.core.search import (
    _merge,
    _rrf_scores,
    build_fts_query,
    prepare_fts_text,
    search_entities,
    search_memory,
)

# ── prepare_fts_text ──────────────────────────────────────────────────────────


class TestPrepareFtsText:
    def test_splits_camel_case(self):
        assert prepare_fts_text("WasteVolumeController") == "Waste Volume Controller"

    def test_splits_acronym_boundary(self):
        assert prepare_fts_text("HTTPServer") == "HTTP Server"

    def test_keeps_snake_case(self):
        assert prepare_fts_text("my_func_name") == "my_func_name"

    def test_keeps_single_word(self):
        assert prepare_fts_text("hello") == "hello"

    def test_empty_string(self):
        assert prepare_fts_text("") == ""

    def test_none(self):
        assert prepare_fts_text(None) == ""

    def test_digit_boundary(self):
        assert prepare_fts_text("Base64Encoder") == "Base64 Encoder"

    def test_spaced_text_unchanged(self):
        assert prepare_fts_text("already spaced") == "already spaced"


# ── build_fts_query ───────────────────────────────────────────────────────────


class TestBuildFtsQuery:
    def test_single_token(self):
        assert build_fts_query("auth") == "auth*"

    def test_multiple_tokens(self):
        assert build_fts_query("auth token") == "auth* OR token*"

    def test_camel_case_query_split(self):
        assert build_fts_query("AuthService") == "auth* OR service*"

    def test_special_characters_dropped(self):
        assert build_fts_query("don't break;") == "don* OR break*"

    def test_symbols_only_returns_none(self):
        assert build_fts_query("!!! ???") is None

    def test_empty_returns_none(self):
        assert build_fts_query("") is None

    def test_deduplicates_case_insensitive(self):
        assert build_fts_query("auth Auth") == "auth*"

    def test_acronym_query_split(self):
        assert build_fts_query("HTTPServer") == "http* OR server*"


# ── RRF helpers ───────────────────────────────────────────────────────────────


class TestRrf:
    def test_ranks_are_one_based(self):
        assert _rrf_scores(["a", "b", "c"]) == {
            "a": 1.0 / 61,
            "b": 1.0 / 62,
            "c": 1.0 / 63,
        }

    def test_empty_signal(self):
        assert _rrf_scores([]) == {}

    def test_merge_sums_contributions(self):
        merged = _merge({"a": 0.5}, {"a": 0.3, "b": 0.2})
        assert merged == {"a": 0.8, "b": 0.2}

    def test_merge_no_signals(self):
        assert _merge() == {}


# ── FTS sync on write paths ───────────────────────────────────────────────────


async def _fts_rows(
    db: aiosqlite.Connection, table: str, where: str = "", params: tuple = ()
) -> list[dict]:
    async with db.execute(f"SELECT * FROM {table} WHERE 1=1 {where}", params) as cursor:
        return [dict(row) for row in await cursor.fetchall()]


class TestFtsSync:
    async def test_add_decision_syncs_fts(self, db, project_id):
        decision_id = await add_decision(
            db, project_id, "Use pessimistic locking", "Prevents lost updates"
        )
        rows = await _fts_rows(db, "decisions_fts", "AND ref = ?", (decision_id,))
        assert len(rows) == 1
        assert rows[0]["title"] == "Use pessimistic locking"
        assert rows[0]["rationale"] == "Prevents lost updates"

    async def test_add_task_syncs_fts(self, db, project_id):
        task_id = await add_task(db, project_id, "Wire up search", notes="FTS5 mirror tables")
        rows = await _fts_rows(db, "tasks_fts", "AND ref = ?", (task_id,))
        assert len(rows) == 1
        assert rows[0]["title"] == "Wire up search"
        assert rows[0]["notes"] == "FTS5 mirror tables"

    async def test_add_session_log_syncs_fts(self, db, project_id):
        await add_session_log(db, project_id, "Implemented the search upgrade")
        rows = await _fts_rows(db, "sessions_fts", "AND summary LIKE ?", ("%search upgrade%",))
        assert len(rows) == 1
        assert rows[0]["summary"] == "Implemented the search upgrade"

    async def test_upsert_entity_syncs_name_row(self, db, project_id):
        entity_id = await upsert_entity(db, project_id, "AuthService", "component")
        rows = await _fts_rows(db, "entities_fts", "AND ref = ?", (entity_id,))
        assert len(rows) == 1
        assert rows[0]["ref"] == entity_id
        assert rows[0]["obs_ref"] is None
        assert rows[0]["content"] == "Auth Service"

    async def test_add_observation_syncs_obs_row(self, db, project_id):
        entity_id = await upsert_entity(db, project_id, "AuthService", "component")
        obs_id = await add_observation(db, entity_id, "handles authentication requests")
        rows = await _fts_rows(db, "entities_fts", "AND ref = ?", (entity_id,))
        assert len(rows) == 2
        obs_rows = [row for row in rows if row["obs_ref"] == obs_id]
        assert len(obs_rows) == 1
        assert obs_rows[0]["content"] == "handles authentication requests"

    async def test_update_task_resyncs_fts(self, db, project_id):
        task_id = await add_task(db, project_id, "Wire up search", notes="original notes")
        await update_task(db, task_id, "done", notes="replaced notes")
        rows = await _fts_rows(db, "tasks_fts", "AND ref = ?", (task_id,))
        assert len(rows) == 1
        assert rows[0]["notes"] == "replaced notes"

    async def test_delete_entity_removes_all_rows(self, db, project_id):
        entity_id = await upsert_entity(db, project_id, "AuthService", "component")
        await add_observation(db, entity_id, "handles authentication requests")
        assert await delete_entity(db, project_id, "AuthService")
        rows = await _fts_rows(db, "entities_fts", "AND ref = ?", (entity_id,))
        assert rows == []

    async def test_delete_observation_removes_only_obs_row(self, db, project_id):
        entity_id = await upsert_entity(db, project_id, "AuthService", "component")
        obs_id = await add_observation(db, entity_id, "handles authentication requests")
        assert await delete_observation(db, obs_id)
        rows = await _fts_rows(db, "entities_fts", "AND ref = ?", (entity_id,))
        assert len(rows) == 1
        assert rows[0]["obs_ref"] is None
        assert rows[0]["content"] == "Auth Service"


# ── Backfill migration ────────────────────────────────────────────────────────


class TestBackfill:
    async def test_backfill_populates_existing_data(self, temp_db_path, project_id):
        # Seed raw rows before the FTS migration runs.
        db = await aiosqlite.connect(str(temp_db_path))
        db.row_factory = aiosqlite.Row
        await db.executescript(__import__("mnemon.db.migrations", fromlist=["SCHEMA"]).SCHEMA)
        await db.execute("INSERT INTO projects (id) VALUES (?)", (project_id,))
        await db.execute(
            "INSERT INTO entities (project_id, name, entity_type) VALUES (?, ?, 'component')",
            (project_id, "AuthService"),
        )
        await db.commit()
        await db.close()

        from mnemon.db.connection import get_db
        from mnemon.db.migrations import FTS_MIGRATION_VERSION, run_migrations

        async with get_db(path=temp_db_path) as conn:
            await run_migrations(conn)
            async with conn.execute("PRAGMA user_version") as cursor:
                row = await cursor.fetchone()
            version = row[0] if row is not None else -1
            assert version == FTS_MIGRATION_VERSION
            rows = await _fts_rows(conn, "entities_fts")
            assert len(rows) == 1
            # camelCase boundary is split for prefix queries.
            assert rows[0]["content"] == "Auth Service"

    async def test_backfill_is_idempotent(self, temp_db_path, project_id):
        import sqlite3

        from mnemon.core.constants import FTS_MIGRATION_VERSION
        from mnemon.db.connection import get_db
        from mnemon.db.migrations import SCHEMA, run_migrations

        # Seed raw rows before the first migration so the backfill has data.
        raw = sqlite3.connect(str(temp_db_path))
        raw.executescript(SCHEMA)
        raw.execute("INSERT INTO projects (id) VALUES (?)", (project_id,))
        raw.execute(
            "INSERT INTO decisions (project_id, title, rationale) VALUES (?, ?, ?)",
            (project_id, "Use pessimistic locking", "Prevents lost updates"),
        )
        raw.commit()
        raw.close()

        async with get_db(path=temp_db_path) as conn:
            await run_migrations(conn)
            async with conn.execute("PRAGMA user_version") as cursor:
                row = await cursor.fetchone()
            assert (row[0] if row is not None else -1) == FTS_MIGRATION_VERSION
            first = await _fts_rows(conn, "decisions_fts")
            assert len(first) == 1

        async with get_db(path=temp_db_path) as conn:
            await run_migrations(conn)
            second = await _fts_rows(conn, "decisions_fts")
            assert second == first


# ── Hybrid cross-category search ──────────────────────────────────────────────


class TestHybridSearch:
    async def test_relevance_oracle_finds_where_like_misses(self, db, project_id):
        entity_id = await upsert_entity(db, project_id, "WasteVolumeController", "component")
        await add_observation(db, entity_id, "handles waste volume limits")

        # A raw legacy-style substring query for the full phrase misses.
        async with db.execute(
            """
            SELECT DISTINCT e.* FROM entities e
            LEFT JOIN observations o ON o.entity_id = e.id
            WHERE (e.name LIKE '%volume controller%' OR o.content LIKE '%volume controller%')
            """
        ) as cursor:
            like_hits = await cursor.fetchall()
        assert like_hits == []

        results = await search_memory(db, project_id, "volume controller")
        names = [entity["name"] for entity in results["entities"]]
        assert "WasteVolumeController" in names

    async def test_multi_term_different_order(self, db, project_id):
        await add_decision(
            db, project_id, "Use pessimistic locking for writes", "Avoid lost updates"
        )

        async with db.execute(
            "SELECT id FROM decisions WHERE rationale LIKE '%locking pessimistic%'"
        ) as cursor:
            like_hits = await cursor.fetchall()
        assert like_hits == []

        results = await search_memory(db, project_id, "locking pessimistic")
        titles = [decision["title"] for decision in results["decisions"]]
        assert "Use pessimistic locking for writes" in titles

    async def test_result_shape_keys(self, db, project_id):
        results = await search_memory(db, project_id, "anything")
        assert set(results.keys()) == {"entities", "decisions", "sessions", "tasks"}
        for category in results.values():
            assert isinstance(category, list)

    async def test_empty_query_results(self, db, project_id):
        results = await search_memory(db, project_id, "zzznonexistentzzz")
        assert results == {"entities": [], "decisions": [], "sessions": [], "tasks": []}

    async def test_max_chars_trims_to_budget(self, db, project_id):
        for index in range(3):
            await add_decision(db, project_id, f"Decision {index}", "x" * 200)
        results = await search_memory(db, project_id, "decision", max_chars=100)
        total = sum(len(d["title"]) + len(d["rationale"]) for d in results["decisions"])
        assert total <= 100
        assert len(results["decisions"]) < 3

    async def test_max_chars_none_keeps_all(self, db, project_id):
        for index in range(3):
            await add_decision(db, project_id, f"Decision {index}", "x" * 200)
        results = await search_memory(db, project_id, "decision")
        assert len(results["decisions"]) == 3

    async def test_graph_proximity_ranks_related_entities(self, db, project_id):
        api_id = await upsert_entity(db, project_id, "AuthApi", "component")
        db_id = await upsert_entity(db, project_id, "AuthDb", "component")
        await add_observation(db, api_id, "handles auth requests")
        await db.execute(
            "INSERT INTO relations (project_id, from_id, to_id, relation) VALUES (?, ?, ?, 'uses')",
            (project_id, api_id, db_id),
        )
        await db.commit()

        results = await search_memory(db, project_id, "auth")
        names = [entity["name"] for entity in results["entities"]]
        # Both endpoints of the relation match, so both surface via proximity.
        assert "AuthApi" in names
        assert "AuthDb" in names
        # The endpoint with more matching evidence ranks first.
        assert names.index("AuthApi") < names.index("AuthDb")

    async def test_recency_breaks_ties(self, db, project_id):
        first_id = await add_decision(db, project_id, "Recent locking decision", "newer")
        second_id = await add_decision(db, project_id, "Older locking decision", "older")
        await db.execute(
            "UPDATE decisions SET created_at = '2020-01-01T00:00:00' WHERE id = ?",
            (second_id,),
        )
        await db.commit()
        results = await search_memory(db, project_id, "locking decision")
        titles = [decision["title"] for decision in results["decisions"]]
        assert titles.index("Recent locking decision") < titles.index("Older locking decision")
        assert first_id and second_id  # both exist; ids keep the linter honest


# ── Entity search (BM25-backed) ───────────────────────────────────────────────


class TestSearchEntities:
    async def test_camel_case_query_finds_entity(self, db, project_id):
        entity_id = await upsert_entity(db, project_id, "WasteVolumeController", "component")
        await add_observation(db, entity_id, "handles waste volume limits")
        results = await search_entities(db, project_id, "volume controller")
        names = [entity["name"] for entity in results]
        assert "WasteVolumeController" in names

    async def test_importance_breaks_ties(self, db, project_id):
        await upsert_entity(db, project_id, "GammaService", "component", importance=0.5)
        await upsert_entity(db, project_id, "DeltaService", "component", importance=0.9)
        results = await search_entities(db, project_id, "service")
        names = [entity["name"] for entity in results]
        assert names.index("DeltaService") < names.index("GammaService")

    async def test_type_filter(self, db, project_id):
        await upsert_entity(db, project_id, "AuthService", "component")
        await upsert_entity(db, project_id, "AuthConcept", "concept")
        results = await search_entities(db, project_id, "auth", entity_type="component")
        names = [entity["name"] for entity in results]
        assert "AuthService" in names
        assert "AuthConcept" not in names

    async def test_limit_caps_results(self, db, project_id):
        for index in range(10):
            await upsert_entity(db, project_id, f"Component{index}", "component")
        results = await search_entities(db, project_id, "component", limit=5)
        assert len(results) == 5

    async def test_empty_result(self, db, project_id):
        results = await search_entities(db, project_id, "zzznonexistentzzz")
        assert results == []

    async def test_observation_content_match(self, db, project_id):
        entity_id = await upsert_entity(db, project_id, "AuthService", "component")
        await add_observation(db, entity_id, "handles authentication requests")
        results = await search_entities(db, project_id, "authentication")
        names = [entity["name"] for entity in results]
        assert "AuthService" in names
