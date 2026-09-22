# Shepherd

A portable workflow pack for teams of coding agents, coordinated through **Herdr**.
Install it into a project to give agents shared instructions, a ticket board and
an explicit process: **plan → implement → independent review → test → accept**.
Shepherd provides Markdown procedures and Python helpers; agents carry out the work.

You assign responsibilities to harnesses. Each harness chooses from its own
available models and delegates to independent workers when its runtime supports it.

| Responsibility | Example owning harness |
| --- | --- |
| Architecture and coordination | Codex |
| Implementation | Codex |
| Designer (optional) | Claude |
| Sounding Board: explore options (optional) | Explicit assignment only |
| Critical Friend: challenge downsides (optional) | Explicit assignment only |
| Review | Claude |
| Testing | Antigravity |
| Admin: sole ticket-board writer | Antigravity |

This is an editable example, not an availability claim. A harness is the tool/session
running agents; a model is a capability that harness exposes. There is no central
role-to-model table. See [responsibilities](workflow/responsibilities.md).
Optional roles activate only when the ticket selects them. Admin can be a dedicated
worker using a cheaper capable model its harness exposes; it records authorized
decisions and validates the board. It gains no technical acceptance authority.

## Quickstart

Requirements: **Python 3.10+**, a **POSIX shell**, and **Git** for source fingerprints.
Local installation, setup and board viewing work without Herdr. Live coordination
also requires Herdr and the selected agent harnesses, with their capabilities
verified before dispatch. The pack itself uses Python's standard library and needs
no package downloads or credentials.

Clone this repository using its published Git URL, or download and extract its
source archive. The extracted directory is the **pack**; the repository you want
agents to work on is the **target project**. Replace the example paths below with
your own. Keep these directories separate; the installer refuses to install the
pack into itself.

```sh
cd /absolute/path/to/shepherd
./install.sh --project /absolute/path/to/project --dry-run
./install.sh --project /absolute/path/to/project

# Continue from the target project, using its installed helpers.
cd /absolute/path/to/project
python3 scripts/setup-shepherd.py --project .
python3 scripts/setup-shepherd.py --project . --show
python3 scripts/render-ticket-dashboard.py --project . --terminal
python3 scripts/setup-workspace.py --project .
```

Setup interactively asks which harnesses you can access, offers role assignments
and saves your accepted choices. `--show` displays the saved role-to-harness
allocations without writing files or checking runtime workers; absent optional
roles appear as Unassigned. These persisted choices do not establish live worker
identities or readiness. Use `--help` for noninteractive options. If the
target is not already a Git repository, initialize it before using source
fingerprints. Installation does not initialize Git, commit files or push anything.

The workspace helper creates the main Architect pane, lazygit, and read-only
Ticket and Role Boards. Role panes are ticket-scoped and deferred by default;
activate only the roles needed for the current ticket with repeated options such
as `--role implementation --role review`. On an idle current shell it uses that
pane as the main Architect panel, puts lazygit at the bottom left and the Ticket
Board at the bottom right. If the current pane is busy, it leaves it untouched
and creates the Architect pane instead. Review the plan, then pass `--accept`
from the actual Herdr environment (`HERDR_ENV=1`). It verifies installed Herdr
help and explicit pane/workspace identities, preserves focus where possible,
stops on a failed launch without retrying, and reports unobserved model
telemetry as `Unavailable`.

Alternatively, install from the target directory with an absolute pack path:

```sh
cd /absolute/path/to/project
/absolute/path/to/shepherd/install.sh --here --dry-run
/absolute/path/to/shepherd/install.sh --here
```

### What installation writes

The installer copies `workflow/` to `.shepherd/`, the project helpers to `scripts/`,
clean `starter/` files into the project, and attribution into `.shepherd/LICENSE`.
It generates `docs/tickets.md` and `docs/tickets.html` for the empty board.
It never copies Shepherd's own active tickets, memory, plans or execution history.

Any existing managed file aborts the entire preflight, even if its contents match.
`--dry-run` writes nothing and still reports conflicts. `--force` replaces **only
listed managed files**, including `AGENTS.md`, `CLAUDE.md`, responsibility choices,
ticket template/queue, memory README and dashboard projections. Back these up first.
Unlisted files, including active tickets and durable memory notes, are preserved;
force can reset a populated queue, so reconcile it with preserved tickets and run
validation afterwards. Project parent aliases (such as macOS `/var`) are normalized. Symlink project
roots, managed destinations/ancestors inside the project and directory collisions are
refused even with force. Force does not merge project instructions. Interrupted
filesystem writes are not transactional; resolve a partial install explicitly.

## Run the workflow

Run these steps and the following helper commands from the **target project**.

1. If you have not already done setup, run `python3 scripts/setup-shepherd.py --project .`. Declare accessible harnesses,
   review advice, edit roles and accept the allocation. See `.shepherd/setup.md`.
   The accepted map lives in `.shepherd/project.json`; capabilities stay unverified
   until preflight. Assign exactly one coordinator and board writer identity.
2. Run `python3 scripts/doctor-shepherd.py --project .` inside Herdr to check the
   installed CLI, caller/API connection and explicit harness launcher/kind mappings.
   Follow `.shepherd/doctor.md` for Blocked/Unverified checks. Then read
   `.shepherd/herdr.md`, discover the installed CLI and capabilities, and
   follow `.shepherd/runbook.md`. Do not dispatch to missing harnesses.
3. The Architect proposes a compact ticket using `.tickets/template.md`, selecting
   optional help or None. Required design finishes before `Ready`. Admin allocates
   the ID and records coordinator-observed bindings once in an external manifest.
