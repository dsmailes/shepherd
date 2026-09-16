# Machine and project doctor

Run after guided setup has saved `.shepherd/project.json`:

```sh
python3 scripts/doctor-shepherd.py --project .
```

This command reads configuration and emits JSON checks. It writes no files,
downloads nothing, changes no configuration, launches no agents and attempts no
login. Herdr and harness software are machine-level prerequisites; Shepherd's
configuration, instructions, tickets and memory remain local to each project.
Before transport probes, it requires architecture, implementation, review, testing
and board assignments; design, sounding_board and critical_friend are optional.
It rejects unknown keys and owners outside the declared roster. Existing complete
six-role schema 1 maps work unchanged. Setup input aliases such as admin are saved
as canonical keys; they are not extra JSON roles. Missing advisers stay absent.

The doctor locates Herdr and calls `--version` with a bounded timeout. If missing,
follow the [official installation guide](https://herdr.dev/docs/install/) yourself,
then open the project's terminal inside Herdr. It does not prescribe a fixed
Herdr version: installed CLI capabilities are the authority.

Before any caller/API check it requires the actual environment `HERDR_ENV=1`.
Outside Herdr it explains where to rerun; it does not inspect the focused pane or
any session. Do not set that variable to evade the gate. Inside Herdr it runs only
`herdr pane current --current` and validates returned pane/tab/workspace identity.
The returned canonical caller identity may differ from stale environment pane IDs.
Failed, timed-out or malformed responses stay Blocked; there is no implicit-focus
fallback or retry dispatch.

The doctor reads `herdr agent start --help` (help only) to discover supported kinds.
For each declared harness it checks explicit `executable` and `herdr_kind` mappings.
It locates the launcher without executing it. Missing mappings or unrecognized
help shape are Unverified; unsupported kinds and missing executables are Blocked.
Custom harness display names are never used to guess a mapping. Setup accepts
these via `--launcher harness=executable` and `--kind harness=kind`; blank interactive
answers preserve Unverified status. Neither mapping verifies that launcher and kind
actually work together; that requires live preflight by the assigned worker.

## Results

- Exit 0: the limited installation/transport checks passed. Task readiness is
  still **Unverified**. Continue the role/capability preflight in `herdr.md`.
- Exit 1: some machine/transport checks are Blocked or Unverified. Resolve each
  listed cause before dispatch; unknown capability is never a Ready signal.
- Exit 2: malformed arguments or missing/invalid/unaccepted project configuration.
  Complete guided setup or repair the named declaration before retrying.

Authentication, tool permissions, model activation, agent readiness and independent
worker identities cannot be inferred from an executable's presence or an API
response. The doctor never upgrades the config's persisted readiness or substitutes
for independent handoff evidence. It provides unauthenticated local observations.

`--herdr /explicit/path/to/herdr` chooses a known installed binary. `--timeout 5`
sets the per-command timeout in seconds; valid values are greater than zero through
60. Timeout/nonzero results are recorded; no installation, update or control command
is used to fix them automatically. Keep JSON output in the external ticket artifact
root if needed for a handoff.
