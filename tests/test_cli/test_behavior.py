"""Behavior tests for CLI commands."""

import json
from pathlib import Path

from click.testing import CliRunner

from mnemon import cli as cli_module
from mnemon.cli import cli
from mnemon.core.graph import add_observation, add_relation, upsert_entity
from mnemon.core.projects import upsert_project
from mnemon.db.connection import get_db
from mnemon.db.migrations import run_migrations


def invoke(args: list[str]):
    return CliRunner().invoke(cli, args)


async def seed_project_graph(db_path: Path, project_id: str = "owner/repo") -> None:
    async with get_db(path=db_path) as db:
        await run_migrations(db)
        await upsert_project(db, project_id)
        component = await upsert_entity(
            db, project_id, "Api", "component", importance=0.8, branch="main"
        )
        database = await upsert_entity(db, project_id, "Db", "system", importance=0.4)
        low = await upsert_entity(db, project_id, "OldLow", "component", importance=0.1)
        await add_observation(db, component, "Handles requests")
        await add_relation(db, project_id, component, database, "uses")
        await db.execute(
            "UPDATE entities SET updated_at = datetime('now', '-45 days') WHERE id = ?",
            (low,),
        )
        await db.commit()


async def seed_project_tree(db_path: Path) -> None:
    async with get_db(path=db_path) as db:
        await run_migrations(db)
        await upsert_project(db, "root/app")
        await upsert_project(db, "root/api", parent_id="root/app")
        await upsert_project(db, "root/worker", parent_id="root/app")


class TestInitInstall:
    def test_init_writes_instructions_and_json_existing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cli_module, "get_project_id", lambda cwd: "owner/repo")

        result = invoke(["init", "--cwd", str(tmp_path)])
        assert result.exit_code == 0
        target = tmp_path / ".github" / "copilot-instructions.md"
        assert target.exists()
        assert "owner/repo" in target.read_text()

        existing = invoke(["init", "--cwd", str(tmp_path), "--format", "json"])
        assert existing.exit_code == 0
        payload = json.loads(existing.output)
        assert payload["fileCreated"] is False
        assert "already exists" in payload["error"]

    def test_init_force_out_and_git_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cli_module, "get_project_id", lambda cwd: "owner/repo")
        out = tmp_path / "init.json"

        result = invoke(["init", "--cwd", str(tmp_path), "--force", "--format", "json", "--out", str(out)])
        assert result.exit_code == 0
        assert json.loads(out.read_text())["projectId"] == "owner/repo"

        monkeypatch.setattr(cli_module, "get_project_id", lambda cwd: (_ for _ in ()).throw(RuntimeError("no git")))
        failed = invoke(["init", "--cwd", str(tmp_path / "missing")])
        assert failed.exit_code == 1
        assert "Could not detect project" in failed.output

    def test_install_writes_skill_existing_json_and_force_out(self, tmp_path):
        result = invoke(["install", "--cwd", str(tmp_path)])
        assert result.exit_code == 0
        target = tmp_path / ".github" / "skills" / "mnemon" / "SKILL.md"
        assert target.exists()

        existing = invoke(["install", "--cwd", str(tmp_path), "--format", "json"])
        assert existing.exit_code == 0
        assert json.loads(existing.output)["skillInstalled"] is False

        out = tmp_path / "install.json"
        forced = invoke(["install", "--cwd", str(tmp_path), "--force", "--format", "json", "--out", str(out)])
        assert forced.exit_code == 0
        assert json.loads(out.read_text())["skillInstalled"] is True

    def test_invalid_format_reports_error(self, tmp_path):
        result = invoke(["install", "--cwd", str(tmp_path), "--format", "yaml"])
        assert result.exit_code == 1
        assert "Invalid format" in result.output


