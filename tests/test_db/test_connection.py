"""Tests for database connection management."""

import tempfile
from pathlib import Path

import pytest

from mnemon.db.connection import DEFAULT_DB_PATH, get_db, get_db_path


class TestGetDbPath:
    """Tests for get_db_path function."""

    def test_default_path(self, monkeypatch):
        """Test that default path is returned when no env var is set."""
        monkeypatch.delenv("MNEMON_DB_PATH", raising=False)
        path = get_db_path()
        assert path == DEFAULT_DB_PATH

    def test_custom_path_from_env(self, monkeypatch):
        """Test that custom path is returned from environment variable."""
        custom_path = "/custom/path/mnemon.db"
        monkeypatch.setenv("MNEMON_DB_PATH", custom_path)
        path = get_db_path()
        assert path == Path(custom_path)

    def test_memory_path(self, monkeypatch):
        """Test that :memory: is handled correctly."""
        monkeypatch.setenv("MNEMON_DB_PATH", ":memory:")
        path = get_db_path()
        assert str(path) == ":memory:"

    def test_memory_path_case_insensitive(self, monkeypatch):
        """Test that 'memory' (lowercase) is handled correctly."""
        monkeypatch.setenv("MNEMON_DB_PATH", "memory")
        path = get_db_path()
        assert str(path) == ":memory:"


@pytest.mark.asyncio
class TestGetDb:
    """Tests for get_db context manager."""

    async def test_creates_parent_directories(self, temp_db_path):
        """Test that parent directories are created if they don't exist."""
        # Get a unique temp directory that we can create
        unique_temp = tempfile.mkdtemp()
        test_path = Path(unique_temp) / "subdir" / "test.db"

        try:
            async with get_db(path=test_path) as db:
                assert db is not None

            # Check that parent was created
            assert test_path.parent.exists()
        finally:
            # Cleanup
            import shutil
            shutil.rmtree(unique_temp, ignore_errors=True)

    async def test_in_memory_database(self):
        """Test that in-memory database works."""
        async with get_db(path=":memory:") as db:
            async with db.execute("SELECT 1") as cur:
                result = await cur.fetchone()
                assert result[0] == 1

    async def test_wal_mode_enabled(self, temp_db_path):
        """Test that WAL mode is enabled."""
        async with get_db(path=temp_db_path) as db:
            async with db.execute("PRAGMA journal_mode") as cur:
                result = await cur.fetchone()
                assert result[0] == "wal"

    async def test_foreign_keys_enabled(self, temp_db_path):
        """Test that foreign keys are enabled."""
        async with get_db(path=temp_db_path) as db:
            async with db.execute("PRAGMA foreign_keys") as cur:
                result = await cur.fetchone()
                assert result[0] == 1
