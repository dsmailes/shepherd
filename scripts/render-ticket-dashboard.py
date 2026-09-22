#!/usr/bin/env python3
"""Render static or terminal dashboards. Adapted from dev-team; see ../LICENSE (MIT)."""

from __future__ import annotations

import argparse
import datetime as _datetime
import html
import math
import os
import re
import shutil
import sys
import time
import unicodedata
from pathlib import Path


STATES = ["Backlog", "Ready", "Design", "In Progress", "Review", "Test", "Done", "Blocked", "Superseded"]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text()


def section(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^## {re.escape(heading)}\s*$\n(?P<body>.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group("body").strip() if match else ""


def plain_value(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^`|`$", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def first_nonempty_line(value: str) -> str:
    for line in value.splitlines():
        line = plain_value(line)
        if line:
            return line
    return ""


def list_items(value: str) -> list[str]:
    items: list[str] = []
    for line in value.splitlines():
        match = re.match(r"^\s*[-*]\s+(.*)", line)
        if match:
            item = plain_value(match.group(1))
            if item:
                items.append(item)
    return items


def first_paragraph(value: str) -> str:
    lines: list[str] = []
    for line in value.splitlines():
        stripped = line.strip()
        if not stripped:
            if lines:
                break
            continue
        if stripped.startswith(("-", "*", "#")):
            continue
        lines.append(stripped)
    return plain_value(" ".join(lines))


def parse_checklists(text: str) -> tuple[int, int]:
    total = len(re.findall(r"^\s*-\s+\[[ xX]\]", text, re.MULTILINE))
    done = len(re.findall(r"^\s*-\s+\[[xX]\]", text, re.MULTILINE))
    return done, total


def queue_warnings(queue_path: Path) -> list[str]:
    if not queue_path.is_file():
        return ["Missing .tickets/queue.md."]
    warnings = []
    seen = set()
    state = ""
    for line in read_text(queue_path).splitlines():
        if line.startswith("## "):
            state = line[3:].strip()
        for ticket_id in re.findall(r"^\s*[-*]\s+`([^`]+)`", line):
            if not re.fullmatch(r"[A-Z][A-Z0-9]*-[0-9]+", ticket_id):
                warnings.append(f"Invalid queue ticket ID: {ticket_id}.")
            if ticket_id in seen:
                warnings.append(f"Duplicate queue ticket: {ticket_id}.")
            seen.add(ticket_id)
            if state not in STATES:
                warnings.append(f"{ticket_id}: queue entry outside a lifecycle heading.")
    return warnings


def parse_queue(queue_path: Path) -> dict[str, str]:
    if not queue_path.exists():
        return {}

    queue: dict[str, str] = {}
    current_state = ""
    for raw_line in read_text(queue_path).splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", raw_line)
        if heading:
            candidate = heading.group(1).strip()
            current_state = candidate if candidate in STATES else ""
            continue

        item = re.search(r"`([^`]+)`", raw_line)
        if current_state and item:
            queue[item.group(1)] = current_state
    return queue


def parse_ticket(path: Path, project: Path, queue_state: str | None) -> dict[str, object]:
    text = read_text(path)
    title = first_nonempty_line(section(text, "Title"))
    state = plain_value(section(text, "State"))
    declared_id = first_nonempty_line(section(text, "ID"))
    ticket_id = ""

    h1 = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    if h1:
        ticket_id = plain_value(h1.group(1))
    if not ticket_id:
        ticket_id = path.stem

    acceptance = list_items(section(text, "Acceptance Criteria"))
    risks = list_items(section(text, "Risks"))
    done_checks, total_checks = parse_checklists(section(text, "Handoff Gates"))
    problem = first_paragraph(section(text, "Problem"))
    verification = first_paragraph(section(text, "Verification Plan"))
    relative_path = path.relative_to(project)

    warnings: list[str] = []
    if not re.fullmatch(r"[A-Z][A-Z0-9]*-[0-9]+", ticket_id):
        warnings.append("Invalid ticket ID.")
    if ticket_id != path.stem:
        warnings.append(f"Filename is {path.stem}; ticket ID is {ticket_id}.")
    if declared_id and declared_id != ticket_id:
        warnings.append(f"ID section says {declared_id}; ticket ID is {ticket_id}.")
    if not declared_id:
        warnings.append("Missing ID section.")
    if queue_state and state and queue_state != state:
        warnings.append(f"Queue says {queue_state}; ticket says {state}.")
    if not queue_state:
        warnings.append("Not listed in .tickets/queue.md.")
    if not state:
        warnings.append("Missing state.")
    if state and state not in STATES:
        warnings.append(f"Unknown ticket state: {state}.")
    if not title:
        warnings.append("Missing title.")

    return {
        "id": ticket_id,
        "title": title or "(Untitled ticket)",
        "state": state or "Unknown",
        "queue_state": queue_state or "",
        "problem": problem,
        "acceptance_count": len(acceptance),
        "risks": risks,
        "verification": verification,
        "checks_done": done_checks,
        "checks_total": total_checks,
        "path": relative_path.as_posix(),
        "warnings": warnings,
    }


def discover_tickets(project: Path) -> list[Path]:
    tickets_dir = project / ".tickets"
    if not tickets_dir.exists():
        return []
    ignored = {"template.md", "queue.md", "README.md"}
    return sorted(path for path in tickets_dir.glob("*.md") if path.name not in ignored)


def state_class(state: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", state.lower()).strip("-") or "unknown"


def pct(done: int, total: int) -> int:
    if total == 0:
        return 0
    return round((done / total) * 100)


def markdown_escape(value: object) -> str:
    text = str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace("|", "\\|")
    text = text.replace("\n", " ")
    return text.strip()


def checkbox(done: int, total: int) -> str:
    if total == 0:
        return "n/a"
    return f"{done}/{total} ({pct(done, total)}%)"


def collect_dashboard_data(project: Path, output: Path) -> dict[str, object]:
    queue = parse_queue(project / ".tickets" / "queue.md")
    tickets = [parse_ticket(path, project, queue.get(path.stem)) for path in discover_tickets(project)]
    for ticket in tickets:
        ticket_path = project / str(ticket["path"])
        ticket["href"] = os.path.relpath(ticket_path, output.parent).replace(os.sep, "/")

    ticket_ids = {str(ticket["id"]) for ticket in tickets}
    queue_only = sorted(ticket_id for ticket_id in queue if ticket_id not in ticket_ids)
    counts = {state: 0 for state in STATES}
    for ticket in tickets:
        state = str(ticket["state"])
        if state in counts:
            counts[state] += 1

    warnings = queue_warnings(project / ".tickets" / "queue.md")
    for ticket in tickets:
        warnings.extend(f"{ticket['id']}: {warning}" for warning in ticket["warnings"])
    warnings.extend(f"{ticket_id}: listed in queue but no matching ticket file was found." for ticket_id in queue_only)

    generated_at = _datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    total_tickets = len(tickets)
    active_count = sum(counts[state] for state in STATES if state not in {"Done", "Superseded"})
    blocked_count = counts["Blocked"]

    return {
        "tickets": tickets,
        "counts": counts,
        "warnings": warnings,
        "generated_at": generated_at,
        "total_tickets": total_tickets,
        "active_count": active_count,
        "blocked_count": blocked_count,
    }


def render_dashboard(project: Path, output: Path, markdown_output: Path | None = None) -> list[Path]:
    data = collect_dashboard_data(project, output)
    tickets = data["tickets"]
    counts = data["counts"]
    warnings = data["warnings"]
    generated_at = data["generated_at"]
    total_tickets = data["total_tickets"]
    active_count = data["active_count"]
    blocked_count = data["blocked_count"]

    rows = "\n".join(render_ticket_row(ticket) for ticket in tickets)
    state_filters = "\n".join(
        f'<button class="state-filter" type="button" data-state="{html.escape(state)}">'
        f"<span>{html.escape(state)}</span><strong>{counts[state]}</strong></button>"
        for state in STATES
    )
    warning_html = render_warnings(warnings)

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ticket Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f7f8;
      --surface: #ffffff;
      --ink: #1e252b;
      --muted: #61707b;
      --line: #d8e0e5;
      --accent: #23746f;
      --accent-soft: #d9eeeb;
      --warn: #a94d16;
      --blocked: #a83248;
      --done: #3f7f46;
      --shadow: 0 18px 45px rgba(23, 35, 43, 0.08);
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}

    a {{ color: inherit; }}

    .page {{
      min-height: 100svh;
      display: grid;
      grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
    }}

    aside {{
      position: sticky;
      top: 0;
      height: 100svh;
      padding: 28px 22px;
      background: #17232b;
      color: #f7fafb;
      overflow: auto;
    }}

    .brand {{
      margin: 0 0 6px;
      font-size: 22px;
      line-height: 1.1;
      font-weight: 760;
      letter-spacing: 0;
    }}

    .timestamp {{
      margin: 0 0 24px;
      color: rgba(247, 250, 251, 0.72);
      font-size: 13px;
    }}

    .metric {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      align-items: baseline;
      padding: 12px 0;
      border-top: 1px solid rgba(247, 250, 251, 0.14);
    }}

    .metric span {{ color: rgba(247, 250, 251, 0.74); }}
    .metric strong {{ font-size: 26px; line-height: 1; }}

    .state-filters {{
      display: grid;
      gap: 4px;
      margin-top: 24px;
    }}

    .state-filter {{
      appearance: none;
      border: 0;
      border-radius: 6px;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      width: 100%;
      padding: 10px 12px;
      background: transparent;
      color: rgba(247, 250, 251, 0.82);
      text-align: left;
      font: inherit;
      cursor: pointer;
    }}

    .state-filter:hover,
    .state-filter.active {{
      background: rgba(247, 250, 251, 0.11);
      color: #ffffff;
    }}

    main {{
      min-width: 0;
      padding: 34px min(5vw, 56px) 56px;
    }}

    header {{
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: end;
      margin-bottom: 28px;
    }}

    h1 {{
      margin: 0;
      font-size: clamp(28px, 4vw, 52px);
      line-height: 1;
      letter-spacing: 0;
    }}

    .subhead {{
      max-width: 680px;
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 16px;
    }}

    .search {{
      min-width: min(360px, 100%);
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 12px 14px;
      background: var(--surface);
      color: var(--ink);
      font: inherit;
      box-shadow: var(--shadow);
    }}

    .warnings {{
      border-left: 4px solid var(--warn);
      background: #fff3e7;
      padding: 14px 16px;
      margin-bottom: 22px;
    }}

    .warnings h2 {{
      margin: 0 0 8px;
      font-size: 15px;
    }}

    .warnings ul {{
      margin: 0;
      padding-left: 20px;
      color: #613118;
    }}

    .table-wrap {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: auto;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 880px;
    }}

    th, td {{
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}

    th {{
      position: sticky;
      top: 0;
      z-index: 1;
      background: #eef3f5;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}

    tr:last-child td {{ border-bottom: 0; }}
    tr.hidden {{ display: none; }}

    .ticket-id {{
      font-weight: 760;
      white-space: nowrap;
    }}

    .ticket-title {{
      margin: 0 0 4px;
      font-weight: 700;
    }}

    .ticket-problem {{
      margin: 0;
      color: var(--muted);
      max-width: 520px;
    }}

    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 4px 9px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: #0d4f4b;
      font-size: 13px;
      font-weight: 700;
      white-space: nowrap;
    }}

    .state-blocked {{ background: #f6dce3; color: var(--blocked); }}
    .state-done {{ background: #dceedd; color: var(--done); }}
    .state-superseded {{ background: #e3e0f2; color: #554c86; }}
    .state-unknown {{ background: #ede5d8; color: #695a42; }}

    .progress {{
      display: grid;
      gap: 6px;
      min-width: 120px;
    }}

    .bar {{
      height: 7px;
      overflow: hidden;
      border-radius: 999px;
      background: #dce5e9;
    }}

    .bar span {{
      display: block;
      height: 100%;
      width: var(--pct);
      background: var(--accent);
    }}

    .meta {{
      color: var(--muted);
      font-size: 13px;
    }}

    .risk-list {{
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
    }}

    .empty {{
      margin: 0;
      color: var(--muted);
    }}

    @media (max-width: 840px) {{
      .page {{ display: block; }}
      aside {{
        position: static;
        height: auto;
        padding: 22px 18px;
      }}
      main {{ padding: 24px 16px 42px; }}
      header {{
        display: grid;
        align-items: start;
      }}
      .search {{ min-width: 0; width: 100%; }}
      .state-filters {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <aside>
      <p class="brand">Ticket Dashboard</p>
      <p class="timestamp">Generated {html.escape(generated_at)}</p>
      <p class="timestamp">Generated projection only. Live state is in .tickets/.</p>
      <div class="metric"><span>Total tickets</span><strong>{total_tickets}</strong></div>
      <div class="metric"><span>Active</span><strong>{active_count}</strong></div>
      <div class="metric"><span>Blocked</span><strong>{blocked_count}</strong></div>
      <nav class="state-filters" aria-label="Filter by state">
        <button class="state-filter active" type="button" data-state="All"><span>All</span><strong>{total_tickets}</strong></button>
        {state_filters}
      </nav>
    </aside>
    <main>
      <header>
        <div>
          <h1>Current ticket state</h1>
          <p class="subhead">A static view of local Markdown tickets, queue alignment, handoff progress, risks, and verification notes.</p>
        </div>
        <input class="search" type="search" placeholder="Search tickets" aria-label="Search tickets">
      </header>
      {warning_html}
      <section class="table-wrap" aria-label="Tickets">
        <table>
          <thead>
            <tr>
              <th>Ticket</th>
              <th>State</th>
              <th>Handoff Gates</th>
              <th>Acceptance</th>
              <th>Risks</th>
              <th>Verification</th>
            </tr>
          </thead>
          <tbody>
            {rows or '<tr><td colspan="6"><p class="empty">No ticket files found in .tickets.</p></td></tr>'}
          </tbody>
        </table>
      </section>
    </main>
  </div>
  <script>
    const filters = document.querySelectorAll(".state-filter");
    const rows = document.querySelectorAll("tbody tr[data-state]");
    const search = document.querySelector(".search");
    let selectedState = "All";

    function applyFilters() {{
      const query = search.value.trim().toLowerCase();
      rows.forEach((row) => {{
        const matchesState = selectedState === "All" || row.dataset.state === selectedState;
        const matchesSearch = !query || row.textContent.toLowerCase().includes(query);
        row.classList.toggle("hidden", !(matchesState && matchesSearch));
      }});
    }}

    filters.forEach((button) => {{
      button.addEventListener("click", () => {{
        selectedState = button.dataset.state;
        filters.forEach((item) => item.classList.toggle("active", item === button));
        applyFilters();
      }});
    }});

    search.addEventListener("input", applyFilters);
  </script>
</body>
</html>
"""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    written = [output]

    if markdown_output is not None:
        markdown = render_markdown_dashboard(
            project=project,
            output=markdown_output,
            tickets=tickets,
            counts=counts,
            warnings=warnings,
            generated_at=generated_at,
            total_tickets=total_tickets,
            active_count=active_count,
            blocked_count=blocked_count,
        )
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(markdown, encoding="utf-8")
        written.append(markdown_output)

    return written


def render_markdown_dashboard(
    project: Path,
    output: Path,
    tickets: list[dict[str, object]],
    counts: dict[str, int],
    warnings: list[str],
    generated_at: str,
    total_tickets: int,
    active_count: int,
    blocked_count: int,
) -> str:
    for ticket in tickets:
        ticket_path = project / str(ticket["path"])
        ticket["markdown_href"] = os.path.relpath(ticket_path, output.parent).replace(os.sep, "/")

    state_lines = "\n".join(f"- **{state}:** {counts[state]}" for state in STATES)
    warning_section = ""
    if warnings:
        warning_items = "\n".join(f"- {markdown_escape(warning)}" for warning in warnings)
        warning_section = f"\n## Attention Needed\n\n{warning_items}\n"

    if tickets:
        rows = "\n".join(render_markdown_ticket_row(ticket) for ticket in tickets)
    else:
        rows = "| No ticket files found in `.tickets`. | | | | | |"

    return f"""# Ticket Dashboard

Generated {generated_at}.

> Generated projection only. The authoritative live board is `.tickets/*.md` plus `.tickets/queue.md`. Regenerate this file after every board mutation.

## Summary

- **Total tickets:** {total_tickets}
- **Active:** {active_count}
- **Blocked:** {blocked_count}

## State Counts

{state_lines}
{warning_section}
## Tickets

| Ticket | State | Handoff Gates | Acceptance | Risks | Verification |
| --- | --- | --- | --- | --- | --- |
{rows}
"""


def render_markdown_ticket_row(ticket: dict[str, object]) -> str:
    ticket_id = markdown_escape(ticket["id"])
    title = markdown_escape(ticket["title"])
    state = markdown_escape(ticket["state"])
    href = str(ticket["markdown_href"])
    problem = markdown_escape(ticket["problem"])
    checks = checkbox(int(ticket["checks_done"]), int(ticket["checks_total"]))
    risks = [markdown_escape(risk) for risk in ticket["risks"]]
    risk_summary = "<br>".join(risks[:3]) if risks else "None listed."
    verification = markdown_escape(ticket["verification"] or "No verification plan summary found.")
    acceptance_count = markdown_escape(ticket["acceptance_count"])
    ticket_cell = f"[{ticket_id}]({href})<br>**{title}**"
    if problem:
        ticket_cell += f"<br>{problem}"
    return f"| {ticket_cell} | {state} | {checks} | {acceptance_count} criteria | {risk_summary} | {verification} |"


def render_ticket_row(ticket: dict[str, object]) -> str:
    ticket_id = str(ticket["id"])
    title = str(ticket["title"])
    state = str(ticket["state"])
    href = str(ticket["href"])
    checks_done = int(ticket["checks_done"])
    checks_total = int(ticket["checks_total"])
    risks = [str(risk) for risk in ticket["risks"]]
    risk_html = (
        "<ul class=\"risk-list\">" + "".join(f"<li>{html.escape(risk)}</li>" for risk in risks[:3]) + "</ul>"
        if risks
        else '<p class="empty">None listed.</p>'
    )
    verification = str(ticket["verification"]) or "No verification plan summary found."
    problem = str(ticket["problem"])
    percent = pct(checks_done, checks_total)

    return f"""<tr data-state="{html.escape(state)}">
  <td>
    <a class="ticket-id" href="{html.escape(href)}">{html.escape(ticket_id)}</a>
    <p class="ticket-title">{html.escape(title)}</p>
    <p class="ticket-problem">{html.escape(problem)}</p>
  </td>
  <td><span class="badge state-{state_class(state)}">{html.escape(state)}</span></td>
  <td>
    <div class="progress">
      <div class="bar" aria-hidden="true"><span style="--pct: {percent}%"></span></div>
      <span class="meta">{checks_done} of {checks_total} checks complete</span>
    </div>
  </td>
  <td><span class="meta">{ticket["acceptance_count"]} criteria</span></td>
  <td>{risk_html}</td>
  <td><span class="meta">{html.escape(verification)}</span></td>
</tr>"""


def render_warnings(warnings: list[str]) -> str:
    if not warnings:
        return ""
    items = "".join(f"<li>{html.escape(warning)}</li>" for warning in warnings)
    return f"""<section class="warnings" aria-label="Ticket warnings">
  <h2>Attention needed</h2>
  <ul>{items}</ul>
</section>"""


def terminal_text(value: object) -> str:
    """Keep text inert: no terminal controls, bidi overrides or joiners."""
    text = unicodedata.normalize("NFC", str(value))
    return "".join(" " if char.isspace() else char for char in text
                   if not unicodedata.category(char).startswith("C") or char.isspace())


def cell_width(char: str) -> int:
    if unicodedata.combining(char) or unicodedata.category(char).startswith("M"):
        return 0
    # Ambiguous characters and symbols get a conservative allowance: their
    # displayed width depends on terminal/font/locale (not available in stdlib).
    return 2 if unicodedata.east_asian_width(char) in "WFA" or unicodedata.category(char) == "So" else 1


def terminal_fit(value: object, width: int, pad: bool = False) -> str:
    text = terminal_text(value)
    truncated = sum(cell_width(char) for char in text) > width
    limit = max(0, width - 1) if truncated else width
    result = ""
    used = 0
    for char in text:
        cells = cell_width(char)
        if used + cells > limit:
            break
        result += char
        used += cells
    if truncated and width > 0:
        result += "~"
        used += 1
    return result + " " * max(0, width - used) if pad else result


def terminal_dimensions(width: int | None, height: int | None) -> tuple[int, int]:
    try:
        size = os.get_terminal_size(sys.stdout.fileno())
    except (OSError, ValueError, AttributeError):
        size = shutil.get_terminal_size(fallback=(120, 24))
    return width or max(1, size.columns), height or max(1, size.lines)


def render_terminal(project: Path, data: dict[str, object], width: int, height: int) -> str:
    """Leave a spare column and row to avoid terminal autowrap/scrolling."""
    columns, rows = max(1, width - 1), max(1, height - 1)
    tickets = data["tickets"]
    warnings = data["warnings"]
    priority = ["Blocked", "In Progress", "Review", "Test", "Ready", "Design", "Backlog", "Superseded", "Done"]
    ordered = sorted(tickets, key=lambda ticket: (
        priority.index(ticket["state"]) if ticket["state"] in priority else
        len(priority) + (ticket["state"] == "Done"), str(ticket["id"])))
    active = sum(ticket["state"] not in {"Done", "Superseded"} for ticket in tickets)
    blocked = sum(ticket["state"] == "Blocked" for ticket in tickets)
    lines = [f"Shepherd | {project.name}",
             f"{len(tickets)} tickets | {active} active | {blocked} blocked | {len(warnings)} warnings"]
    # Compact counts stay useful in a 40-column split.
    if sum(cell_width(char) for char in lines[1]) > columns:
        lines[1] = f"Total {len(tickets)}  Active {active}  Blocked {blocked}  Warn {len(warnings)}"
    id_width = min(18, max(9, max((len(str(ticket["id"])) for ticket in tickets), default=9)))
    id_width = max(1, min(id_width, columns - 21))
    state_width = 11
    lines.append(f'{terminal_fit("ID", id_width, True)}  {terminal_fit("STATE", state_width, True)}  TITLE')
    warning_rows = 1 if warnings else 0
    capacity = max(0, rows - len(lines) - warning_rows)
    if len(ordered) > capacity:
        capacity = max(0, capacity - 1)  # Keep room for the overflow count.
    for ticket in ordered[:capacity]:
        lines.append(f'{terminal_fit(ticket["id"], id_width, True)}  '
                     f'{terminal_fit(ticket["state"], state_width, True)}  {terminal_text(ticket["title"])}')
    if not tickets and len(lines) < rows - warning_rows:
        lines.append("No tickets.")
    hidden = len(ordered) - capacity if len(ordered) > capacity else 0
    if hidden:
        lines.append(f"Showing {min(capacity, len(ordered))}/{len(ordered)} tickets; {hidden} hidden")
    if warnings:
        lines.append(f"! {len(warnings)} warning(s): {warnings[0]}")
    # Extremely short panes still report omitted rows rather than imply completeness.
    if len(lines) > rows:
        lines = lines[:max(0, rows - 1)] + [f"{len(tickets)} tickets; {len(warnings)} warnings; enlarge pane"]
    return "\n".join(terminal_fit(line, columns) for line in lines)


def board_signature(project: Path) -> tuple[tuple[str, bytes | None], ...]:
    paths = [project / ".tickets" / "queue.md", *discover_tickets(project)]
    return tuple((path.name, path.read_bytes() if path.exists() else None) for path in paths)


def show_terminal(project: Path, width: int | None, height: int | None,
                  watch: bool, interval: float) -> int:
    previous = None
    try:
        while True:
            dimensions = terminal_dimensions(width, height)
            read_failed = False
            try:
                signature = board_signature(project)
                key = (dimensions, signature)
                if key != previous:
                    data = collect_dashboard_data(project, project / "docs/tickets.html")
                    frame = render_terminal(project, data, *dimensions)
                else:
                    frame = None
            except (OSError, UnicodeError) as error:
                read_failed = True
                frame = terminal_fit(f"Unable to read ticket board: {error}", max(1, dimensions[0] - 1))
                key = (dimensions, frame)
            if key != previous:
                if watch:
                    sys.stdout.write("\x1b[2J\x1b[H")
                sys.stdout.write(frame + "\n")
                sys.stdout.flush()
                previous = key
            if not watch:
                return 1 if read_failed else 0
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def positive_interval(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description="Render HTML/Markdown dashboards or a compact terminal board from .tickets/*.md.")
    parser.add_argument("--project", default=".", help="Project root containing .tickets. Defaults to current directory.")
    parser.add_argument("--output", default="docs/tickets.html", help="Output HTML path, relative to project unless absolute.")
    parser.add_argument(
        "--markdown-output",
        default="docs/tickets.md",
        help="Output Markdown path, relative to project unless absolute. Defaults to docs/tickets.md.",
    )
    parser.add_argument("--no-markdown", action="store_true", help="Only render the HTML dashboard.")
    parser.add_argument("--terminal", action="store_true", help="Print a read-only plain-text board; writes no files.")
    parser.add_argument("--watch", action="store_true", help="Watch the terminal board; redraw on content or size changes (TTY required).")
    parser.add_argument("--width", type=positive_int, help="Terminal columns; defaults to detected size.")
    parser.add_argument("--height", type=positive_int, help="Terminal rows; defaults to detected size.")
    parser.add_argument("--interval", type=positive_interval, default=1.0, help="Watch polling interval in seconds (default: 1).")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Check ticket/queue consistency and exit non-zero when dashboard warnings exist.",
    )
    args = parser.parse_args()
    if args.validate and (args.terminal or args.watch):
        parser.error("--validate cannot be combined with --terminal or --watch")
    if args.watch and not sys.stdout.isatty():
        parser.error("--watch requires a TTY; use --terminal for plain-text output")

    project = Path(args.project).resolve()
    if args.terminal or args.watch:
        return show_terminal(project, args.width, args.height, args.watch, args.interval)
    output = Path(args.output)
    if not output.is_absolute():
        output = project / output
    markdown_output = None
    if not args.no_markdown:
        markdown_output = Path(args.markdown_output)
        if not markdown_output.is_absolute():
            markdown_output = project / markdown_output

    if args.validate:
        data = collect_dashboard_data(project, output)
        warnings = data["warnings"]
        if warnings:
            print("Ticket dashboard validation failed:")
            for warning in warnings:
                print(f"- {warning}")
            return 1
        print("Ticket dashboard validation passed.")
        return 0

    written = render_dashboard(project, output, markdown_output)
    for path in written:
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
