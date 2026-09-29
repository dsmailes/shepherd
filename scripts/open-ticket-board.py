#!/usr/bin/env python3
"""Preview or open a read-only ticket board in one Herdr pane."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess


def json_command(herdr: str, args: list[str]) -> dict:
    result = subprocess.run([herdr, *args], capture_output=True, text=True, timeout=15)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        if "PermissionDenied" in detail or "Operation not permitted" in detail:
            raise RuntimeError(
                "Herdr live API access was denied; run this command from an active Herdr pane "
                "with a reachable Herdr session"
            )
        raise RuntimeError(f"Herdr command failed: {' '.join(args)}: {detail}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Herdr returned non-JSON for {' '.join(args)}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"Herdr returned invalid response for {' '.join(args)}")
    return value


def current_pane(herdr: str) -> tuple[str, str]:
    response = json_command(herdr, ["pane", "current", "--current"])
    pane = response.get("result", {}).get("pane", {})
    pane_id, workspace_id = pane.get("pane_id"), pane.get("workspace_id")
    if not pane_id or not workspace_id:
        raise RuntimeError("Herdr current-pane response lacks explicit pane/workspace identity")
    return pane_id, workspace_id


def run_board(herdr: str, pane_id: str, project: Path) -> None:
    command = shlex.join((
        "python3", "scripts/render-ticket-dashboard.py", "--project", str(project), "--watch"
    ))
    result = subprocess.run([herdr, "pane", "run", pane_id, command],
                            capture_output=True, text=True, timeout=20)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Ticket board launch failed in pane {pane_id}: {detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("."))
    parser.add_argument("--herdr", default="herdr")
    parser.add_argument("--direction", choices=("right", "down"), default="right",
                        help="Direction for the new board pane relative to the current pane")
    parser.add_argument("--accept", action="store_true", help="Create the pane and launch the board")
    args = parser.parse_args()
    project = args.project.resolve()
    if not (project / ".tickets").is_dir():
        parser.error(f"Project has no .tickets directory: {project}")
    if not shutil.which(args.herdr) and not Path(args.herdr).is_file():
        parser.error(f"Herdr executable not found: {args.herdr}")
    try:
        if not args.accept:
            print(f"Ticket board preview for {project}")
            print("No live changes are made without --accept and HERDR_ENV=1.")
            print(f"Would split the current Herdr pane {args.direction} and run the read-only board with --watch.")
            return 0
        if os.environ.get("HERDR_ENV") != "1":
            raise RuntimeError("Opening a Herdr pane requires the actual HERDR_ENV=1 context")
        source, workspace = current_pane(args.herdr)
        split = subprocess.run(
            [args.herdr, "pane", "split", "--pane", source, "--direction", args.direction,
             "--no-focus", "--cwd", str(project)],
            capture_output=True, text=True, timeout=20)
        if split.returncode:
            detail = (split.stderr or split.stdout).strip()
            raise RuntimeError(f"Herdr pane split failed: {detail}")
        try:
            pane_id = json.loads(split.stdout).get("result", {}).get("pane", {}).get("pane_id")
        except json.JSONDecodeError as error:
            raise RuntimeError("Herdr pane split returned non-JSON output") from error
        if not pane_id:
            raise RuntimeError("Herdr pane split returned no explicit pane identity")
        run_board(args.herdr, pane_id, project)
        print(f"Created Ticket Board in pane {pane_id} in workspace {workspace}; focus preserved.")
        return 0
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Ticket board setup stopped: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
