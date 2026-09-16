# Responsibilities and harness-local model choice

## Editable example

| Responsibility | Owning harness | Required worker |
| --- | --- | --- |
| Architecture and coordination | Codex | Architect, orchestration only |
| Implementation | Codex | Executor, separate from Architect |
| Design | Claude | Designer when required by ticket |
| Explore options | Explicit assignment only | Optional Sounding Board |
| Challenge an approach | Explicit assignment only | Optional Critical Friend |
| Review | Claude | Reviewer, independent of Executor |
| Testing | Antigravity | Tester, independent of Executor and Reviewer |
| Admin / ticket-board ownership | Antigravity | One named board writer |

Before use, replace or confirm this example with the user's assignments. Record
one coordinator identity and one board writer identity here or in the ticket.
The named writer is the only session that mutates tickets, queue and projections;
other roles submit proposals/reports. Owning testing and board work in the same
harness is allowed, but test verdict and board acceptance are separate actions.
The Architect cannot accept its own orchestration work as Done.
Admin records another authorized acceptor's decision; it has no technical
acceptance authority merely from board ownership. Select optional help per ticket,
not automatically from allocated owners. A dedicated Admin may use a cheaper
capable model through the same harness-local selection contract below.

## Supervisor versus worker

A harness supervisor receives assignments and selects an available model/effort
using its native capabilities. It creates or selects a separately identifiable
role worker. Multiple roles may share a harness; Architect, Executor, Reviewer
and Tester must use distinct observed worker sessions/tasks. A pane is a transport
address, not proof of independence. Changing a role label in one session is not a
new worker. Native child tasks are valid when they expose independent identities.
When native child delegation is absent, a fresh Herdr session of the assigned
harness is valid if its independent worker identity is observed. If those identities
or the required role capability cannot be established, block
and request explicit reassignment; do not pretend delegation occurred.

The coordinator or harness observer records the observed worker binding and its
evidence once in the ticket's external assignment manifest. Keep assignment labels,
supervisor lineage, runtime worker identity and transport address distinct; invented
labels and copied parent IDs are not runtime proof. Brief each worker with its own
manifest entry. Workers report only self-visible telemetry, defaulting unseen fields
to `Unavailable`, and flag mismatches. A linked coordinator observation can establish
separation when workers cannot see their own IDs; no observed independent identity
still blocks dispatch. These observations are not authenticated signatures.

## Selection contract

The owning harness discovers its own supported models, efforts and native
delegation API. Choose using task complexity, risk, required tools, context,
project cost/privacy limits and observed availability. Do not infer ownership from
model names. Do not request hidden model switches or prescribe another harness's
model catalog. If switching is unsupported, report the actual inherited model
when observable; otherwise write `Unavailable`. Treat effort and token usage the
same way. Record the reason for the selection, supported activation mechanism,
and observed outcome. A requested model is not proof of activation.

Project constraints: record budget, permitted providers, network/data restrictions
and required tools before dispatch; use existing project constraints when present.
Unavailable harness: stop that assignment and obtain explicit user/coordinator
reassignment consistent with user constraints. Never silently fall back.

Run guided setup in `setup.md` (installed: `.shepherd/setup.md`) first.
The accepted `.shepherd/project.json` is the ownership source of truth. The
Markdown example never substitutes for a user-reviewed accessible roster.

Record observed model/effort changes in every attempt report with the reason.
Unavailable telemetry and provider/runtime updates limit exact reproduction;
a fixed model catalog is neither required nor a guarantee of reproducibility.