class TestReadGraphPruneProjects:
    def test_read_text_json_and_out(self, tmp_path):
        db_path = tmp_path / "mnemon.db"
        result = invoke([
            "read",
            "--project",
            "owner/repo",
            "--branch",
            "main",
            "--db-path",
            str(db_path),
        ])
        assert result.exit_code == 0
        assert "owner/repo" in result.output

        out = tmp_path / "context.json"
        as_json = invoke([
            "read",
            "--project",
            "owner/repo",
            "--branch",
            "main",
            "--db-path",
            str(db_path),
            "--format",
            "json",
            "--out",
            str(out),
        ])
        assert as_json.exit_code == 0
        assert "context" in json.loads(out.read_text())

    async def test_graph_text_json_empty_and_prune(self, tmp_path):
        db_path = tmp_path / "mnemon.db"
        empty = invoke(["graph", "--project", "owner/repo", "--db-path", str(db_path)])
        assert empty.exit_code == 0
        assert "No entities" in empty.output

        await seed_project_graph(db_path)

        graph_text = invoke(["graph", "--project", "owner/repo", "--db-path", str(db_path), "--min", "0.5"])
        assert graph_text.exit_code == 0
        assert "Api" in graph_text.output
        assert "Handles requests" in graph_text.output
        assert "uses: Db" in graph_text.output

        graph_json = invoke([
            "graph",
            "--project",
            "owner/repo",
            "--db-path",
            str(db_path),
            "--type",
            "component",
            "--format",
            "json",
        ])
        assert graph_json.exit_code == 0
        assert json.loads(graph_json.output)["filteredBy"]["entityType"] == "component"

        dry_run = invoke([
            "prune",
            "--project",
            "owner/repo",
            "--db-path",
            str(db_path),
            "--dry-run",
            "--below",
            "0.2",
        ])
        assert dry_run.exit_code == 0
        assert "OldLow" in dry_run.output

        pruned = invoke([
            "prune",
            "--project",
            "owner/repo",
            "--db-path",
            str(db_path),
            "--below",
            "0.2",
            "--days",
            "30",
            "--format",
            "json",
        ])
        assert pruned.exit_code == 0
        assert json.loads(pruned.output)["prunedCount"] == 1

    async def test_projects_and_tree_commands(self, tmp_path):
        db_path = tmp_path / "mnemon.db"
        empty = invoke(["projects", "--db-path", str(db_path)])
        assert empty.exit_code == 0
        assert "No projects" in empty.output

        await seed_project_tree(db_path)

        listed = invoke(["projects", "--db-path", str(db_path), "--format", "json"])
        assert listed.exit_code == 0
        assert json.loads(listed.output)["total"] == 3

        children = invoke(["project-children", "--project", "root/app", "--db-path", str(db_path)])
        assert children.exit_code == 0
        assert "root/api" in children.output

        tree = invoke(["project-tree", "--db-path", str(db_path)])
        assert tree.exit_code == 0
        assert "- root/app" in tree.output
        assert "  - root/api" in tree.output

        removed = invoke([
            "project-set-parent",
            "--project",
            "root/api",
            "--db-path",
            str(db_path),
        ])
        assert removed.exit_code == 0
        assert "removed" in removed.output

        missing = invoke(["project-set-parent", "--project", "missing/project", "--db-path", str(db_path)])
        assert missing.exit_code == 1
        assert "not found" in missing.output


class TestLogCommit:
    def test_log_commit_success_empty_and_git_failure(self, tmp_path, monkeypatch):
        db_path = tmp_path / "mnemon.db"
        monkeypatch.setattr(cli_module, "get_project_id", lambda cwd: "owner/repo")
        monkeypatch.setattr(cli_module, "get_branch", lambda cwd: "main")
        monkeypatch.setattr(
            cli_module,
            "get_commit_context",
            lambda cwd: {
                "sha": "abcdef123456",
                "short_sha": "abcdef12",
                "message": "Add feature\n\nbody",
                "author": "Ada",
                "files": ["a.py", "b.py"],
            },
        )

        result = invoke(["log-commit", "--db-path", str(db_path), "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["commitSha"] == "abcdef12"
        assert payload["filesCount"] == 2

        monkeypatch.setattr(
            cli_module,
            "get_commit_context",
            lambda cwd: {"sha": "abcdef", "short_sha": "abcdef", "message": " ", "author": "", "files": []},
        )
        empty = invoke(["log-commit", "--db-path", str(db_path)])
        assert empty.exit_code == 0
        assert "empty commit message" in empty.output

        monkeypatch.setattr(cli_module, "get_project_id", lambda cwd: (_ for _ in ()).throw(RuntimeError("no git")))
        skipped = invoke(["log-commit", "--db-path", str(db_path), "--format", "json"])
        assert skipped.exit_code == 0
        assert "Skipped" in json.loads(skipped.output)["error"]

