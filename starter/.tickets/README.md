# Live ticket board

The named Admin/board writer alone edits tickets and `queue.md`. Allocate the next unused
numeric suffix by inspecting every ticket, then copy `template.md`. Keep filename,
H1, ID section and queue ID aligned. `## State` contains only one lifecycle token.
Each ticket appears exactly once under its state in the queue. `Superseded` is a
terminal state for a ticket replaced by an accepted ticket; link the replacement
without rewriting the superseded ticket's history. Explanations go in
other sections. After every mutation regenerate both projections, then run the
dashboard with `--validate`. On failure stop ordinary writes and reconcile. Admin
records authorized transitions and acceptance, never inventing role evidence.
These checks do not enforce handoffs. Use the compact template and link shared
assignment/report details once; expand for material risk.
