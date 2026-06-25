---
name: mnemon
description: Long Term Memory Skill
---

# Mnemon — Long Term Memory Skill

Use this skill whenever the user wants to save, store, or record something for future sessions.

---

## Trigger phrases

- "remember this" / "save this" / "don't forget"
- "add to memory" / "add this to long term memory"
- "store this decision" / "log this task"
- "make a note of" / "this is important"
- "add this to the knowledge graph"

---

## Required setup

Verify the `mnemon` MCP server is connected before proceeding.
Call `memory_read` first — if it fails, tell the user and stop.

---

## Step 1 — Get context

Call `memory_read` with:
- `project_id`: from `.github/copilot-instructions.md`
- `branch`: current git branch

---

## Step 2 — Classify the input

### Session memory (project/branch state)

| What the user wants to store | Action |
|---|---|
| An architectural or design decision | `memory_summarize` with `decisions[]` |
| A task or feature to build | `memory_summarize` with `tasks_new[]` |
| General project context, stack, conventions | `memory_project_set_context` |
| What happened this session | `memory_summarize` with `summary` |
| A task that just got done | `memory_task_update(status: 'done')` |

### Knowledge graph (entities and relationships)

Use the graph when the user is describing a **thing** — a component, a concept,
a person, a system, a file — rather than a task or decision.

| What the user describes | Action |
|---|---|
| A new component/service/class | `graph_entity_upsert(entity_type: 'component')` |
| A concept or pattern in the codebase | `graph_entity_upsert(entity_type: 'concept')` |
| A person and their role | `graph_entity_upsert(entity_type: 'person')` |
| A new fact about an existing entity | `graph_observe` |
| How two things relate | `graph_relate` |

---

## Step 3 — Determine scope

- Feature-specific / this branch only → pass `branch` or `branch_scoped: true`
- Project-wide, architectural → global (omit branch / `is_global: true`)

**Default to global when unsure.**

---

## Step 4 — Store it

### Storing a decision
```
memory_summarize(
  project_id, branch, summary, current_focus, next_steps,
  decisions = [{ title, rationale, branch_scoped: false }]
)
```

### Storing a task
```
memory_summarize(
  ...,
  tasks_new = [{ title, status: 'todo', is_global: false }]
)
```

### Storing an entity (knowledge graph)
```
graph_entity_upsert(
  project_id = ...,
  name       = "WasteVolumeController",
  entity_type = "component",
  observations = [
    "handles CRUD for waste volume configs",
    "uses Spring Data JPA",
    "returns WasteVolumeDTO on all endpoints"
  ],
  importance = 0.8    ← high: core component
)
```

### Adding a fact to an existing entity
```
graph_observe(
  project_id   = ...,
  entity_name  = "WasteVolumeController",
  observation  = "now also handles bulk import via POST /bulk"
)
```

### Connecting two entities
```
graph_relate(
  project_id  = ...,
  from_entity = "WasteVolumeForm",
  relation    = "calls",
  to_entity   = "WasteVolumeController"
)
```

---

## Step 5 — Set importance correctly

| Importance | When to use |
|---|---|
| `0.9` | Core architectural component, central concept |
| `0.7` | Important but not central — major feature component |
| `0.5` | Default — general entity |
| `0.3` | Minor utility, helper, peripheral concept |
| `0.1` | Rarely relevant, mostly for completeness |

Entities with importance ≥ 0.4 appear automatically in `memory_read` context.

---

## Step 6 — Confirm

Tell the user exactly what was stored:

> ✓ **Decision** (global): "Use JSONB polymorphism for volume types"
> ✓ **Entity** `WasteVolumeController` [component, importance: 0.8] — 3 observations added
> ✓ **Relation**: WasteVolumeForm —[calls]→ WasteVolumeController

One line per item. Don't repeat what they said back to them.

---

## Rules

- Never store secrets, tokens, or passwords.
- If the user gives multiple things, store all of them.
- If something fails, say so clearly.
- When in doubt between global and branch-scoped, choose global.
- Batch related stores into one `memory_summarize` call where possible.
