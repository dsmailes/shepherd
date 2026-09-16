# Project workflow

Use `.shepherd/responsibilities.md`, `.shepherd/roles.md`, `.shepherd/runbook.md`,
`.shepherd/herdr.md` and `.shepherd/handoffs.md` for nontrivial work.
Confirm the editable harness map, one coordinator and one Admin/sole board writer.
Activate optional Designer, Sounding Board and Critical Friend per ticket or record
None; they do not replace review/testing. Required design finishes before Ready.
Each harness chooses from its available models; report observed choices honestly.
Architect orchestrates only; independent Executor, Reviewer and Tester sessions
are required. Do not silently fall back when a harness or worker is unavailable.
Execute Ready tickets only. One named writer owns `.tickets/*.md`, queue and
regeneration of `docs/tickets.md` and `docs/tickets.html`, then validates. Admin
records an authorized non-Architect acceptor's decision; Tester Pass is distinct
from acceptance. Use compact tickets/reports linking shared external bindings;
coordinator-observed identity is separate from worker-unseen telemetry (Unavailable).
Dispatch once and distinguish delivery acknowledgement from completion monitoring.
Keep reports/artifacts outside frozen source and keep
`.memory/` for durable knowledge. No commits/pushes are implied by this workflow.

Run guided setup in `setup.md` (installed: `.shepherd/setup.md`) first.
The accepted `.shepherd/project.json` is the ownership source of truth. The
Markdown example never substitutes for a user-reviewed accessible roster.
