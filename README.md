# Mnemon

[![PyPI version](https://img.shields.io/pypi/v/mnemonn.svg)](https://pypi.org/project/mnemonn/)
[![Python versions](https://img.shields.io/pypi/pyversions/mnemonn.svg)](https://pypi.org/project/mnemonn/)
[![CI](https://github.com/paulushcgcj/mnemon/actions/workflows/ci.yml/badge.svg)](https://github.com/paulushcgcj/mnemon/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/paulushcgcj/mnemon.svg)](LICENSE)

Persistent project memory and a scoped knowledge graph for AI coding agents.

Mnemon helps an AI coding agent remember what matters between sessions: what the project is, what branch is being worked on, what decisions were made, what tasks are still open, and which components or concepts are important in the codebase.

It is intentionally small and local-first. There is no hosted service to configure and no vector database to operate. Mnemon runs as an MCP server, stores memory in SQLite, and gives compatible agents a clean context block at the start of every session.

## Why Mnemon

AI coding sessions often lose the thread. A new session may need the same explanations again: the branch goal, the plan, the constraints, the decision history, the half-finished task, the component that should not be touched casually.

Mnemon is built around continuity rather than chat history search.

- **Session memory** keeps the current project state, per-branch focus, decisions, tasks, and recent session history.
- **Knowledge graph memory** stores entities, observations, and typed relations for components, concepts, files, people, and systems.
- **Git-aware setup** derives the project id from the repository remote, so each repo gets a stable memory namespace.
- **Branch-aware state** lets the same repository have different active plans on different branches.
- **Local storage** keeps memory in `~/.agent-memory/mnemon.db`.
- **MCP tools** let agents read and update memory as part of their normal workflow.

The result is a compact memory layer that helps an agent start a session already oriented instead of asking you to rebuild the map by hand.

## How It Works

Mnemon keeps two complementary layers.

### Session Memory

Session memory answers: "Where are we right now?"

It stores:

- project-wide context, such as stack, conventions, and architecture notes
- branch-specific focus and next steps
- decisions, either global or branch-scoped
- tasks with `todo`, `in-progress`, `blocked`, or `done` status
- recent session summaries
- git commit entries from optional hooks

Agents read this through `memory_read` at the start of a session and update it through `memory_summarize` at the end.

### Knowledge Graph

The graph answers: "What do we know about the important things in this project?"

It stores:

- **entities** such as components, concepts, files, people, systems, or custom types
- **observations** as factual notes attached to entities
- **relations** such as `calls`, `implements`, `depends_on`, `owns`, `uses`, or custom labels
- **importance scores** from `0.0` to `1.0`

Important graph entities are automatically included in the session-start context, so architectural knowledge becomes part of the agent's working memory without a separate search step.

## Installation

**Mac / Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/paulushcgcj/mnemon/main/install.sh | bash
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/paulushcgcj/mnemon/main/install.ps1 | iex
```

**Via pip / uv (all platforms)**

```bash
pip install mnemonn
# or
uv tool install mnemonn
```

> **macOS note:** If you see a security warning on first run, clear the quarantine flag once: `xattr -d com.apple.quarantine /usr/local/bin/mnemon`

### One-off Usage

```bash
# Run a command without permanent installation
uvx mnemonn read --help
```

### From Source (Development)

```bash
# Clone the repository
git clone https://github.com/paulushcgcj/mnemon.git
cd mnemon

# Install in development mode
uv sync
uv tool install -e .
```

During development, you can also run it directly with:

```bash
uv run mnemon --help
```

## Quick Start

Install Mnemon, then set up a repository:

```bash
uv tool install /path/to/mnemon
cd /path/to/your/repo
mnemon init
mnemon install
bash /path/to/mnemon/install-hooks.sh
```

`mnemon init` creates:

```text
.github/copilot-instructions.md
```

The file tells the agent to call Mnemon at session start and session end.

`mnemon install` creates:

```text
.github/skills/mnemon/SKILL.md
```

The skill tells the agent how to handle requests such as "remember this", "save this decision", or "add this to the knowledge graph".

The hook installer links:

```text
.git/hooks/post-commit
.git/hooks/post-merge
```

Those hooks log commits into Mnemon's session history.

## MCP Configuration

Configure your MCP client to run Mnemon over stdio:

```json
{
  "command": "mnemon",
  "args": ["serve"]
}
```

After that, compatible agents can call Mnemon's tools directly.

## CLI

```bash
mnemon serve
```

Start the MCP server over stdio.

```bash
mnemon init
mnemon init --force
```

Generate `.github/copilot-instructions.md` for the current repository. Mnemon detects the project id from `git remote get-url origin`, using the `owner/repo` slug.

```bash
mnemon install
mnemon install --force
```

Install the Mnemon skill into `.github/skills/mnemon/SKILL.md`.

```bash
mnemon read
mnemon read --project owner/repo --branch main
```

Print the full context block that an agent receives at session start.

```bash
mnemon graph
mnemon graph --min 0.6
mnemon graph --type component
```

Inspect the project knowledge graph.

```bash
mnemon prune
mnemon prune --below 0.3 --days 60
mnemon prune --dry-run
```

Remove stale, low-importance entities from the graph.

```bash
mnemon projects
```

List projects known to the local memory store.

```bash
mnemon log-commit
```

Log the latest commit. This is normally called by the installed git hooks.

## MCP Tools

Mnemon exposes two groups of tools.

### Session Tools

- `memory_read(project_id, branch)` returns the full session-start context block.
- `memory_summarize(...)` stores the end-of-session summary, current focus, next steps, decisions, completed tasks, and new tasks.
- `memory_task_update(task_id, status, notes)` updates a task during a session.
- `memory_project_set_context(project_id, context)` sets the global project context.
- `memory_log_commit(...)` logs a commit into session history.
- `memory_project_list(parent_id)` lists known projects.

### Graph Tools

- `graph_entity_upsert(...)` creates or updates an entity and optionally adds observations.
- `graph_observe(project_id, entity_name, observation)` adds a fact to an existing entity.
- `graph_relate(project_id, from_entity, relation, to_entity)` connects two entities.
- `graph_search(project_id, query, entity_type, limit)` searches by entity name or observation content.
- `graph_read(project_id, branch, importance_min)` reads the graph.
- `graph_forget(project_id, entity_name, observation_id)` deletes an entity or a single observation.

## Data Model

Mnemon stores data in:

```text
~/.agent-memory/mnemon.db
```

The SQLite schema has nine tables:

- `projects`
- `project_state`
- `branch_state`
- `decisions`
- `tasks`
- `session_log`
- `entities`
- `observations`
- `relations`

The project id is normally inferred from the git remote URL. For example:

```text
git@github.com:owner/repo.git
https://github.com/owner/repo.git
```

Both resolve to:

```text
owner/repo
```

## Example Flow

At the beginning of a session, the agent calls:

```text
memory_read(project_id="owner/repo", branch="feature/imports")
```

Mnemon returns a context block containing project context, decisions, graph entities, branch focus, tasks, and recent history.

During the session, the agent can update task status:

```text
memory_task_update(task_id="a1b2c3d4", status="in-progress")
```

When the user says "remember that the ImportService owns CSV validation", the agent can store graph knowledge:

```text
graph_entity_upsert(
  project_id="owner/repo",
  name="ImportService",
  entity_type="component",
  observations=["owns CSV validation"],
  importance=0.7
)
```

At the end of the session, the agent calls:

```text
memory_summarize(
  project_id="owner/repo",
  branch="feature/imports",
  summary="Implemented CSV validation path and added error handling.",
  current_focus="Finishing import validation edge cases.",
  next_steps="Add tests for malformed rows and empty files."
)
```

The next session starts with that context already available.

## Design Principles

- **Continuity over retrieval tricks.** Mnemon focuses on the information an agent needs to resume work, not on building a general-purpose RAG stack.
- **Project and branch scope by default.** Memory follows the way software work actually happens.
- **Append important history, overwrite current state.** Session logs and observations accumulate; branch focus stays current.
- **Local and inspectable.** Memory is SQLite, and the CLI can read the context and graph directly.
- **Small surface area.** The system is meant to be easy to install, understand, and remove.

## Development

Run the CLI from the repository:

```bash
uv run mnemon --help
```

Start the MCP server:

```bash
uv run mnemon serve
```

Inspect the current repository memory:

```bash
uv run mnemon read
```

The package entry point is defined in `pyproject.toml`:

```toml
[project.scripts]
mnemon = "mnemon.cli:cli"
```

## Recent Improvements

The following improvements have been completed as part of the ongoing development:

| Date | Change | Workstream | Impact |
|------|--------|-----------|--------|
| 2026-06-23 | Fixed SQL injection vulnerability in search_entities | [01-security-fixes](.temp/plan/01-security-fixes.md) | HIGH - Security |
| 2026-06-23 | Added input validation for entity types, task statuses, importance | [02-input-validation](.temp/plan/02-input-validation.md) | HIGH - Data Quality |
| 2026-06-23 | Extracted magic strings into constants module | [03-constants-refactor](.temp/plan/03-constants-refactor.md) | MEDIUM - Maintainability |
| 2026-06-23 | Made database path configurable via env var and CLI | [04-configurable-db-path](.temp/plan/04-configurable-db-path.md) | MEDIUM - Testability |
| 2026-06-23 | Improved git hooks with better error handling | [05-git-hook-improvements](.temp/plan/05-git-hook-improvements.md) | MEDIUM - Reliability |
| 2026-06-24 | Added CLI quality improvements (contracts, format flags, error handling) | [09-cli-quality-improvements](.temp/plan/09-cli-quality-improvements.md) | HIGH - CLI Infrastructure |

### Architecture Updates

- **New Module:** `mnemon/core/constants.py` - Centralized constants and validation helpers
- **Enhanced:** `mnemon/db/connection.py` - Now supports `MNEMON_DB_PATH` environment variable and explicit path override
- **Improved:** `mnemon/core/git.py` - `get_commit_context()` now handles first commit gracefully
- **Hardened:** All CLI commands now include `--db-path` option for testing
- **New Directories:** `mnemon/contracts/` - Pydantic models for JSON output contracts, `mnemon/commands/` - Shared CLI utilities

## Status

Mnemon is early software. The core loop is intentionally usable now: install it, initialize a repository, connect an MCP client, and let the agent keep project memory as work progresses.

The most valuable next improvements are likely around export/import, richer graph inspection, comprehensive test coverage, and more client-specific setup guides.
