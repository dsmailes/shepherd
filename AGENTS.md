# Shepherd development

This repository is a portable workflow pack, not an application.
Read `workflow/responsibilities.md`, `workflow/roles.md`, `workflow/runbook.md`,
`workflow/handoffs.md` and `workflow/herdr.md` before nontrivial implementation.
Use Ready tickets; keep live board writes with the one explicitly assigned owner.
Architects orchestrate only. Independent Executor, Reviewer and Tester sessions
are required. No self-review, hidden fallback or invented runtime evidence.
Use the ticket's explicit bootstrap ownership if it differs from the example map.
Do not import active pack tickets into installed projects. Preserve MIT attribution.
Installer changes require the full stdlib suite and fresh --project and --here
installs. Reports and build artifacts belong outside frozen source.
No commits, pushes or live harness launches are implied by installation.
