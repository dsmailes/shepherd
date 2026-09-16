# <ticket> / <role> / <attempt>

Aim for 150–300 words; expand for material risk. Link the shared assignment manifest
and detailed logs instead of copying the ticket or other workers' identities.

- Binding: <external manifest link and own ticket/role/attempt/generation entry>
- Verdict: <Ready for review / Pass / Fail / Blocked; advisory roles: findings>
- Result: <changes or scope inspected; acceptance covered; actionable findings>
- Target: <command/declaration and before/after JSON links, or immutable commit>
- Checks: <exact commands, exit codes and output links; limitations>
- Next gate / risks: <recommendation, blockers or untested behavior; no board writes>
- Self-visible telemetry: <worker identity, model, effort, tokens: Unavailable for
  each unless observed; selection reason/activation and changes if observed>
- Effort: <elapsed time and correction round; no estimated hidden token usage>

The manifest holds coordinator-observed worker identity, supervisor lineage,
transport IDs, readiness/delivery state, checkout/source ownership, artifact root,
selection rationale and verification/integration plan once. Workers link their own
entry and report discrepancies; unseen self-identity is **Unavailable**, never a
copied supervisor ID. Coordinator-observed independence is still required.

## Acceptance entry (Admin records after independent role reports)

- Evidence: <manifest links to distinct E/R/T reports, matching targets and required
  integration/full validation; separate merge N/A only with rationale>
- Decision: <Accept / Reject; acceptor identity, user/delegated authority, rationale,
  timestamp and any authorized waiver; Architect cannot accept its own work>
- Board: <transition recorded, projections regenerated, validation result>

Test Pass alone is not acceptance. Role independence and truthful evidence cannot
be waived. Admin records the decision; it does not author another role's evidence.
