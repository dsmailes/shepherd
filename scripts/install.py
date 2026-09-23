#!/usr/bin/env python3
"""Conservative local installer; no network, harness launches, or model prompts."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys


def checked_destination(target, relative):
    path = target / relative
    for candidate in [path, *path.parents]:
        if candidate.is_symlink():
            raise ValueError(f"Symlink destination or ancestor refused: {candidate}")
    if path.exists() and not path.is_file():
        raise ValueError(f"Managed file is not a regular file: {path}")
    for ancestor in path.parents:
        if ancestor.exists() and not ancestor.is_dir():
            raise ValueError(f"Parent is not a directory: {ancestor}")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--project", type=Path)
    destination.add_argument("--here", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Replace listed managed files only")
    parser.add_argument("--workflow-only", action="store_true",
                        help="Update only installed .shepherd workflow documents")
    args = parser.parse_args()
    if args.workflow_only and args.force:
        parser.error("--workflow-only cannot be combined with --force")
    pack = Path(__file__).resolve().parent.parent
    target = (Path.cwd() if args.here else args.project).absolute()
    if target.is_symlink():
        parser.error("Symlink project root refused")
    # Normalize OS aliases such as macOS /var before checking managed descendants.
    target = target.resolve()
    if target == pack:
        parser.error("Refusing to install the pack into itself")
    manifest = {}
    if args.workflow_only:
        for source in sorted((pack / "workflow").glob("*.md")):
            manifest[Path(".shepherd") / source.name] = source
        generated = []
    else:
        for source in sorted((pack / "starter").rglob("*")):
            if source.is_file():
                manifest[source.relative_to(pack / "starter")] = source
        for source in sorted((pack / "workflow").glob("*.md")):
            manifest[Path(".shepherd") / source.name] = source
        manifest[Path(".shepherd/LICENSE")] = pack / "LICENSE"
        for name in ("render-ticket-dashboard.py", "source-fingerprint.py", "setup-shepherd.py", "setup-workspace.py",
                     "assignment-report.py", "pane-lifecycle.py", "doctor-shepherd.py"):
            manifest[Path("scripts") / name] = pack / "scripts" / name
        generated = [Path("docs/tickets.md"), Path("docs/tickets.html")]
    try:
        destinations = {relative: checked_destination(target, relative)
                        for relative in [*manifest, *generated]}
        conflicts = [str(p) for p in destinations.values() if p.exists()]
        if conflicts and not args.workflow_only and not args.force:
            raise ValueError("Existing managed files; no writes performed. Use --force explicitly:\n" +
                             "\n".join(conflicts))
        for relative in destinations:
            print(("Would write " if args.dry_run else "Write ") + str(relative))
        if args.dry_run:
            return 0
        for relative, source in manifest.items():
            path = destinations[relative]
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, path)
        if args.workflow_only:
            print("Workflow documents updated; project instructions, tickets, scripts and dashboards were left unchanged.")
        else:
            subprocess.run([sys.executable, str(target / "scripts/render-ticket-dashboard.py"),
                            "--project", str(target)], check=True)
            print("Installed. Run python3 scripts/setup-shepherd.py --project " + str(target))
            print("No harness allocation is accepted until guided setup completes.")
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Install failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
