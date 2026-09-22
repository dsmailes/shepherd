# Guided setup

Do this before dispatch. The responsibility table is an illustration; there is no
accepted default assignment. Installed agents should explicitly read these files;
Shepherd does not claim any Antigravity instruction auto-discovery convention.

```sh
python3 scripts/setup-shepherd.py --project .
```

To inspect an already accepted allocation without rerunning setup, use
`python3 scripts/setup-shepherd.py --project . --show`. This reads
`.shepherd/project.json`, prints every canonical role (including optional roles
as Unassigned when absent), and makes no changes. It reports persisted harness
choices only; it does not identify live workers or sessions, probe runtimes, or
establish readiness. `--show` cannot be combined with setup options.

Interactive setup asks which harnesses/agents the user can access, optional tools
and limits, role strengths, and optional explicit launcher/Herdr kind mappings. It shows the suggested map, permits role overrides,
then asks for acceptance before writing `.shepherd/project.json`.

For automation, declare the roster explicitly. Omit `--accept` to preview without
writing. Names are user-defined, case-sensitive for references and unique without
regard to case; they are not a fixed catalog of models or supported runtimes.

```sh
python3 scripts/setup-shepherd.py --project . --harness Codex --harness Claude --harness Antigravity
python3 scripts/setup-shepherd.py --project . --harness MyAgent --harness OtherAgent --strength review=MyAgent --assign admin=OtherAgent --assign sounding-board=MyAgent --assign critical-friend=OtherAgent --accept
```

`--strength role=harness` contributes a user's declared aptitude to the suggestion;
`--assign role=harness` takes precedence as an explicit role preference. Both may
be repeated and may reference only the accessible roster. For repeated declarations
of a role, the last wins after alias normalization; all `--assign` declarations take
precedence over all `--strength` declarations. Core roles: architecture,
implementation, review, testing, board (Admin). Optional roles: design,
sounding_board, critical_friend. Input aliases: admin → board, sounding-board →
sounding_board, critical-friend → critical_friend. JSON stores only canonical keys,
retaining schema_version 1 and board_writer_role=board for existing installations.
`--preferences` records free-text constraints for agent-led advice;
the deterministic helper does not infer capabilities from prose or vendor names.

Without declared strengths, roster order supplies a transparent starting point:
first harness for architecture/implementation, second (if present) for design/review,
third (if present) for testing/board, otherwise first for testing/board. Extra
harnesses stay available for explicit assignments. This is not a measured ranking.
A single harness can own all responsibilities through distinct role sessions.
New advisers are omitted unless explicitly assigned via `--strength` or `--assign`.
The existing design owner suggestion remains compatible, but allocation never
activates optional work: each ticket records selected help or None. Required design
completes before Ready. No new adviser is silently assigned to old configurations.

## Agent-led advice before acceptance

Ask which harnesses are accessible and what they can actually do: native delegation
or fresh independent sessions, design/browser tools, repository and shell/test
access, platform integration, usage limits and privacy/cost constraints. Use known
strengths and user preferences to suggest responsibilities and explain tradeoffs.
An agent with design tools may fit design/review; one with the necessary platform
and shell may fit testing. Do not assign a role requiring known-missing tools.
If the needed ability is unknown, preserve `Unverified` and block dispatch until
capability preflight observes it. Roster membership alone never establishes readiness.

Review the complete proposed map with the user before saving. The helper can
capture this through explicit `--strength`/`--assign` flags after consultation.
Persisted JSON is the accepted ownership source of truth; Markdown describes the
contracts and example only. The helper's acceptance confirms the allocation, not
role capability, worker identity, readiness or permission to run commands.
Each owning harness still selects its own available model and reports its choice.
Admin can use the least-cost capable model its harness exposes, including a
dedicated worker where useful. It must reliably update and validate the board,
escalate ambiguity and record the authorized acceptor's decision; it cannot waive
gates or become an additional writer. Model names and requested changes are never
treated as observed activation. See `roles.md` for advisory and Admin boundaries.

Existing configuration is preserved unless `--force` is explicit. Force replaces
only `.shepherd/project.json` after acceptance; it changes no active ticket or
running worker. Reconfiguration during active work requires the handover protocol.
Never use a changed map to silently take over a running assignment. Installation
also preserves this config even with installer `--force` (it is not a managed file).


## Verify machine setup after allocation

Optionally declare `--launcher harness=executable` and `--kind harness=kind` (repeat
as needed). Each reference must name a harness in the accepted roster. Values are
user declarations, not inferred vendor mappings. Executables may be command names
or explicit paths, with no shell arguments. A kind must be discovered from the
installed `herdr agent start --help`, not guessed from a display name. Unknown
mappings stay absent and the doctor reports Unverified. The helpers do not run
launchers or claim Antigravity mapping support merely from the example table.

Run `python3 scripts/doctor-shepherd.py --project .` after accepting setup. See
`doctor.md` for return codes, environment gate and the separation between machine
checks and task readiness. Setup acceptance persists user choice only; it does not
claim Herdr is installed, a session is connected, agents are signed in, or required
independent role workers exist. Those remain blocked until observed preflight.
