#!/usr/bin/env python3
"""Run deterministic, read-only checks over Executor and Tester evidence."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

PASS, FAIL, INFO = "PASS", "FAIL", "INFO"
DEFAULT_PROFILE = {
    "build_pass": [r"\*\* BUILD SUCCEEDED \*\*"],
    "build_fail": [r"\*\* BUILD FAILED \*\*"],
    "test_pass": [r"\*\* TEST SUCCEEDED \*\*"],
    "test_fail": [r"\*\* TEST FAILED \*\*"],
    "test_count": [r"passed on ", r"Executed\s+\d+\s+tests?", r"Test Case .* passed"],
    "silent_failure": [r"\btry\?\b", r"catch\s*\{\s*\}"],
    "duplicate_warning": [r"is implemented in both"],
    "source_prefixes": [],
    "coordinator_prefixes": [".memory/", "scripts/", ".shepherd/"],
    "protected_files": [],
    "snapshot_paths": [],
    "source_extensions": [".py", ".swift", ".m", ".mm", ".js", ".ts", ".java", ".kt", ".rs", ".go"],
}


class Report:
    def __init__(self):
        self.rows = []

    def add(self, status, name, detail=""):
        self.rows.append((status, name, detail))

    def finish(self):
        width = max([len(row[1]) for row in self.rows] + [10])
        for status, name, detail in self.rows:
            print(f"{status:<4}  {name:<{width}}  {detail}")
        failures = sum(status == FAIL for status, _, _ in self.rows)
        print("-" * 60)
        print(f"RESULT: {'FAIL' if failures else 'PASS'} ({len(self.rows)} check(s), {failures} failed)")
        return 1 if failures else 0


def run(command, cwd=None):
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def profile_for(project, explicit=None):
    path = Path(explicit) if explicit else Path(project) / ".shepherd/verify.json"
    profile = dict(DEFAULT_PROFILE)
    if not path.exists():
        return profile, None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read verification profile {path}: {error}") from error
    if not isinstance(loaded, dict):
        raise ValueError(f"Verification profile must be a JSON object: {path}")
    for key, value in loaded.items():
        if key not in DEFAULT_PROFILE:
            raise ValueError(f"Unknown verification profile key: {key}")
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"Verification profile key {key} must be a list of strings")
        profile[key] = value
    return profile, path


def matches_any(text, patterns):
    for pattern in patterns:
        try:
            if re.search(pattern, text, re.MULTILINE):
                return True
        except re.error as error:
            raise ValueError(f"Invalid verification regex {pattern!r}: {error}") from error
    return False


def fingerprint(project, ticket):
    script = Path(project) / "scripts/source-fingerprint.py"
    result = run([sys.executable, str(script), "--project", str(project), "--ticket", ticket])
    if result.returncode:
        return None, result.stderr.strip() or result.stdout.strip()
    try:
        return json.loads(result.stdout)["value"], ""
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        return None, f"unparseable fingerprint output: {error}"


def check_fingerprint(report, project, ticket, expected, frozen):
    value, problem = fingerprint(project, ticket)
    if value is None:
        report.add(FAIL, "fingerprint", problem)
    elif expected and value != expected:
        report.add(FAIL if frozen else INFO, "fingerprint",
                   f"{value[:12]} != expected {expected[:12]}" + (" (frozen target)" if frozen else " (target may have changed)"))
    elif expected:
        report.add(PASS, "fingerprint", value[:12] + " matches expected")
    else:
        report.add(INFO, "fingerprint", value)
    return value


def check_build_log(report, path, profile, label):
    text = read(path) if path else None
    if text is None:
        report.add(FAIL, label, f"missing: {path}")
        return
    build_ok = matches_any(text, profile["build_pass"])
    build_bad = matches_any(text, profile["build_fail"])
    report.add(PASS if build_ok and not build_bad else FAIL, label,
               "pass pattern found" if build_ok and not build_bad else "missing pass pattern or failure pattern found")


def check_test_log(report, path, profile, label):
    text = read(path) if path else None
    if text is None:
        report.add(FAIL, label, f"missing: {path}")
        return
    test_ok = matches_any(text, profile["test_pass"])
    test_bad = matches_any(text, profile["test_fail"])
    report.add(PASS if test_ok and not test_bad else FAIL, label + " result",
               "pass pattern found" if test_ok and not test_bad else "missing pass pattern or failure pattern found")
    count = sum(len(re.findall(pattern, text, re.MULTILINE)) for pattern in profile["test_count"])
    report.add(PASS if count else FAIL, label + " tests ran", f"{count} count match(es); zero means the filter may have matched nothing")
    duplicate = sum(len(re.findall(pattern, text, re.MULTILINE)) for pattern in profile["duplicate_warning"])
    report.add(PASS if not duplicate else FAIL, label + " duplicate warnings", str(duplicate))
    report.add(INFO, label + " profile", "configured patterns applied")


def changed_paths(project):
    result = run(["git", "-C", str(project), "status", "--porcelain", "-uall"])
    if result.returncode:
        raise ValueError(result.stderr.strip() or "git status failed")
    paths = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append((line[:2], path.strip('"')))
    return paths


def control_path(path, ticket):
    return path in {f".tickets/{ticket}.md", ".tickets/queue.md", "docs/tickets.md", "docs/tickets.html"}


def check_scope(report, project, ticket, profile, allowed):
    paths = changed_paths(project)
    prefixes = allowed or profile["source_prefixes"]
    if not prefixes:
        report.add(INFO, "changed-file scope", "no allowed source prefixes configured")
        return paths
    outside = []
    for _, path in paths:
        if control_path(path, ticket) or any(path.startswith(prefix) for prefix in profile["coordinator_prefixes"]):
            continue
        if prefixes and not any(path.startswith(prefix) for prefix in prefixes):
            outside.append(path)
    report.add(PASS if not outside else FAIL, "changed-file scope",
               f"{len(paths)} changed path(s)" if not outside else "outside scope: " + ", ".join(outside[:8]))
    return paths


def scan_source(report, project, paths, profile):
    hits = []
    extensions = set(profile["source_extensions"])
    for _, relative in paths:
        if Path(relative).suffix not in extensions:
            continue
        text = read(Path(project) / relative)
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for pattern in profile["silent_failure"]:
                if matches_any(line.split("//", 1)[0], [pattern]):
                    hits.append(f"{relative}:{number}")
                    break
    report.add(PASS if not hits else FAIL, "silent-failure scan", "none" if not hits else "; ".join(hits[:8]))


def check_protected(report, project, base, files):
    if not files:
        report.add(INFO, "protected files", "none configured")
        return
    if not base:
        report.add(INFO, "protected files", "no --base supplied")
        return
    result = run(["git", "-C", str(project), "diff", "--quiet", base, "--", *files])
    report.add(PASS if result.returncode == 0 else FAIL, "protected files", "unchanged" if result.returncode == 0 else "changed: " + ", ".join(files))


def check_snapshots(report, project, prefixes):
    if not prefixes:
        report.add(INFO, "snapshot/golden files", "none configured")
        return
    paths = changed_paths(project)
    modified = [path for status, path in paths if any(path.startswith(prefix) for prefix in prefixes) and status.strip()]
    report.add(PASS if not modified else FAIL, "snapshot/golden files", "none changed" if not modified else ", ".join(modified[:8]))


def verify(args, tester=False):
    profile, profile_path = profile_for(args.project, args.profile)
    report = Report()
    check_fingerprint(report, args.project, args.ticket, args.expect_fingerprint, args.frozen)
    label = "tester" if tester else "executor"
    check_build_log(report, args.build_log, profile, label + " build")
    check_test_log(report, args.test_log, profile, label + " test")
    if getattr(args, "rerun", None):
        for spec in args.rerun:
            name, separator, path = spec.partition("=")
            if not separator or not name or not path:
                raise ValueError("--rerun values must be name=log-path")
            check_test_log(report, path, profile, "rerun " + name)
    paths = check_scope(report, args.project, args.ticket, profile, args.allowed)
    if not tester:
        scan_source(report, args.project, paths, profile)
    check_protected(report, args.project, args.base, profile["protected_files"] + args.unchanged)
    check_snapshots(report, args.project, profile["snapshot_paths"])
    if profile_path:
        report.add(INFO, "verification profile", str(profile_path))
    return report.finish()


def sessions(root):
    return sorted(Path(os.path.expanduser(root)).glob("**/rollout-*.jsonl"))


def find_sessions(root, token=None, session_id=None):
    found = []
    for path in sessions(root):
        if session_id and session_id in path.name:
            found.append(path)
        elif token and token in (read(path) or ""):
            found.append(path)
    return found


def last_assistant_message(path):
    last = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = obj.get("payload", {})
        if payload.get("type") == "message" and payload.get("role") == "assistant":
            last = "".join(part.get("text", "") for part in payload.get("content", []) if isinstance(part, dict))
    return last or ""


def codex_report(args):
    deadline = time.time() + args.timeout
    while True:
        found = find_sessions(args.sessions, args.token, args.session_id)
        if len(found) > 1:
            raise ValueError(f"ambiguous session evidence: {len(found)} logs match")
        if found:
            message = last_assistant_message(found[0])
            if args.out:
                output = Path(args.out)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    "<!-- Coordinator-correlated session evidence; NOT Herdr-observed identity. -->\n\n" + message + "\n",
                    encoding="utf-8",
                )
            marker_ok = not args.marker or re.search(args.marker, message, re.MULTILINE)
            print(f"INFO  session log  {found[0]}")
            print("INFO  identity      coordinator-correlated, NOT Herdr-observed")
            print(f"RESULT: {'PASS' if marker_ok else 'FAIL'} (optional fallback only)")
            return 0 if marker_ok else 1
        if not args.timeout:
            raise ValueError("no session log contains the supplied token or session id")
        if time.time() >= deadline:
            raise TimeoutError("timed out waiting for a matching session log")
        time.sleep(args.interval)


def wait_for(args):
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        present = not args.file or (read(args.file) is not None and (not args.contains or args.contains in read(args.file)))
        status = None
        if args.pane:
            result = run([args.herdr, "pane", "get", args.pane])
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or "Herdr pane status failed")
            try:
                status = json.loads(result.stdout).get("result", {}).get("pane", {}).get("agent_status")
            except json.JSONDecodeError as error:
                raise ValueError("Herdr pane status was not JSON") from error
        if present and (not args.pane or status not in {"working", "starting"}):
            print(f"PASS  readiness  file={args.file or 'none'} status={status or 'not-requested'}")
            print("RESULT: PASS (1 check(s), 0 failed)")
            return 0
        time.sleep(args.interval)
    print(f"FAIL  readiness  file={args.file or 'none'} status={status or 'not-requested'}")
    print("RESULT: FAIL (1 check(s), 1 failed)")
    return 1


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)

    def common(command):
        command.add_argument("--project", default=".")
        command.add_argument("--ticket", required=True)
        command.add_argument("--profile")
        command.add_argument("--expect-fingerprint")
        command.add_argument("--frozen", action="store_true", help="Treat fingerprint mismatch as a blocking failure")
        command.add_argument("--base")
        command.add_argument("--unchanged", nargs="*", default=[])
        command.add_argument("--build-log", required=True)
        command.add_argument("--test-log", required=True)
        command.add_argument("--allowed", nargs="*", default=[])

    executor = sub.add_parser("verify-executor")
    common(executor)
    executor.set_defaults(handler=lambda args: verify(args, False))
    tester = sub.add_parser("verify-tester")
    common(tester)
    tester.add_argument("--rerun", nargs="*", default=[])
    tester.set_defaults(handler=lambda args: verify(args, True))

    waiting = sub.add_parser("wait")
    waiting.add_argument("--file")
    waiting.add_argument("--contains")
    waiting.add_argument("--pane")
    waiting.add_argument("--herdr", default="herdr")
    waiting.add_argument("--timeout", type=int, default=600)
    waiting.add_argument("--interval", type=int, default=10)
    waiting.set_defaults(handler=wait_for)

    report = sub.add_parser("codex-report")
    report.add_argument("--token")
    report.add_argument("--session-id")
    report.add_argument("--sessions", default="~/.codex/sessions")
    report.add_argument("--out")
    report.add_argument("--marker")
    report.add_argument("--timeout", type=int, default=0)
    report.add_argument("--interval", type=int, default=10)
    report.set_defaults(handler=codex_report)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    if hasattr(args, "project"):
        args.project = os.path.abspath(args.project)
    try:
        return args.handler(args)
    except (OSError, ValueError, TimeoutError, subprocess.TimeoutExpired) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
