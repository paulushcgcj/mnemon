import pytest
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path
import asyncio
from pydantic import BaseModel

from mnemon.core.git import get_project_id, get_branch, get_commit_context
from mnemon.core.projects import (
    upsert_project,
    list_projects,
    set_project_parent,
    get_project_children,
    get_project_tree,
)
from mnemon.commands._utils import (
    run_async,
    load_file,
    load_files,
    write_output,
    format_output,
    CLIError,
    validate_format,
    handle_cli_error,
    get_project_id_from_cwd,
    get_branch_from_cwd,
)

# ── core/git.py coverage ──────────────────────────────────────────────────────


def test_get_project_id_success():
    with patch("mnemon.core.git.subprocess.check_output") as mock_git:
        mock_git.return_value = b"https://github.com/owner/repo.git"
        assert get_project_id() == "owner/repo"


def test_get_project_id_failure():
    with patch("mnemon.core.git.subprocess.check_output") as mock_git:
        mock_git.side_effect = subprocess.CalledProcessError(1, "git")
        with pytest.raises(RuntimeError, match="Not a git repo"):
            get_project_id()


def test_get_project_id_no_match():
    with patch("mnemon.core.git.subprocess.check_output") as mock_git:
        mock_git.return_value = b"invalid-url"
        with pytest.raises(ValueError, match="Cannot parse owner/repo"):
            get_project_id()


def test_get_branch():
    with patch("mnemon.core.git.subprocess.check_output") as mock_git:
        mock_git.return_value = b"main\n"
        assert get_branch() == "main"


def test_get_commit_context_first_commit():
    with patch("mnemon.core.git._git") as mock_git:

        def side_effect(cmd, *args, **kwargs):
            if cmd == "rev-parse" and "HEAD" in args:
                return "abc123456789"
            if cmd == "log":
                if "--pretty=%B" in args:
                    return "Initial commit"
                if "--pretty=%an" in args:
                    return "Test Author"
            if cmd == "diff":
                raise subprocess.CalledProcessError(1, "git")
            return ""

        mock_git.side_effect = side_effect
        ctx = get_commit_context()
        assert ctx["sha"] == "abc123456789"
        assert ctx["is_first_commit"] is True


# ── core/projects.py coverage ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_project_circular_reference(db):
    await upsert_project(db, "CIRC_A")
    await upsert_project(db, "CIRC_B", parent_id="CIRC_A")

    with pytest.raises(ValueError, match="Circular reference detected"):
        await upsert_project(db, "CIRC_A", parent_id="CIRC_B")


@pytest.mark.asyncio
async def test_upsert_project_self_parent(db):
    with pytest.raises(ValueError, match="cannot be its own parent"):
        await upsert_project(db, "SELF_P", parent_id="SELF_P")


@pytest.mark.asyncio
async def test_list_projects_recursive(db):
    await upsert_project(db, "ROOT_REC")
    await upsert_project(db, "CHILD_REC", parent_id="ROOT_REC")
    await upsert_project(db, "GRAND_REC", parent_id="CHILD_REC")

    results = await list_projects(db, parent_id="ROOT_REC", include_children=True)
    assert len(results) == 3
    ids = {r["id"] for r in results}
    assert "ROOT_REC" in ids
    assert "CHILD_REC" in ids
    assert "GRAND_REC" in ids


@pytest.mark.asyncio
async def test_set_project_parent_circular(db):
    await upsert_project(db, "SET_A")
    await upsert_project(db, "SET_B", parent_id="SET_A")

    with pytest.raises(ValueError, match="Circular reference detected"):
        await set_project_parent(db, "SET_A", "SET_B")


@pytest.mark.asyncio
async def test_get_project_tree_all(db):
    tree = await get_project_tree(db)
    assert isinstance(tree, list)


# ── commands/_utils.py coverage ───────────────────────────────────────────────


def test_run_async_new_loop():
    async def hello():
        return "world"

    assert run_async(hello()) == "world"


def test_load_file_success(tmp_path):
    p = tmp_path / "test.txt"
    p.write_text("hello", encoding="utf-8")
    assert load_file(p) == "hello"
    assert load_files([p]) == ["hello"]


def test_load_file_failure(tmp_path):
    p = tmp_path / "readonly.txt"
    p.write_text("hello")
    p.chmod(0o000)
    try:
        with pytest.raises(CLIError, match="Failed to read"):
            load_file(p)
    finally:
        p.chmod(0o644)


def test_write_output_model(tmp_path):
    class MockModel(BaseModel):
        name: str

    m = MockModel(name="test")
    p = tmp_path / "out.json"
    write_output(m, p, format="json")
    assert '"name":"test"' in p.read_text().replace(" ", "")

    p2 = tmp_path / "out.txt"
    write_output(m, p2, format="text")
    assert "'name': 'test'" in p2.read_text()


def test_format_output_model_validation():
    class MockModel(BaseModel):
        val: int

    assert '"val":1' in format_output({"val": 1}, format="json", model_class=MockModel).replace(
        " ", ""
    )

    with pytest.raises(CLIError, match="Failed to validate"):
        format_output({"val": "bad"}, format="json", model_class=MockModel)


def test_handle_cli_error_unexpected():
    with pytest.raises(SystemExit):
        handle_cli_error(ValueError("Unexpected"))


def test_get_project_and_branch_from_cwd():
    with patch("mnemon.core.git.get_project_id", return_value="proj"):
        assert get_project_id_from_cwd() == "proj"
    with patch("mnemon.core.git.get_branch", return_value="br"):
        assert get_branch_from_cwd() == "br"

    with patch("mnemon.core.git.get_project_id", side_effect=Exception("fail")):
        with pytest.raises(CLIError):
            get_project_id_from_cwd()
    with patch("mnemon.core.git.get_branch", side_effect=Exception("fail")):
        with pytest.raises(CLIError):
            get_branch_from_cwd()


@pytest.mark.asyncio
async def test_get_project_children_recursive(db):
    await upsert_project(db, "p_rec")
    await upsert_project(db, "c_rec", parent_id="p_rec")
    await upsert_project(db, "g_rec", parent_id="c_rec")

    children = await get_project_children(db, "p_rec", recursive=True)
    assert len(children) == 2
    assert {c["id"] for c in children} == {"c_rec", "g_rec"}
