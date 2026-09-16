"""Read-only source target identity, not a lock or authenticity mechanism."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

# Adapted from dev-team, Copyright (c) 2026 David John Smailes; see ../LICENSE.
class PolicyError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PolicyError(message)


def _git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Git can exit successfully while warning that unreadable paths were omitted.
    require(not result.stderr.strip(), "incomplete-source-manifest")
    return result.stdout


def _walk_error(error):
    raise PolicyError("incomplete-source-manifest") from error


def _manifest(root, snapshot):
    if snapshot:
        paths = []
        for directory, dirs, files in os.walk(root, followlinks=False, onerror=_walk_error):
            parent = Path(directory)
            if parent == root and ".git" in dirs:
                dirs.remove(".git")
            if parent == root and ".git" in files:
                files.remove(".git")
            for name in list(dirs):
                if (parent / name).is_symlink():
                    files.append(name)
                    dirs.remove(name)
            paths.extend((parent / name).relative_to(root).as_posix() for name in files)
        return sorted(paths, key=os.fsencode)
    try:
        top = os.fsdecode(_git(root, "rev-parse", "--show-toplevel")).strip()
        require(Path(top).resolve() == root, "fingerprint-needs-repository-root")
        tracked = _git(root, "ls-files", "--cached", "-z").split(b"\0")
        untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
        require(not _git(root, "ls-files", "--unmerged", "-z"), "unmerged-verification-target")
    except subprocess.CalledProcessError as error:
        raise ValueError("Use --snapshot only for a separately prepared frozen source directory") from error
    return sorted({os.fsdecode(path) for path in tracked + untracked if path}, key=os.fsencode)


def _digest(root, declaration, snapshot):
    digest = hashlib.sha256()
    def add(value):
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
    add(json.dumps(declaration, sort_keys=True).encode("utf-8"))
    exclusions = declaration["excluded_control_paths"]
    paths = [path for path in _manifest(root, snapshot) if path not in exclusions]
    for name in paths:
        path = root / name
        add(os.fsencode(name))
        # Never follow an intermediate directory symlink outside the source tree.
        require(all(not parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents),
                "symlinked-source-directory")
        try:
            info = path.lstat()
        except FileNotFoundError:
            add(b"deleted")
            continue
        add(str(stat.S_IMODE(info.st_mode)).encode("ascii"))
        if stat.S_ISLNK(info.st_mode):
            add(b"link")
            add(os.fsencode(os.readlink(path)))
        else:
            require(stat.S_ISREG(info.st_mode), "unsupported-file-type")
            add(b"file")
            file_hash = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    file_hash.update(chunk)
            add(file_hash.digest())
    return digest.hexdigest()


def fingerprint(root, ticket_id=None, snapshot=False):
    root = Path(root).resolve(strict=True)
    require(root.is_dir(), "invalid-fingerprint-root")
    excluded = []
    if ticket_id is not None:
        require(isinstance(ticket_id, str) and re.fullmatch(r"[A-Z][A-Z0-9]*-[0-9]+", ticket_id),
                "invalid-ticket-id")
        excluded = [".tickets/" + ticket_id + ".md", ".tickets/queue.md",
                    "docs/tickets.html", "docs/tickets.md"]
    declaration = {
        "manifest": "prepared-source-snapshot-v1" if snapshot else "git-tracked-and-nonignored-untracked-v1",
        "excluded_control_paths": excluded,
    }
    first = _digest(root, declaration, snapshot)
    require(first == _digest(root, declaration, snapshot), "moving-verification-target")
    return dict(declaration, kind="content-sha256", value=first)


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".")
    parser.add_argument("--ticket")
    parser.add_argument("--snapshot", action="store_true",
                        help="Use only for a separately prepared frozen source directory")
    args = parser.parse_args()
    try:
        print(json.dumps(fingerprint(args.project, args.ticket, args.snapshot), indent=2))
        return 0
    except (ValueError, OSError) as error:
        parser.exit(1, f"Fingerprint failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
