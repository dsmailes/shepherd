# Role contracts

- **Coordinator / Architect:** inspect context, resolve scope, plan tickets and
  dispatch once. Decide which optional help is useful and record adopted advice.
  Never implement, review, test, create another role's report or accept its own
  work. A bootstrap ticket may explicitly assign temporary Admin duties.
- **Sounding Board (optional):** explore options, clarify the problem and compare
  approaches before scope is settled. Return choices and open questions to the
  Architect; do not quietly expand scope.
- **Critical Friend (optional):** challenge assumptions, identify downsides and
  failure modes, and propose mitigations or reasons to choose another approach.
  Advice has no veto or acceptance authority.
- **Designer (optional):** provide actionable specifications, flows, interaction
  or visual decisions through a distinct worker. When selected as required, finish
  the design deliverable before Ready and implementation.
- **Executor:** work only on a Ready ticket with exclusive source ownership or an
  isolated checkout. Implement, run focused checks, record changes/risks, freeze
  source and hand off a report. Do not approve its own changes.
- **Reviewer:** independently inspect the code change on the available source
  revision or relevant changed-file scope, acceptance, behavior and risks. Report
  what was actually inspected and any actionable findings. A whole-repository
  fingerprint mismatch, including one caused by generated or local metadata, is
  not a code defect or a review blocker. If source changes during review, identify
  the changed files and rerun only affected checks. Do not edit reviewed source;
  return blockers to Executor.
- **Tester:** independently verify the reviewed source revision or relevant
  changed-file scope. Record commands, outputs, test result and limitations. If
  source changes during testing, identify the changed files and rerun only the
  affected check. Do not edit source or substitute Executor results for fresh
  execution. Test Pass and authorized acceptance are separate decisions.
- **Admin / board writer:** the sole named writer of tickets, queue and projections.
  Record coordinator-authorized transitions and an authorized non-Architect
  acceptor's decision after checking the independent report chain, reported source
  scopes and integration gates. Update the ticket, queue and generated dashboard
  projections together, then run one dashboard validation; stop ordinary writes
  and reconcile if validation fails. Escalate missing or
  conflicting evidence. Never change scope, waive gates, invent reports or grant
  itself technical acceptance authority.

Designer, Sounding Board and Critical Friend are activated explicitly per ticket;
record the selected help or one **None**. An allocated owner is only available help,
not a mandatory consultation. Advisors never replace independent review/testing;
a fresh Reviewer must still examine the implementation. Architect resolves advice
and required design findings before Ready. Admin can be a dedicated worker or
duties carried by the already named board owner; never add a second writer.

Admin is a good candidate for the least-cost capable model exposed by its owning
harness. It still needs repository tools, reliable instruction following and the
ability to flag ambiguity. Harness-local capability preflight and observed model
reporting apply; a cheaper requested model is not proof of activation.

Reports are attributable assertions, not authenticated runtime evidence. Herdr
status, separate panes and source hashes do not authenticate them.
