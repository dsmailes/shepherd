# Bind-and-dispatch procedure

An allocated harness, an idle pane, or a pane merely labeled for a role is not a
binding. Treating any of those as "dispatched" or "running" is the exact mistake
this procedure exists to prevent.

## Sequence

1. **Readiness probe.** The coordinator confirms the candidate's harness, readiness
   and assignment context — ticket, role, attempt, generation, artifact root and
   scope. A harmless identity probe may establish readiness, but must not include
   the work assignment.
2. **Observe and bind.** The coordinator or harness observer establishes a fresh,
   dedicated pane/session for the assigned harness and role, confirms it is distinct
   from every other required worker, and records the exact workspace ID, pane ID,
   harness kind, observed session ID and live state with direct Herdr evidence. The
   sole Admin/board writer serializes role, attempt, target and ownership generation
   in the external manifest before dispatch. Never reuse or relabel another role's
   pane/session.
3. **Dispatch once.** Only after the binding is recorded does the coordinator send
   the work once. Record delivery acknowledgement separately from completion; it
   confirms receipt, not success.
4. **Idle or unassigned panes stay visible, honestly labeled.** A pane that
   exists and is idle, or is merely named to match a role, must keep reporting as
   such until there is an actual binding for it. Tooling must reflect Herdr's own
   observed state, never a guessed or aspirational one.
5. **Reconcile uncertainty; never duplicate-dispatch.** If delivery is uncertain
   (timeout, ambiguous reply, silence), inspect the existing worker/session before
   doing anything else. Record the reconciliation outcome explicitly — confirmed,
   unreachable, or reassigned — before any further action. A guess is not a
   substitute for reconciliation, and reconciliation is not permission to send a
   second dispatch alongside an unconfirmed first one.
6. **Admin/generation handover is explicit.** Exactly one named Admin owns board
   writes at a time. Before a successor Admin (new ownership generation) writes
   anything, the outgoing Admin/generation must go quiescent, and the ticket must
   name both the outgoing and incoming Admin and generation.

## Native identity timing by harness kind

The following is a dated observation, not a runtime guarantee. User/Claude live
evidence from **2026-09-17** reported this baseline, with `antigravity-cli`
`v3`, `agy.toml` `2026.06.24.1`, Codex hook `v8`, and Claude hook `v9`:

- A fresh Claude worker exposed an `agent_session` at pane/session start
  (reported abbreviated value `aa2e0a21-…`).
- A fresh, fully loaded and idle Codex worker exposed no native identity until
  it received a trivial `herdr agent` prompt; the subsequently reported
  abbreviated value was `01a0ae5c-…`.
- Codex and Antigravity may likewise report `Unavailable` before their first
  `herdr agent` prompt. Expected absence at that point alone does not mean the
  worker is blocked or broken.

Runtime or hook updates may change this timing. Keep the observation date and
versions with any later comparison, and never fill in an absent identity or
turn an abbreviated value into a worker identity proof. After the prompt,
reconcile the actual Herdr pane/session fields before proceeding.

Delayed native identity does not establish role independence, pane ownership,
readiness, or authorization to dispatch work. Apply the dedicated-pane,
creating-ticket, observed worker/session binding, quiescence, and safe-cleanup
criteria accepted in **HERDR-010**; if those facts cannot be established, keep
the assignment unbound or blocked and request explicit reassignment as required
by the handoff gates.

For a fresh Codex pane, first confirm it is at the interactive prompt, then send a
harmless identity probe. Once the first prompt has caused Herdr to observe the
session, run `herdr agent list`, `herdr api snapshot`, and
`herdr pane get <pane-id>`. Use the explicit pane/workspace IDs in those direct
views to record the binding before dispatch. For a fresh Claude pane, wait for its
startup `agent_session` and record the same direct pane state. Do not use role-name
matches from the read-only assignment report as authoritative evidence: matching
labels across workspaces can select the wrong pane.

## Completion marker for low-observability workers

Some harnesses have no real Herdr detection rule behind their reported state —
check with `herdr agent explain <pane>`; a `rule: none` with a generic fallback
(e.g. `default_known_agent_idle_fallback`) means `agent_status`/`agent wait` is
not backed by an actual observation and must not be trusted for delivery or
completion, even immediately after a successful `agent start`.

For such a worker, the dispatch itself must specify one exact, single-line
completion marker, scoped to that assignment, that the worker is asked to print
as the very last line of its final message and nothing after it:

```
SHEPHERD-REVIEW-COMPLETE: <ticket> / <role> / <attempt> / Pass|Fail
```

The dispatcher confirms completion only by reading the pane's actual terminal
output (`herdr pane read`) and finding that literal marker — never by trusting
status/wait for a worker with no real detection rule. Including the ticket, role
and attempt in the marker keeps an accidental match against unrelated pane text
effectively impossible. If the marker does not appear within a bounded, disclosed
timeout, treat it as uncertain delivery under the reconciliation rule above:
inspect the pane, do not send a second prompt alongside an unconfirmed first one.

`herdr pane read` line-wraps long output at the pane's rendered width, splitting
the marker across multiple lines with leading indentation on the continuation.
Stripping newlines alone (e.g. `tr -d '\n'`) still leaves that indentation sitting
where the wrap was, producing extra spaces (and sometimes a hyphen split mid-word)
that break an exact-string match even though the marker was genuinely printed.
Normalize whitespace before matching — collapse newlines and runs of spaces to a
single space (e.g. `tr -s ' \n' ' '`) — and match on that normalized text, not on
the raw multi-line read. Confirm a suspected timeout by reading the pane once more
with normalization before concluding delivery is actually uncertain.

This applies to any worker whose `agent explain` shows no real rule, not only
Antigravity; a harness with a genuine detection rule and `agent_session` identity
does not need a marker convention layered on top of Herdr's own observed state.

## Three provenances, never blurred

- **Accepted/config allocation** — what `.shepherd/project.json` records as the
  preferred harness per role. A persisted *preference*, not an identity claim and
  not evidence of readiness.
- **Observed runtime facts** — what Herdr itself reports right now for a pane or
  session (pane id, agent kind, `agent_session`, `agent_status`). Unverified or
  Unavailable whenever not actually observed; never inferred from a label or from
  the accepted allocation.
- **Worker self-reported identity/telemetry** — what a dispatched worker states
  about its own model, effort, and session in its own report. Unavailable for
  anything it cannot itself directly observe, and never copied from another
  party's identity (see `report-template.md`).

## Read-only assignment report

`python3 scripts/assignment-report.py --project .` cross-references the accepted
allocation against observed Herdr pane state, one row per role:

```
Accepted allocation cross-checked against observed Herdr pane state.
Provenance: 'harness' is a persisted config choice; 'pane/agent/session/state' are
live-observed facts reported by Herdr itself, or Unverified/Unavailable when not
independently confirmed.
  Executor: harness=Codex pane=w3:p2 agent=codex session=01a0a5bd-... state=idle
  Reviewer: harness=Claude pane=Unverified agent=Unverified session=Unverified
  state=Unverified (no unique observed pane labeled for this harness)
```

It never writes configuration, tickets, or board projections, and never
dispatches, sends, or launches anything. Outside an actual Herdr environment
(`HERDR_ENV=1` with `herdr` available), or when a role has no uniquely labeled
observed pane, every observed field reports Unverified/Unavailable rather than
guessing. It does not track acknowledgement or completion — those stay in the
ticket's own Reports And Acceptance / Blockers And Corrections history, which
this tool does not infer from pane state and cannot substitute for.
