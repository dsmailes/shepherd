#!/usr/bin/env python3
"""Plan and, after explicit acceptance, set up a Herdr workspace."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import re
import shlex

REQUIRED = ("architecture", "implementation", "review", "testing", "board")
OPTIONAL = ("design", "sounding_board", "critical_friend")
ALL_ROLES = REQUIRED + OPTIONAL
MIN_WIDTH = 20.0
MIN_HEIGHT = 8.0
BOARD_MIN_WIDTH = 40.0
BOARD_MIN_HEIGHT = 8.0
HELP_COMMANDS = {
    "split": ("pane", "split", "--help"),
    "run": ("pane", "run", "--help"),
    "start": ("agent", "start", "--help"),
}


def load_config(project: Path) -> tuple[dict, Path]:
    path = project.resolve() / ".shepherd/project.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read accepted project configuration at {path}: {exc}") from exc
    if not isinstance(config, dict) or config.get("schema_version") != 1 or config.get("allocation_accepted") is not True:
        raise ValueError("Accepted .shepherd/project.json is required")
    assignments = config.get("assignments")
    roster = config.get("harnesses")
    if not isinstance(assignments, dict) or not isinstance(roster, list):
        raise ValueError("Configuration has no valid assignments or harness roster")
    names = {item.get("name") for item in roster if isinstance(item, dict)}
    missing = [role for role in REQUIRED if role not in assignments]
    if missing:
        raise ValueError("Missing required role assignments: " + ", ".join(missing))
    if any(role not in ALL_ROLES for role in assignments):
        raise ValueError("Configuration contains an unknown role assignment")
    for role, owner in assignments.items():
        if not isinstance(owner, str) or owner not in names:
            raise ValueError(f"Role {role} has no declared harness mapping")
    return config, path


def argv_text(argv: tuple[str, ...] | list[str]) -> str:
    return json.dumps(list(argv), ensure_ascii=False)


def plan(config: dict, project: Path, active_roles: list[str] | tuple[str, ...] = ()) -> list[dict]:
    assignments = config["assignments"]
    active = set(active_roles) | {"architecture"}
    panes = []
    if "architecture" in assignments and "architecture" in active:
        panes.append({"name": "Shepherd architecture", "role": "architecture",
                      "harness": assignments["architecture"],
                      "kind": _kind(config, assignments["architecture"])})
    panes += [{"name": "Lazygit", "utility": "lazygit"},
              {"name": "Ticket Board", "board": "ticket"}]
    for role in ALL_ROLES:
        if role in assignments and role != "architecture" and role in active:
            panes.append({"name": f"Shepherd {role}", "role": role,
                          "harness": assignments[role],
                          "kind": _kind(config, assignments[role])})
    panes.append({"name": "Role Board", "board": "role"})
    return panes


def _kind(config: dict, harness: str) -> str | None:
    for item in config["harnesses"]:
        if item.get("name") == harness:
            return item.get("herdr_kind")
    return None


def print_plan(config: dict, project: Path, herdr: str, active_roles: list[str] | tuple[str, ...] = ()) -> None:
    print(f"Workspace setup preview for {project.resolve()}")
    print("No live changes are made without --accept and HERDR_ENV=1.")
    print("Layout: main Architect pane with lazygit, Ticket Board and Role Board; role panes are deferred until activated with --role.")
    print("Active roles: " + ", ".join(dict.fromkeys(["architecture", *active_roles])))
    for index, item in enumerate(plan(config, project, active_roles)):
        direction = "down" if item.get("utility") == "lazygit" else "right"
        if item.get("utility") == "lazygit":
            command = (herdr, "pane", "run", "<new-pane-id>", "lazygit")
        elif "board" in item:
            command = (herdr, "pane", "run", "<new-pane-id>", shlex.join(("python3",
                       "scripts/render-ticket-dashboard.py" if item["board"] == "ticket" else "scripts/setup-shepherd.py",
                       "--project", str(project), "--watch" if item["board"] == "ticket" else "--show")))
        else:
            command = (herdr, "agent", "start", item["role"], "--kind", item["kind"] or "<mapped-kind>", "--pane", "<new-pane-id>")
        print(f"  {item['name']} ({item.get('harness', 'read-only')}, split {direction}): {argv_text(command)}")


def checked_help(herdr: str) -> None:
    supported = set()
    for name, command in HELP_COMMANDS.items():
        result = subprocess.run([herdr, *command], capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        if result.returncode or (name == "split" and "--direction" not in output) or (name == "run" and "pane run" not in output) or (name == "start" and "--kind" not in output) or (name == "start" and "--pane" not in output):
            raise RuntimeError(f"Installed Herdr does not expose verified {name} capability")
        if name == "start":
            for values in re.findall(r"\[possible values:\s*([^\]]+)\]", output, re.I):
                supported.update(value.strip() for value in values.split(",") if value.strip())
    return supported


def json_command(herdr: str, args: list[str], timeout: int = 10) -> dict:
    result = subprocess.run([herdr, *args], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"Herdr command failed: {' '.join(args)}: {result.stderr.strip()}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Herdr returned non-JSON for {' '.join(args)}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Herdr returned invalid identity for {' '.join(args)}")
    return value


def shell_ready(info: dict, pane_id: str) -> None:
    payload = info.get("result", {}).get("process_info")
    if not isinstance(payload, dict) or not payload.get("shell_pid"):
        raise RuntimeError(f"Pane {pane_id} has unknown shell readiness")
    foreground = payload.get("foreground_processes")
    if not isinstance(foreground, list) or not foreground:
        raise RuntimeError(f"Pane {pane_id} has no observed foreground shell")
    shells = ("bash", "zsh", "sh", "fish", "ksh", "nu")
    shell_pid = payload.get("shell_pid")
    if not isinstance(shell_pid, int) or shell_pid <= 0:
        raise RuntimeError(f"Pane {pane_id} has an invalid shell PID")
    # An idle pane reports only its shell. A shell child means the pane is
    # occupied, even when the child itself was started by a shell.
    if len(foreground) != 1:
        raise RuntimeError(f"Pane {pane_id} is busy: multiple foreground processes observed")
    process = foreground[0]
    if not isinstance(process, dict):
        raise RuntimeError(f"Pane {pane_id} has unknown foreground process identity")
    process_pid = process.get("pid")
    if not isinstance(process_pid, int) or process_pid <= 0:
        raise RuntimeError(f"Pane {pane_id} has unknown foreground process PID")
    if process_pid != shell_pid:
        raise RuntimeError(f"Pane {pane_id} is busy: foreground PID {process_pid} differs from shell PID {shell_pid}")
    text = json.dumps(process).casefold()
    if not any(re.search(rf"(?:^|[^a-z]){name}(?:$|[^a-z])", text) for name in shells):
        raise RuntimeError(f"Pane {pane_id} is occupied by a non-shell foreground process")


def layout_geometry(response: dict) -> tuple[tuple[float, float], list[dict]] | None:
    value = response.get("result", {}).get("layout", response.get("result", {}))
    if not isinstance(value, dict):
        return None
    area = value.get("area")
    if not isinstance(area, dict):
        # Compatibility with early local captures; live responses use area.
        area = value
    width, height = area.get("width"), area.get("height")
    if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
        return None
    panes = value.get("panes", [])
    if not isinstance(panes, list):
        return None
    return (float(width), float(height)), panes


def layout_size(layout: dict) -> tuple[float, float] | None:
    geometry = layout_geometry(layout)
    return geometry[0] if geometry else None


def validate_geometry(response: dict, pane_count: int) -> tuple[float, float]:
    geometry = layout_geometry(response)
    if not geometry:
        raise RuntimeError("Herdr layout lacks layout.area dimensions")
    (width, height), panes = geometry
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        raise RuntimeError("Current pane layout is too small or has unknown geometry")
    for pane in panes:
        if not isinstance(pane, dict):
            raise RuntimeError("Observed pane geometry has an unknown pane entry")
        rect = pane.get("rect")
        if not isinstance(rect, dict):
            raise RuntimeError("Observed pane geometry has an unknown rect")
        pw, ph = rect.get("width"), rect.get("height")
        if not isinstance(pw, (int, float)) or not isinstance(ph, (int, float)):
            raise RuntimeError("Observed pane geometry has an unknown rect")
        if pw < MIN_WIDTH or ph < MIN_HEIGHT:
            raise RuntimeError("Existing pane geometry is below usable minimums")
    # Model the final layout as a balanced grid before issuing any split. This
    # catches the common failure where repeated splits create tiny board panes.
    candidates = []
    for columns in range(1, pane_count + 1):
        rows = (pane_count + columns - 1) // columns
        if width / columns >= BOARD_MIN_WIDTH and height / rows >= BOARD_MIN_HEIGHT:
            candidates.append((abs(width / columns - height / rows), columns))
    if not candidates:
        raise RuntimeError(f"Balanced workspace would create unusable panes ({width:g}x{height:g}, {pane_count} panes)")
    return width, height


def validate_created_pane(response: dict, pane_id: str, board: bool = False) -> tuple[float, float]:
    """Validate the measured rect for a pane returned after a real split."""
    geometry = layout_geometry(response)
    if not geometry:
        raise RuntimeError(f"Pane {pane_id} layout lacks measured area or rects")
    _, panes = geometry
    for pane in panes:
        if not isinstance(pane, dict):
            continue
        observed_id = pane.get("pane_id") or pane.get("id")
        if observed_id != pane_id:
            continue
        rect = pane.get("rect")
        if not isinstance(rect, dict):
            raise RuntimeError(f"Pane {pane_id} has an unknown measured rect")
        width, height = rect.get("width"), rect.get("height")
        if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
            raise RuntimeError(f"Pane {pane_id} has an unknown measured rect")
        minimum_width = BOARD_MIN_WIDTH if board else MIN_WIDTH
        if width < minimum_width or height < MIN_HEIGHT:
            raise RuntimeError(
                f"Pane {pane_id} measured rect is below usable minimums: {width:g}x{height:g}"
            )
        return float(width), float(height)
    raise RuntimeError(f"Pane {pane_id} was absent from measured layout")


def execute(config: dict, project: Path, herdr: str, active_roles: list[str] | tuple[str, ...] = ()) -> int:
    if os.environ.get("HERDR_ENV") != "1":
        raise RuntimeError("Live workspace setup requires the actual HERDR_ENV=1 context")
    if not shutil.which(herdr) and not Path(herdr).is_file():
        raise RuntimeError(f"Herdr executable not found: {herdr}")
    workspace_plan = plan(config, project, active_roles)
    role_items = [item for item in workspace_plan if "role" in item]
    missing = sorted({item["harness"] for item in role_items if not item["kind"]})
    if missing:
        raise RuntimeError("No Herdr kind mapping for assigned harnesses: " + ", ".join(missing))
    supported = checked_help(herdr)
    unsupported = sorted({item["kind"] for item in role_items if item["kind"] not in supported})
    if unsupported:
        raise RuntimeError("Unsupported Herdr kind mapping(s): " + ", ".join(unsupported))
    harnesses = {item["name"]: item for item in config["harnesses"]}
    missing_launchers = sorted({item["harness"] for item in role_items
                                if not harnesses[item["harness"]].get("executable")})
    unavailable_launchers = sorted({item["harness"] for item in role_items
                                   if harnesses[item["harness"]].get("executable") and
                                   not (shutil.which(harnesses[item["harness"]]["executable"]) or
                                        Path(harnesses[item["harness"]]["executable"]).is_file())})
    if missing_launchers or unavailable_launchers:
        details = missing_launchers + [f"{name} (unavailable)" for name in unavailable_launchers]
        raise RuntimeError("Configured launcher mapping unavailable: " + ", ".join(details))
    current = json_command(herdr, ["pane", "current", "--current"])
    pane = current.get("result", {}).get("pane", {})
    base = pane.get("pane_id")
    workspace = pane.get("workspace_id")
    if not base or not workspace:
        raise RuntimeError("Current Herdr response lacks explicit pane/workspace identity")
    geometry = json_command(herdr, ["pane", "layout", "--pane", base])
    layout_data = layout_geometry(geometry)
    observed_panes = layout_data[1] if layout_data else None
    size = validate_geometry(geometry, len(workspace_plan) + max(1, len(observed_panes or [])))
    panes = json_command(herdr, ["pane", "list", "--workspace", workspace]).get("result", {}).get("panes", [])
    agents = json_command(herdr, ["agent", "list"]).get("result", {}).get("agents", [])
    requested_names = {item["role"] for item in role_items}
    existing_names = {agent.get("name") or agent.get("label") for agent in agents if isinstance(agent, dict)}
    conflicts = sorted(requested_names & existing_names)
    if conflicts:
        raise RuntimeError("Live agent name conflict(s): " + ", ".join(conflicts))
    # Existing panes are not targets of this operation. We inspect only the
    # selected base pane to see whether an idle shell can safely become the
    # main Architect pane; unrelated panes may be busy workers.
    reuse_base = False
    if any(item.get("role") == "architecture" for item in workspace_plan):
        try:
            shell_ready(json_command(herdr, ["pane", "process-info", "--pane", base]), base)
            reuse_base = True
        except RuntimeError:
            reuse_base = False
    print(f"Using workspace {workspace}, base pane {base}, observed layout {size[0]:g}x{size[1]:g}; balanced split plan preserves focus.")
    created = []
    created_specs = []
    created_by_name = {}
    pane_widths = {base: size[0]}
    pane_heights = {base: size[1]}
    role_region = []
    launched = []
    for index, item in enumerate(workspace_plan):
        if reuse_base and item.get("role") == "architecture":
            pane_id = base
            created_by_name[item["name"]] = pane_id
            role_region.append(pane_id)
            run = subprocess.run([herdr, "agent", "start", item["role"], "--kind", item["kind"], "--pane", pane_id],
                                 capture_output=True, text=True, timeout=40)
            if run.returncode:
                detail = (run.stderr or run.stdout).strip()
                raise RuntimeError(f"Launch failed for {item['name']} in pane {pane_id}; diagnostic: {detail}")
            launched.append(pane_id)
            print(f"Using {item['name']} in existing main pane {pane_id}; model: Unavailable (worker telemetry not inferred).")
            continue

        if item.get("utility") == "lazygit":
            source, direction = base, "down"
        elif item.get("board") == "ticket":
            source, direction = created_by_name["Lazygit"], "right"
        elif item.get("board") == "role":
            if not role_region:
                role_region.append(base)
            source, direction = max(role_region, key=lambda pane_id: pane_widths.get(pane_id, 0)), "down"
        else:
            if not role_region:
                role_region.append(base)
            source, direction = max(role_region, key=lambda pane_id: pane_widths.get(pane_id, 0)), "right"
        try:
            split = subprocess.run([herdr, "pane", "split", "--pane", source, "--direction", direction, "--no-focus", "--cwd", str(project)], capture_output=True, text=True, timeout=20)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Pane split timed out for {item['name']}; created pane IDs: {created or 'none'}; launched: {launched or 'none'}; diagnostic: {exc.stderr or 'timeout'}; no retry was attempted") from exc
        if split.returncode:
            detail = (split.stderr or split.stdout).strip()
            raise RuntimeError(f"Pane split failed for {item['name']}; created pane IDs: {created or 'none'}; launched: {launched or 'none'}; diagnostic: {detail}; no retry was attempted")
        try:
            pane_id = json.loads(split.stdout).get("result", {}).get("pane", {}).get("pane_id")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Pane split returned no explicit pane identity for {item['name']}; created pane IDs: {created or 'none'}; launched: {launched or 'none'}; diagnostic: {split.stdout.strip()}") from exc
        if not pane_id:
            raise RuntimeError(f"Pane split returned no explicit pane identity for {item['name']}; created pane IDs: {created or 'none'}; launched: {launched or 'none'}")
        created.append(pane_id)
        created_by_name[item["name"]] = pane_id
        created_specs.append((pane_id, "board" in item))
        try:
            # Split direction is only a request; gate each created pane on its
            # measured Herdr rect before submitting any command.
            for measured_id, is_board in created_specs:
                measured = json_command(herdr, ["pane", "layout", "--pane", measured_id])
                validate_created_pane(measured, measured_id, is_board)
            measured_rect = layout_geometry(measured)[1]
            rect = next((entry.get("rect") for entry in measured_rect
                         if isinstance(entry, dict) and (entry.get("pane_id") or entry.get("id")) == pane_id), None)
            if isinstance(rect, dict):
                pane_widths[pane_id] = float(rect.get("width", 0))
                pane_heights[pane_id] = float(rect.get("height", 0))
            if direction == "right":
                pane_widths[source] = pane_widths[pane_id]
            else:
                pane_heights[source] = pane_heights[pane_id]
        except RuntimeError as exc:
            raise RuntimeError(
                f"Created pane geometry is unusable for {item['name']}; created pane IDs: {created}; "
                f"launched: {launched or 'none'}; diagnostic: {exc}; no retry was attempted"
            ) from exc
        if item.get("utility") == "lazygit" or "board" in item:
            try:
                shell_ready(json_command(herdr, ["pane", "process-info", "--pane", pane_id]), pane_id)
            except RuntimeError as exc:
                raise RuntimeError(f"New board pane {pane_id} is not ready; created pane IDs: {created}; launched: {launched or 'none'}; diagnostic: {exc}") from exc
        if item.get("utility") == "lazygit":
            command = ["lazygit"]
        elif "board" in item:
            command = ["python3", "scripts/render-ticket-dashboard.py" if item["board"] == "ticket" else "scripts/setup-shepherd.py", "--project", str(project), "--watch" if item["board"] == "ticket" else "--show"]
        if item.get("utility") == "lazygit" or "board" in item:
            try:
                run = subprocess.run([herdr, "pane", "run", pane_id, shlex.join(command)], capture_output=True, text=True, timeout=20)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(f"Utility/board command timed out in pane {pane_id}; created pane IDs: {created}; launched: {launched or 'none'}; diagnostic: {exc.stderr or 'timeout'}; no retry was attempted") from exc
        else:
            if not item["kind"]:
                raise RuntimeError(f"No Herdr kind mapping for assigned harness {item['harness']}")
            try:
                run = subprocess.run([herdr, "agent", "start", item["role"], "--kind", item["kind"], "--pane", pane_id], capture_output=True, text=True, timeout=40)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(f"Agent start timed out for {item['name']} in pane {pane_id}; created pane IDs: {created}; launched: {launched or 'none'}; diagnostic: {exc.stderr or 'timeout'}; no retry was attempted") from exc
        if run.returncode:
            detail = (run.stderr or run.stdout).strip()
            raise RuntimeError(f"Launch failed for {item['name']} in pane {pane_id}; created pane IDs: {created}; launched: {launched or 'none'}; diagnostic: {detail}; no duplicate retry was attempted")
        launched.append(pane_id)
        if "role" in item:
            role_region.append(pane_id)
        print(f"Created {item['name']} in pane {pane_id}; model: Unavailable (worker telemetry not inferred).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("."))
    parser.add_argument("--herdr", default="herdr")
    parser.add_argument("--role", action="append", choices=ALL_ROLES, default=[],
                        help="Activate a ticket-scoped role pane; repeat for multiple roles")
    parser.add_argument("--accept", action="store_true", help="Execute the reviewed plan in the current Herdr workspace")
    args = parser.parse_args()
    try:
        config, _ = load_config(args.project)
        project = args.project.resolve()
        if not args.accept:
            print_plan(config, project, args.herdr, args.role)
            return 0
        return execute(config, project, args.herdr, args.role)
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"Workspace setup stopped: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
