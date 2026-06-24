import re
import subprocess


def _git(*args, cwd: str | None = None) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=cwd, stderr=subprocess.DEVNULL
    ).decode().strip()


def get_project_id(cwd: str | None = None) -> str:
    """
    Extract 'owner/repo' from git remote URL.
    Handles SSH:   git@github.com:bcgov/nr-waste-plus.git
    Handles HTTPS: https://github.com/bcgov/nr-waste-plus.git
    """
    try:
        url = _git("remote", "get-url", "origin", cwd=cwd)
    except subprocess.CalledProcessError:
        raise RuntimeError("Not a git repo or no remote 'origin'.") from None
    match = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    if not match:
        raise ValueError(f"Cannot parse owner/repo from: {url}")
    return match.group(1)


def get_branch(cwd: str | None = None) -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)


def get_commit_context(cwd: str | None = None) -> dict:
    """
    Get context about the current commit.

    Returns a dict with:
    - sha: Full commit hash
    - short_sha: First 8 characters of hash
    - message: Commit message
    - author: Author name
    - files: List of changed files (empty for first commit)
    - stat: Diff stat (empty for first commit)

    Handles first commit (no parent) gracefully.
    """
    sha     = _git("rev-parse", "HEAD", cwd=cwd)
    message = _git("log", "-1", "--pretty=%B", cwd=cwd).strip()
    author  = _git("log", "-1", "--pretty=%an", cwd=cwd)

    # Try to get diff from parent, but handle first commit
    try:
        files   = _git("diff", "HEAD~1", "HEAD", "--name-only", cwd=cwd).splitlines()
        stat    = _git("diff", "HEAD~1", "HEAD", "--stat", cwd=cwd)
    except subprocess.CalledProcessError:
        # This is the first commit, no parent
        files   = []
        stat    = ""

    return {
        "sha":       sha,
        "short_sha": sha[:8],
        "message":   message,
        "author":    author,
        "files":     [f for f in files if f],
        "stat":      stat,
        "is_first_commit": len(files) == 0 and len(stat) == 0,
    }
