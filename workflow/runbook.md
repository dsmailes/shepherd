# Runbook

1. **Inspect.** Read project instructions, memory and live tickets. Confirm the
   editable responsibility map, coordinator and sole board writer. The board
   writer scans `.tickets/*.md` for the next unused numeric ID, including completed
   tickets. Tiny questions/typos may skip tickets; nontrivial work uses them.
2. **Prepare.** Architect proposes problem, scope, acceptance, risks, skill context,
   verification and role assignment. Record optional Designer, Sounding Board and
   Critical Friend help or None, with adopted findings. Admin creates the ticket and
   queue entry. Required design completes before Ready. Resolve blocking scope
   decisions and capabilities before moving to Ready.
3. **Preflight.** Follow `herdr.md` and `binding.md`. Give each required role a
   fresh dedicated pane of its assigned harness; never reuse another role's pane or
   session. Before dispatch, confirm the exact workspace ID, pane ID, harness kind,
   observed session ID and state from direct Herdr evidence. Record that binding and
   its evidence in the external assignment manifest before the coordinator sends
   work. The sole board writer serializes the assignment/generation; a missing
   assigned harness or independent worker blocks dispatch until explicit
   reassignment. Where native child delegation is absent, use a fresh observed
   session of the assigned harness if supported; never relabel an existing worker.
4. **Own source.** Classify read-only versus mutating/building. Choose isolated
   ticket branch/worktree when supported and commits are authorized, otherwise
   serialize mutable work. Use one external project/ticket artifact root for
   Executor, Reviewer, Tester and all retries. Name the exclusive owner. Avoid
   concurrent source edits during checks. Platform-specific leases are optional
   and only held around actually contended commands.
5. **Execute.** The board writer moves Ready to In Progress when the Executor
   starts. Executor implements, runs focused checks and writes an external report.
   No automatic commits or pushes. Freeze one target under `handoffs.md`; the board
   writer moves to Review after the implementation gate passes.
6. **Review and verify.** Coordinator dispatches independent Reviewer, then Tester
   only after Review Pass. The board writer moves Review to Test. Failed work
   returns to In Progress through the writer; fix with Executor and invalidate old
   review/test approval when source changes. Reuse the artifact root. Limit to two
   correction rounds; stop earlier for unchanged repeated failure or missing
   capability. Preserve diagnostics and record Blocked with the resume condition.
7. **Integrate.** With isolated ticket commits, integrate only reviewed commits and
   run one full required matrix on the resulting integration commit. Record both
   ticket and integration targets. Serialized single-target work can mark a
   separate merge batch not applicable with rationale, but must run the required
   full project validation on the final target. New source changes require fresh
   review and tests. Failed integration blocks acceptance.
8. **Accept.** Admin checks the complete independent review/test chain, each
   report's inspected source scope, integration evidence and the project's
   user/delegated acceptance authority.
   Record another authorized acceptor's explicit decision before Done; Admin cannot
   grant itself authority. Tester Pass is insufficient. Architect may not accept its
   own work. Regenerate both projections, then validate; reconcile any failure.
   Capture evidence before cleaning only named disposable worktrees/artifacts;
   retain failed/blocked artifacts. Write durable findings to `.memory/` only.

9. **Clean up owned panes.** After Admin records completion, capture the final
   report/fingerprint and confirm the worker/session is quiescent. Generate the
   read-only close plan with `scripts/pane-lifecycle.py`; close only role panes
   whose observed `creating_ticket` exactly matches the ticket and whose
   ownership is `ticket-created`. Recheck each pane ID immediately before a
   close. Keep ticket/role board panes until Done. On any uncertainty or partial
   failure, stop, preserve diagnostics and reconcile; never retry blindly.

Only `.tickets/*.md` plus `.tickets/queue.md` hold live state. Keep `## State` to one
exact lifecycle token; put explanations in other sections. When a board update
cannot finish, stop other writes, reconcile ticket and queue, regenerate and
validate. Dashboard generation is not a state transition or a gate validator.

Run guided setup in `setup.md` (installed: `.shepherd/setup.md`) first.
The accepted `.shepherd/project.json` is the ownership source of truth. The
Markdown example never substitutes for a user-reviewed accessible roster.


## Ambiguous attempts and board-owner recovery

Before dispatch, the board writer serializes the ticket, attempt, role, assigned
worker/session and ownership generation binding. One coordinator sends the work
only after that binding exists. Reject conflicting simultaneous role claims.
An old assignment/attempt result cannot satisfy a current gate.

A delivery timeout without acknowledgement makes delivery **ambiguous**, not failed.
Once acknowledged, a short observation window ending while the worker is working
is ordinary monitoring, not ambiguous delivery. Use a task-appropriate overall
deadline and periodic progress; if execution becomes uncertain, reconcile existing
status, acknowledgement and report state within a bounded interval. Never resend
or grant a new mutable source owner until the prior writer is confirmed stopped/
quiescent or safely isolated without access to the new target.
Marking an attempt superseded does not stop its process or revoke filesystem access.
Keep late reports labeled with their original attempt and `superseded` status;
do not accept them or silently discard them. If safety cannot be established,
remain Blocked and retain all logs.

If the board writer crashes or is unreachable, pause all board mutations. Only
the user or a previously authorized coordinator may explicitly hand over ownership.
Record old/new owner identities, reason and a new ownership generation. Require
prior-owner acknowledgement or confirmed quiescence before another writer starts.
If neither is possible, remain Blocked. The new writer reconciles the live tickets
and queue, frozen source target, all active/ambiguous attempts and role/session
history before resuming. Reconfiguration alone is not a handover.

Generation and attempt IDs are cooperative metadata, not authenticated fencing.
Shepherd supplies no atomic runtime lock, quorum or protection against a dishonest
worker. A relayed report and matching source hash do not prove commands ran.
Require independent source inspection and fresh tests with retained outputs;
record the limits of unauthenticated evidence instead of claiming stronger proof.


## Proportional work and short handoffs

Default to one Execute → Review → Test chain. Review changed scope and run affected
checks; run the full required matrix once at final integration. Repeat broader
checks only for new failures, changes or unresolved risk. Only actionable correctness,
security or acceptance blockers return work to Executor; record style and other
nonblocking observations without bouncing the ticket.

Use the compact default ticket (about 300–500 words for small work) and role report
(150–300 words), expanding for material risk. Keep shared bindings, source/verification
contract and linked logs once in the external manifest. Each report supplies its
verdict, result, target/checks, risks and next gate; acceptance can be a short entry
linking that same evidence. No separate readiness exchange is needed when current
runtime observations already establish readiness. Do not relitigate disclosed,
accepted portable limitations or identity provenance beyond
the checks needed for independence and truthful evidence. Allow at most two
correction rounds; stop earlier on unchanged failure or no new evidence. Report
observed token usage when exposed, otherwise elapsed time and round count; never
invent usage or enforcement. The coordinator chooses proportional verification and
ends out-of-scope discussion without waiving role independence or required gates.
