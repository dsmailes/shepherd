# Portable handoffs and frozen targets

## Identify source

Reports and test/build output go to the ticket's named repository-external artifact
root. Freeze source by stopping writers; the fingerprint tool does not acquire a
lock. Record the source revision or relevant changed-file scope actually inspected
or tested. An authorized immutable scoped commit is preferred; a content
fingerprint is optional supporting provenance when commits are not authorized:

```sh
python3 scripts/source-fingerprint.py --project /path/to/project --ticket TASK-001
```

Run from an actual Git repository root. The manifest covers tracked and nonignored
untracked paths, file modes, symlink text and tracked deletions, rejects unmerged
entries and compares two successive reads. Git-ignored untracked files are outside
this mode: inspect ignore rules and ensure required source is included. A tracked
ignored file remains included. Store the JSON output in the external artifact root.
For a separately prepared frozen source directory without Git, use `--snapshot`;
this covers all files, including ignored files, except root `.git` administration.
Do not use snapshot mode to disguise an actively changing project directory.

With `--ticket TASK-001`, the **only control exclusions** are:

- `.tickets/TASK-001.md`
- `.tickets/queue.md`
- `docs/tickets.md`
- `docs/tickets.html`

No wildcard ticket, memory, plan, configuration or report exclusions exist. Omitting
`--ticket` excludes no control paths. Capture the declaration when a fingerprint
is used, but do not make a whole-repository hash an approval gate. Generated or
local metadata can change without changing the code under review. Reviewer and
Tester report the revision or relevant changed-file diff they actually inspected,
along with findings and test results. If source changes during review or testing,
identify the changed files and rerun only the affected check. A fingerprint
mismatch alone is not a code defect, does not block review or testing, and does
not justify creating another source copy or worktree solely to reconcile hashes.
Read the excluded active ticket independently; acceptance or scope changes still
invalidate approval even when the source hash is unchanged.

Pane ownership is part of the handoff evidence: record the stable pane ID, role,
creating ticket, ownership provenance (`ticket-created`), observed worker/session
binding, and whether the pane is a role or read-only board pane. Cleanup order is
completion marker → evidence capture → Admin recording → observed quiescence →
read-only close plan → per-pane recheck and close. Missing provenance, unrelated
or existing panes, board panes, blocked diagnostics, and any partial failure are
preserved.

## Transition gates

| Transition | Required evidence |
| --- | --- |
| Backlog → Ready (optionally through Design) | Complete scope, acceptance, risks, skills, checks, capability and source-ownership contract; required design |
| Ready → In Progress | Independent Executor observed and assignment acknowledged |
| In Progress → Review | Executor report, focused checks, stable target, no active source writer |
| Review → Test | Independent Reviewer Pass on the inspected revision or relevant changed-file scope, findings resolved |
| Test → Done | Independent Tester Pass; required integration/full validation; reported source scope; explicit authorized acceptance by non-Architect acceptor |
| Any active state → Blocked | Concrete reason, preserved artifacts, owner and resume condition |
| Review/Test → In Progress | Actionable failure routed to Executor; old approvals invalidated |

Board writer applies transitions and queue updates serially; every role supplies
its own concise report using `report-template.md`, linking the shared external
assignment manifest. Coordinator-observed bindings establish independence; unseen
worker-self-visible identity/model telemetry is Unavailable and does not require
copying another session's ID. Admin records acceptance from the authorized acceptor,
regenerates projections and validates. Record any authorized gate waiver with
who, why and remaining risk; role independence and truthful evidence are never
waived or silently downgraded. A missing independent session blocks the gate.
Resuming Blocked requires rechecking the original destination gate.

These are portable procedures, not enforced runner evidence. The dashboard checks
board consistency only. Content hashes detect target changes, not report authorship
or authorization. Never fabricate session IDs, commit SHAs or signed/runtime proof.
