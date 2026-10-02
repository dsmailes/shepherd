# TASK-NNN Executor brief

Write this file in the external artifact root before dispatch. Send the Executor
one line pointing to it; do not paste a long brief into the pane.

## Context

- Ticket and acceptance: `.tickets/TASK-NNN.md`
- Base revision or relevant changed-file scope:
- Artifact root and exclusive source owner:
- References and decisions:

## Scope

1. Observable implementation item.
2. Observable implementation item.

Out of scope and owning ticket:

## Constraints and lessons

Read the project-owned lessons file, if present. Record decisions, risks and
which lessons apply. Do not edit tracked files outside the ticket's control paths
while the target is frozen.

## Checks

Run focused checks only. Name the commands, expected results and the evidence
files to write. The independent Tester runs the full required matrix once on the
frozen target. Use `scripts/verify-evidence.py` on the evidence before handoff.

## Report

Write a concise report to the external artifact root with changed files, source
revision or scope, commands and results, risks, deviations, and anything not
verified. No commits or pushes unless the ticket explicitly authorizes them.
