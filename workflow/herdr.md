# Herdr coordination preflight

Shepherd is optimized for Herdr transport but supplies no runtime controller.
CLI details vary: use the installed help as the authority, never guessed flags.

## Discover without dispatch

After accepted project setup, run `python3 scripts/doctor-shepherd.py --project .`
for read-only machine/caller checks. Read `doctor.md`; a successful result still
leaves authentication, task capabilities and independent workers Unverified.

```sh
printf '%s\n' "${HERDR_ENV:-unset}"
command -v herdr
herdr --version
herdr --help
herdr --skill
herdr agent --help
herdr pane --help
```

Live control requires `HERDR_ENV=1` in the actual coordinator environment and a
reachable local workspace/API. Do not set the variable just to bypass this gate.
Outside Herdr, read/plan locally; block live coordination or use an explicitly
agreed manual independent-session workflow with its limitations disclosed.
Read the installed built-in skill before control and inspect command-group help
before using any subcommand. This pack deliberately ships no guessed launch or
prompt commands. Discovery above does not launch agents.

## Bind before sending

- Inspect live workspace, pane and agent state using commands discovered locally.
  Use explicit stable pane/agent IDs or verified unique live names, not implicit
  focus, index assumptions, guessed IDs or remembered sessions.
- Record the original workspace, pane cwd, layout and focus. Match the ticket's
  project/checkout and external artifact root before sending anything. Preserve
  cwd/layout/focus; only alter these with task authorization and restore incidental
  focus changes. Do not use the current dev pane as an unverified worker.
- Check supported harness kinds, executable availability, requested tool access,
  native model/delegation controls and independent session identity. Do not assume
  Antigravity is installed, controllable by Herdr, or exposes a delegation API.
  If unsupported, report Unavailable and stop this assignment. Manual operation or
  another harness needs explicit reassignment, not an automatic fallback.
- Establish the addressed agent's verified readiness from current runtime evidence;
  do not require another exchange when that suffices. A shell prompt, pane creation
  success or absence of output is insufficient. Inspect starting, idle/ready,
  working, blocked, error and exited states as exposed by the installed runtime.
  Never inject work into a busy or blocked session. Investigate its actual reason.
- Exactly one coordinator dispatches once. Link the worker's own external manifest
  entry: ticket, role, attempt, generation, target and observed binding. Record the
  delivery acknowledgement separately from completion; it confirms receipt, not
  success. Unknown delivery requires reconciliation, never duplicate dispatch.
- Monitor the existing task at sensible intervals with visible progress and a
  bounded task-appropriate overall deadline. A short observation timeout while an
  acknowledged task is working does not make delivery ambiguous. At a deadline or
  loss of status, inspect the existing task, acknowledgement and report before any
  retry; never start overlapping mutable work. On blocked/exited workers,
  preserve output, report the resume condition and ask the coordinator for explicit
  reassignment where needed. Do not repeatedly send prompts, invent readiness or
  start substitute agents without checking existing execution.

Herdr pane identity routes messages. Independent native worker/session identity
establishes role separation. Coordinator/harness observers record both and the
observation evidence once, separating supervisor lineage from worker identity.
Workers link that binding and default unseen self-telemetry to Unavailable. Never
copy the supervisor's ID into the worker field. If no responsible observer can
establish runtime identity, independence stays blocked; an invented label is not proof.
Neither is an authenticated report signature. Do not claim model activation,
completed tests or integration from status indicators alone.
