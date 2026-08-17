"""Tests for opt-in release update detection and uv upgrades."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from mnemon import update


def test_latest_stable_ignores_prereleases() -> None:
    """The latest stable release excludes prerelease metadata."""
    releases = {"1.0.0": [], "1.1.0rc1": [], "1.0.1": [], "2.0.0.dev1": []}

    assert update._latest_stable(releases) == "1.0.1"


def test_check_for_update_uses_fresh_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A fresh cache avoids a network request."""
    cache = tmp_path / "update.json"
    now = datetime(2026, 8, 17, tzinfo=UTC)
    cached = update.UpdateStatus("1.0.0", "1.1.0", True, now.isoformat())
    cache.write_text(update.json.dumps(update.asdict(cached)), encoding="utf-8")
    monkeypatch.setenv(update.UPDATE_CACHE_PATH_ENV, str(cache))
    monkeypatch.setattr(update, "installed_version", lambda: "1.0.0")
    monkeypatch.setattr(update, "fetch_latest_version", lambda timeout: pytest.fail("network call"))

    assert update.check_for_update(now=now) == cached


def test_check_for_update_reports_offline_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Network failures return a non-fatal error status."""
    monkeypatch.setenv(update.UPDATE_CACHE_PATH_ENV, str(tmp_path / "update.json"))
    monkeypatch.setattr(update, "installed_version", lambda: "1.0.0")
    monkeypatch.setattr(
        update,
        "fetch_latest_version",
        lambda timeout: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    status = update.check_for_update(now=datetime(2026, 8, 17, tzinfo=UTC), force=True)

    assert status.error == "offline"
    assert status.update_available is False


def test_check_for_update_honors_opt_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """The opt-out environment variable prevents checking."""
    monkeypatch.setenv(update.UPDATE_CHECK_DISABLED_ENV, "1")
    monkeypatch.setattr(update, "installed_version", lambda: "1.0.0")

    status = update.check_for_update()

    assert status.skipped is True
    assert status.latest_version is None


def test_apply_uv_upgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit upgrades invoke uv without shell evaluation."""
    completed = SimpleNamespace(stdout="upgraded\n")
    monkeypatch.setattr(update.shutil, "which", lambda executable: "/usr/bin/uv")
    monkeypatch.setattr(update.subprocess, "run", lambda *args, **kwargs: completed)

    assert update.apply_uv_upgrade() is completed


def test_update_command_reports_available_release(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI reports an available update without applying it."""
    from click.testing import CliRunner

    from mnemon.cli import cli

    status = update.UpdateStatus("1.0.0", "1.1.0", True, "2026-08-17T00:00:00+00:00")
    monkeypatch.setattr(update, "check_for_update", lambda: status)

    result = CliRunner().invoke(cli, ["update"])

    assert result.exit_code == 0
    assert "Update available: 1.0.0 → 1.1.0" in result.output
    assert "--apply" in result.output


def test_update_command_apply_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI only invokes uv when --apply is supplied."""
    from click.testing import CliRunner

    from mnemon.cli import cli

    status = update.UpdateStatus("1.0.0", "1.1.0", True, "2026-08-17T00:00:00+00:00")
    applied = False

    def apply() -> SimpleNamespace:
        nonlocal applied
        applied = True
        return SimpleNamespace(stdout="updated")

    monkeypatch.setattr(update, "check_for_update", lambda: status)
    monkeypatch.setattr(update, "apply_uv_upgrade", apply)

    result = CliRunner().invoke(cli, ["update", "--apply"])

    assert result.exit_code == 0
    assert applied is True
    assert result.output == "updated\n"
