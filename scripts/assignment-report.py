#!/usr/bin/env python3
"""Read-only role/harness/pane cross-check. Never writes files or dispatches work."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

ROLE_LABELS = {
    "architecture": "Coordinator / Architect",
    "implementation": "Executor",
    "design": "Designer (optional)",
    "review": "Reviewer",
    "testing": "Tester",
    "board": "Admin / board writer",
    "sounding_board": "Sounding Board (optional)",
    "critical_friend": "Critical Friend (optional)",
}
OPTIONAL_ROLES = {"design", "sounding_board", "critical_friend"}
REQUIRED_ROLES = set(ROLE_LABELS) - OPTIONAL_ROLES


def safe_config_path(project: Path) -> Path:
    if project.is_symlink():
        raise ValueError("Symlink project root refused")
    path = project.resolve() / ".shepherd/project.json"
    for candidate in [path, *path.parents]:
        if candidate.is_symlink():
            raise ValueError(f"Symlink config path refused: {candidate}")
    return path


def load_accepted_config(project: Path) -> dict:
    path = safe_config_path(project)
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"No accepted setup configuration found at {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read valid setup configuration at {path}: {exc}") from exc
    if (not isinstance(config, dict) or config.get("schema_version") != 1
            or config.get("allocation_accepted") is not True
            or not isinstance(config.get("assignments"), dict)
            or not isinstance(config.get("harnesses"), list)):
        raise ValueError(f"Invalid or unaccepted setup configuration at {path}")
    assignments = config["assignments"]
    if not REQUIRED_ROLES.issubset(assignments):
        raise ValueError(f"Incomplete role assignments in setup configuration at {path}")
    names = set()
    for entry in config["harnesses"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not entry["name"].strip():
            raise ValueError(f"Invalid harness roster in setup configuration at {path}")
        names.add(entry["name"])
    for role, owner in assignments.items():
        if role not in ROLE_LABELS or not isinstance(owner, str) or owner not in names:
            raise ValueError(f"Invalid role assignment in setup configuration at {path}: {role!r}")
    return config


def observe_panes(herdr: str, timeout: int = 10):
    """Strictly read-only. Returns None (meaning Unverified) whenever live observation
    is not actually available or confirmed; never guesses or infers pane state."""
    if os.environ.get("HERDR_ENV") != "1":
        return None
    if not shutil.which(herdr) and not Path(herdr).is_file():
        return None
    try:
        result = subprocess.run([herdr, "pane", "list"], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    panes = payload.get("result", {}).get("panes")
    return panes if isinstance(panes, list) else None


def correlate(config: dict, panes) -> list[dict]:
    assignments = config["assignments"]
    by_label: dict[str, list[dict]] = {}
    if panes is not None:
        for pane in panes:
            if not isinstance(pane, dict):
                continue
            label = pane.get("label")
            if isinstance(label, str) and label.strip():
                by_label.setdefault(label.casefold(), []).append(pane)

    rows = []
    for role, label in ROLE_LABELS.items():
        harness = assignments.get(role)
        row = {"role": role, "label": label,
               "harness": harness or ("Unassigned" if role in OPTIONAL_ROLES else "Missing")}
        if not harness:
            row.update(pane="Unverified", agent="Unverified", session="Unverified", state="Not assigned")
            rows.append(row)
            continue
        if panes is None:
            row.update(pane="Unverified", agent="Unverified", session="Unverified",
                       state="Unverified (no live Herdr observation)")
            rows.append(row)
            continue
        matches = by_label.get(harness.casefold(), [])
        if len(matches) != 1:
            row.update(pane="Unverified", agent="Unverified", session="Unverified",
                       state="Unverified (no unique observed pane labeled for this harness)")
            rows.append(row)
            continue
        pane = matches[0]
        session = pane.get("agent_session")
        session_value = (session.get("value") if isinstance(session, dict)
                         and isinstance(session.get("value"), str) else "Unavailable")
        row.update(
            pane=pane.get("pane_id", "Unavailable"),
            agent=pane.get("agent", "Unavailable"),
            session=session_value,
            state=pane.get("agent_status", "Unavailable"),
        )
        rows.append(row)
    return rows


def render(rows: list[dict], live: bool) -> str:
    lines = [
        "Accepted allocation cross-checked against observed Herdr pane state." if live
        else "Accepted allocation only; no live Herdr observation available "
             "(outside HERDR_ENV=1, herdr unavailable, or the read-only call did not return a usable pane list).",
        "Provenance: 'harness' is a persisted config choice; 'pane/agent/session/state' are live-observed "
        "facts reported by Herdr itself. Pane ownership and creating-ticket provenance are not Herdr fields "
        "and remain Unavailable here; cross-reference the external assignment manifest separately.",
    ]
    for row in rows:
        lines.append(f"  {row['label']}: harness={row['harness']} pane={row['pane']} agent={row['agent']} "
                     f"session={row['session']} state={row['state']}")
    lines.append("This report records no acknowledgement, dispatch, close or acceptance and writes nothing; "
                 "completion history stays in the ticket's own Reports/Blockers sections. Ownership and "
                 "creating-ticket fields require the external assignment manifest; use pane-lifecycle.py "
                 "with that manifest-enriched inventory to produce a conservative close plan.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("."))
    parser.add_argument("--herdr", default="herdr", help="Herdr executable to probe read-only, if any")
    args = parser.parse_args()
    try:
        config = load_accepted_config(args.project)
        panes = observe_panes(args.herdr)
        rows = correlate(config, panes)
        print(render(rows, live=panes is not None))
        return 0
    except ValueError as error:
        parser.exit(1, f"Assignment report stopped: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