4. Dispatch independent Executor, Reviewer and Tester workers. Reports live in one
   repository-external ticket artifact root. Only the board writer updates state.
5. Admin records an authorized non-Architect acceptor's decision after same-target
   review, tests and required integration, then regenerates and validates the board.
   A Tester Pass alone does not mean Done.

Small tickets aim for 300–500 words and role reports for 150–300, linking shared
bindings and detailed logs once. Workers report unseen self-telemetry as
`Unavailable`; the coordinator records observed independence. Dispatch once,
acknowledge delivery, then monitor that task to completion. See the
[runbook](workflow/runbook.md) and [role contracts](workflow/roles.md).

```sh
python3 scripts/render-ticket-dashboard.py --project . --validate
python3 scripts/render-ticket-dashboard.py --project .
python3 scripts/source-fingerprint.py --project . --ticket TASK-001
```

The dashboard is a generated view; `.tickets/*.md` and `.tickets/queue.md` are the
live board. Fingerprints detect content changes, including nonignored untracked
source. They do not lock files or authenticate reports. Read [handoffs](workflow/handoffs.md)
and the [report template](workflow/report-template.md) before accepting work.

### Ticket board in a terminal pane

Use the terminal view for a compact board with ticket IDs, states, titles, counts
and board warnings. Markdown tables need a Markdown viewer; printing
`docs/tickets.md` directly displays their markup.

```sh
python3 scripts/render-ticket-dashboard.py --project . --terminal
# Keep a dedicated terminal pane updated; Ctrl-C stops it.
python3 scripts/render-ticket-dashboard.py --project . --watch
```

These commands read `.tickets/` and write no files. Watch mode requires a TTY,
polls once per second, and redraws only when ticket/queue content or the pane size
changes. Use `--interval 2` to poll every two seconds. Piped `--terminal` output is
plain text without terminal escape sequences.

The view detects the terminal size, leaves a spare row and column to avoid
scrolling, and puts blocked and active tickets ahead of completed work. Hidden
tickets and warning counts remain visible; `~` marks truncated text. It shows the
first warning; use `--validate` separately for the full warning list. Very small
panes ask for more room. Unicode widths use conservative stdlib estimates; exact
emoji/font widths vary by terminal. Override geometry with `--width 120 --height 12`
for a reproducible snapshot (non-TTY fallback: 120 by 24, or `COLUMNS`/`LINES`).
Run the existing command without `--terminal`/`--watch` to regenerate the full
HTML and Markdown dashboards.

## Per-project use and machine setup

Install Herdr and the chosen harness software once on your machine; use the
[official Herdr installation guide](https://herdr.dev/docs/install/) if it is absent.
Shepherd never downloads software, signs in, or launches agents during installation,
setup or doctor checks. Run the local installer and accepted setup separately for
each project. Each project keeps its own `.shepherd/project.json`, instructions,
tickets and memory; it does not change another project's allocation.

Existing `AGENTS.md` or `CLAUDE.md` makes the conservative installer refuse writes.
To keep existing project rules, install into a temporary directory, inspect its
manifest, deliberately merge the generated instructions into your existing files,
and copy the remaining project-local files after checking for collisions. Do not
use force merely to merge instructions: it replaces managed files including them.

## Develop this pack

From the Shepherd pack directory, run the existing standard-library test suite:

```sh
python3 -m unittest discover -s tests -v
```

This first version supplies portable instructions and disclosed independent reports.
It does not enforce runtime roles, launch agents automatically, install harnesses,
or claim a tested live Antigravity integration. Unsupported delegation or missing
independent sessions blocks the affected work until explicitly reassigned.

### Repository layout

| Path | Purpose |
| --- | --- |
| `workflow/` | Role contracts, setup and operating procedures; installed as `.shepherd/` |
| `starter/` | Clean project instructions, ticket templates and memory directory |
| `scripts/` | Installer, setup, doctor, board rendering and fingerprint helpers |
| `tests/` | Standard-library tests and fixtures |
| `.tickets/` | Local development tickets and queue; excluded from published source |
| `docs/agent-plans/` | Local agent development plans; excluded from published source |
| `docs/tickets.md`, `docs/tickets.html` | Local generated board views; excluded from published source |
| `docs/` (other paths) | Product documentation eligible for publishing |

### Before publishing

The pack's `.gitignore` keeps its development history local: root `.tickets/`,
`docs/agent-plans/`, `docs/tickets.md` and `docs/tickets.html` are excluded from
Git and published source. Clones and source archives omit this local history;
installation uses the clean templates in `starter/` to create a new project board.

It also excludes Python environments/caches, coverage output,
OS/editor temporary files and local `.env` files. Environment examples named
`.env.example`, `.env.sample`, `.env.template` or `.env.<name>.example` (also
`.sample`/`.template`) remain eligible for Git; keep their values non-secret.
Source, shared configuration, starter templates (including `starter/.tickets/`)
and other product documentation remain eligible for Git.

Review `git status --short` and the files you intend to publish before committing.
Ignore rules do not remove already tracked files or scan for credentials. Keep
execution reports and build artifacts outside the source tree as required by the
workflow. This root `.gitignore` is for developing Shepherd; the installer does
not copy it into target projects, which retain their own ignore policy.

## Attribution

Inspired by dev-team. The dashboard and fingerprint implementation are adapted
from dev-team, Copyright (c) 2026 David John Smailes, under the [MIT License](LICENSE).
