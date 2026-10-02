# Evidence verification

`scripts/verify-evidence.py` is a read-only deterministic check over external
Executor and Tester evidence. It never edits the project, launches an agent or
sends pane input. It prints one `PASS`, `FAIL` or `INFO` row per check and a
`RESULT` line. Exit `0` means no failed checks, `1` means a failed check and `2`
means invalid usage or an unavailable environment.

Create `.shepherd/verify.json` when the project needs patterns or paths beyond
the built-in portable defaults:

```json
{
  "build_pass": ["BUILD OK"],
  "build_fail": ["BUILD FAILED"],
  "test_pass": ["TESTS PASSED"],
  "test_fail": ["TESTS FAILED"],
  "test_count": ["Ran [0-9]+ tests"],
  "silent_failure": ["\\btry\\?\\b", "catch\\s*\\{\\s*\\}"],
  "duplicate_warning": ["implemented in both"],
  "source_prefixes": ["src/", "tests/"],
  "coordinator_prefixes": [".memory/", "scripts/", ".shepherd/"],
  "protected_files": ["src/schema.json"],
  "snapshot_paths": ["snapshots/"],
  "source_extensions": [".py", ".js"]
}
```

Use it on evidence stored outside the source tree:

```sh
python3 scripts/verify-evidence.py verify-executor \
  --project . --ticket TASK-NNN \
  --build-log /external/TASK-NNN/build.log \
  --test-log /external/TASK-NNN/focused.log
python3 scripts/verify-evidence.py verify-tester \
  --project . --ticket TASK-NNN \
  --build-log /external/TASK-NNN/build.log \
  --test-log /external/TASK-NNN/full.log \
  --rerun affected=/external/TASK-NNN/rerun.log
```

An expected fingerprint is informational by default. Add `--frozen` only when
the command is checking an explicitly frozen target. A zero-test count fails,
even when the tool reports a successful command. `codex-report` is an optional,
weaker coordinator-correlated fallback for a missing native session identity; it
is never Herdr identity or independence evidence and requires explicit approval.
