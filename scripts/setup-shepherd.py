#!/usr/bin/env python3
"""Declare accessible harnesses, review role advice, and persist an accepted map."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROLES = ("architecture", "implementation", "design", "review", "testing", "board",
         "sounding_board", "critical_friend")
ROLE_ALIASES = {"admin": "board", "sounding-board": "sounding_board",
                "critical-friend": "critical_friend"}
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


def propose(roster, overrides=()):
    names = []
    for raw in roster:
        name = raw.strip()
        if not name or any(ord(c) < 32 for c in name):
            raise ValueError("Harness names must be nonempty text without control characters")
        if name.casefold() in {item.casefold() for item in names}:
            raise ValueError(f"Duplicate harness: {name}")
        names.append(name)
    if not names:
        raise ValueError("No accessible harnesses declared; setup cannot allocate roles")
    # Roster order expresses preference, not a hardcoded vendor/model ranking.
    primary = names[0]
    reviewer = names[1] if len(names) > 1 else primary
    tester = names[2] if len(names) > 2 else primary
    assignments = dict(architecture=primary, implementation=primary, design=reviewer,
                       review=reviewer, testing=tester, board=tester)
    for override in overrides:
        role, separator, owner = override.partition("=")
        role, owner = role.strip(), owner.strip()
        role = ROLE_ALIASES.get(role, role)
        if not separator or role not in ROLES:
            raise ValueError(f"Use role=harness with one of: {', '.join(ROLES)}")
        if owner not in names:
            raise ValueError(f"Owner {owner!r} is not in the declared accessible roster")
        assignments[role] = owner
    return {
        "schema_version": 1,
        "harnesses": [{"name": name, "capabilities": "Unverified"} for name in names],
        "assignments": assignments,
        "coordinator_role": "architecture",
        "board_writer_role": "board",
        "readiness": "Blocked pending capability and independent worker identity preflight",
        "advice": [
            "Roster order is your preference; no model or vendor capability ranking is assumed.",
            "First harness owns planning and implementation through different worker sessions.",
            "A second harness owns design and review when available; tickets activate design only when needed.",
            "Sounding Board and Critical Friend are optional and allocated only by explicit declaration.",
            "A third harness owns testing and Admin board duties when available; with two, testing uses the first.",
            "Architect, Executor, Reviewer and Tester require distinct observed worker identities.",
            "Exactly one Admin writes the board and records an authorized acceptor's decision.",
            "Admin may use the least-cost capable model its harness exposes; capability still needs preflight.",
            "Overrides replace this advice. Each owner must still pass capability preflight."
        ],
    }


def apply_launcher_mappings(config, launchers, kinds):
    entries = {entry["name"]: entry for entry in config["harnesses"]}
    for field, mappings in (("executable", launchers), ("herdr_kind", kinds)):
        for declaration in mappings:
            owner, separator, value = declaration.partition("=")
            owner, value = owner.strip(), value.strip()
            if not separator or owner not in entries or not value or any(ord(c) < 32 for c in value):
                raise ValueError(f"Use declared-harness=value for {field}; owner must be accessible")
            entries[owner][field] = value
    return config


def safe_config_path(project):
    if project.is_symlink():
        raise ValueError("Symlink project root refused")
    path = project.resolve() / ".shepherd/project.json"
    for candidate in [path, *path.parents]:
        if candidate.is_symlink():
            raise ValueError(f"Symlink config path refused: {candidate}")
    if path.exists() and not path.is_file():
        raise ValueError("Configuration destination is not a regular file")
    return path


def save(path, config, force):
    if path.exists() and not force:
        raise ValueError("Existing configuration preserved; use --force to replace it explicitly")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(config, indent=2) + "\n"
    if not force:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(data)
    else:
        descriptor, temporary = tempfile.mkstemp(prefix=".setup-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(data)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def show_allocation(path):
    """Print accepted role-to-harness allocations without probing runtime state."""
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"No accepted setup configuration found at {path}") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read valid setup configuration at {path}: {error}") from error
    if (not isinstance(config, dict) or config.get("schema_version") != 1
            or config.get("allocation_accepted") is not True
            or not isinstance(config.get("assignments"), dict)
            or not isinstance(config.get("harnesses"), list)):
        raise ValueError(f"Invalid or unaccepted setup configuration at {path}")

    assignments = config["assignments"]
    harnesses = config["harnesses"]
    if not REQUIRED_ROLES.issubset(assignments):
        raise ValueError(f"Incomplete role assignments in setup configuration at {path}")
    names = set()
    for entry in harnesses:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not entry["name"].strip():
            raise ValueError(f"Invalid harness roster in setup configuration at {path}")
        names.add(entry["name"])
    for role, owner in assignments.items():
        if role not in ROLE_LABELS or not isinstance(owner, str) or owner not in names:
            raise ValueError(f"Invalid role assignment in setup configuration at {path}: {role!r}")

    print("Accepted role allocations (persisted harness choices):")
    for role, label in ROLE_LABELS.items():
        owner = assignments.get(role)
        value = owner if owner is not None else ("Unassigned" if role in OPTIONAL_ROLES else "Missing")
        print(f"  {label}: {value}")
    print("These are saved harness allocations, not live worker/session identities or readiness evidence.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("."))
    parser.add_argument("--show", action="store_true",
                        help="Display accepted role-to-harness allocations without writing or probing")
    parser.add_argument("--harness", action="append", help="Accessible harness in preference order; repeat")
    parser.add_argument("--assign", action="append", default=[],
                        help="Override role=harness; repeat. Roles: " + ", ".join(ROLES) +
                             "; aliases: admin, sounding-board, critical-friend")
    parser.add_argument("--strength", action="append", default=[], help="Declared role strength role=harness; influences advice before --assign")
    parser.add_argument("--launcher", action="append", default=[], help="Explicit harness=executable mapping; repeat, never launched by setup")
    parser.add_argument("--kind", action="append", default=[], help="Explicit harness=Herdr-kind mapping; repeat, verified by doctor later")
    parser.add_argument("--preferences", default="", help="Optional tools, cost or capability preferences")
    parser.add_argument("--accept", action="store_true", help="Explicitly accept and save noninteractive proposal")
    parser.add_argument("--force", action="store_true", help="Replace existing project.json after acceptance")
    args = parser.parse_args()
    try:
        path = safe_config_path(args.project)
        if args.show:
            setup_options = (args.harness is not None or args.assign or args.strength or args.launcher
                             or args.kind or args.preferences or args.accept or args.force)
            if setup_options:
                raise ValueError("--show cannot be combined with setup options")
            show_allocation(path)
            return 0
        interactive = args.harness is None and sys.stdin.isatty()
        if args.harness is None and not interactive:
            raise ValueError("Noninteractive setup requires --harness; no assignments were saved")
        roster = args.harness
        preferences = args.preferences
        overrides = args.assign
        if interactive:
            print("Which coding harnesses/agents can you access? Enter names in preference order.")
            roster = input("Names, separated by commas: ").split(",")
            preferences = input("Optional capabilities, tools, budget or role preferences: ").strip()
            print("Optional help: design (allocated by default), sounding_board, critical_friend; admin aliases board.")
            strengths = input("Known role strengths (role=harness, comma-separated), or Enter: ").strip()
            if strengths:
                args.strength.extend(strengths.split(","))
            launchers = input("Known launchers (harness=executable, comma-separated), or Enter for Unverified: ").strip()
            kinds = input("Known Herdr kinds (harness=kind, comma-separated), or Enter for Unverified: ").strip()
            if launchers:
                args.launcher.extend(launchers.split(","))
            if kinds:
                args.kind.extend(kinds.split(","))
        config = propose(roster, [*args.strength, *overrides])
        apply_launcher_mappings(config, args.launcher, args.kind)
        config["preferences"] = preferences
        config["declared_strengths"] = args.strength
        print(json.dumps(config, indent=2))
        if preferences:
            print("Preferences are recorded for agent-led advice/preflight; this helper does not infer capabilities.")
        if interactive:
            edits = input("Optional overrides (role=harness separated by commas), or Enter: ").strip()
            if edits:
                config = propose(roster, [*args.strength, *overrides, *edits.split(",")])
                apply_launcher_mappings(config, args.launcher, args.kind)
                config["preferences"] = preferences
                config["declared_strengths"] = args.strength
                print(json.dumps(config, indent=2))
            accepted = input("Accept and save this allocation? [y/N]: ").strip().casefold() in ("y", "yes")
        else:
            accepted = args.accept
        if not accepted:
            print("Proposal only; no configuration written. Use --accept after reviewing it.")
            return 0
        config["allocation_accepted"] = True
        save(path, config, args.force)
        print(f"Saved {path}. Allocation accepted; capabilities and worker identities remain unverified.")
        print("Next: python3 scripts/doctor-shepherd.py --project " + str(args.project))
        return 0
    except (ValueError, OSError, EOFError, KeyboardInterrupt) as error:
        parser.exit(1, f"Setup stopped: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
