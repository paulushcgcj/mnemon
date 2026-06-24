import aiosqlite

from .memory import (
    get_branch_state, get_decisions,
    get_project_state, get_recent_sessions, get_tasks,
)
from .graph import get_full_graph

STATUS_ICON = {
    "in-progress": "▶",
    "blocked":     "✗",
    "todo":        "○",
    "done":        "✓",
}

ENTITY_ICON = {
    "component": "⬡",
    "concept":   "◈",
    "person":    "◉",
    "file":      "◻",
    "system":    "◆",
    "custom":    "◇",
}


async def build_context(db: aiosqlite.Connection, project_id: str, branch: str) -> str:
    project_state = await get_project_state(db, project_id)
    branch_st     = await get_branch_state(db, project_id, branch)
    decisions     = await get_decisions(db, project_id, branch)
    tasks         = await get_tasks(db, project_id, branch)
    recent        = await get_recent_sessions(db, project_id, branch, limit=5)
    # Top entities by importance — inject the most relevant ones into context
    entities      = await get_full_graph(db, project_id, branch=branch, importance_min=0.4, limit=15)

    lines: list[str] = [f"## {project_id}  |  branch: {branch}", ""]

    # ── Global context ────────────────────────────────────────────────────────
    if project_state and project_state.get("context"):
        lines += ["### Project (Global)", project_state["context"], ""]

    global_decisions = [d for d in decisions if not d.get("branch")]
    if global_decisions:
        lines.append("### Global Decisions")
        for d in global_decisions:
            date      = d["created_at"][:10]
            rationale = f" — {d['rationale']}" if d.get("rationale") else ""
            lines.append(f"- [{date}] **{d['title']}**{rationale}")
        lines.append("")

    # ── Entity graph ──────────────────────────────────────────────────────────
    if entities:
        lines.append("### Knowledge Graph")
        # Group by entity type
        by_type: dict[str, list] = {}
        for e in entities:
            by_type.setdefault(e["entity_type"], []).append(e)

        for etype, group in sorted(by_type.items()):
            icon = ENTITY_ICON.get(etype, "◇")
            lines.append(f"\n**{etype.capitalize()}s** {icon}")
            for e in group:
                obs_lines = [f"  - {o['content']}" for o in e["observations"]]
                out_rels  = [r for r in e["relations"] if r["direction"] == "out"]
                rel_lines = [f"  → {r['relation']}: **{r['other_name']}**" for r in out_rels]

                lines.append(f"- **{e['name']}**" + (f"  *(importance: {e['importance']:.1f})*" if e['importance'] != 0.5 else ""))
                lines.extend(obs_lines)
                lines.extend(rel_lines)
        lines.append("")

    # ── Branch context ────────────────────────────────────────────────────────
    lines.append(f"### Branch: `{branch}`")

    if branch_st:
        if branch_st.get("current_focus"):
            lines += ["", f"**Focus:** {branch_st['current_focus']}"]
        if branch_st.get("next_steps"):
            lines += ["", "**Next Steps:**", branch_st["next_steps"]]
        lines.append("")
    else:
        lines += ["", "*No session recorded for this branch yet.*", ""]

    branch_decisions = [d for d in decisions if d.get("branch") == branch]
    if branch_decisions:
        lines.append("**Branch Decisions:**")
        for d in branch_decisions:
            date      = d["created_at"][:10]
            rationale = f" — {d['rationale']}" if d.get("rationale") else ""
            lines.append(f"- [{date}] {d['title']}{rationale}")
        lines.append("")

    # ── Tasks ─────────────────────────────────────────────────────────────────
    if tasks:
        lines.append("**Tasks:**")
        for t in tasks:
            icon  = STATUS_ICON.get(t["status"], "?")
            scope = " *(global)*" if not t.get("branch") else ""
            note  = f" — {t['notes']}" if t.get("notes") else ""
            lines.append(f"  [{icon}] `{t['id']}` {t['title']}{scope}{note}")
        lines.append("")

    # ── Recent sessions ───────────────────────────────────────────────────────
    if recent:
        lines.append("**Recent Sessions:**")
        for s in recent:
            date = s["created_at"][:10]
            tag  = f" [{s['source']}]" if s.get("source") != "ai" else ""
            sha  = f" ({s['sha'][:8]})" if s.get("sha") else ""
            lines.append(f"- {date}{tag}{sha}: {s['summary']}")

    return "\n".join(lines)
