#!/usr/bin/env python3
"""Evaluate Herdr pane cleanup without closing panes.

This helper is deliberately read-only.  It turns an observed pane inventory and
the ticket's completion evidence into a close plan.  A caller may execute the
plan only after independently reconciling the same pane IDs and confirming
quiescence; the helper never invokes Herdr or guesses ownership from labels.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _reason(pane: dict, ticket: str, completion_marker: str,
            evidence_captured: bool, admin_recorded: bool,
            quiescent: bool) -> list[str]:
    reasons: list[str] = []
    pane_id = pane.get("pane_id") or pane.get("id")
    if not isinstance(pane_id, str) or not pane_id.strip():
        reasons.append("pane has no observed stable ID")
    if pane.get("board") is True or pane.get("kind") == "board":
        reasons.append("board panes remain until Done")
    if not isinstance(pane.get("role"), str) or not pane["role"].strip():
        reasons.append("pane is not an active role pane")
    if pane.get("creating_ticket") != ticket:
        reasons.append("creating ticket is absent or does not match")
    if pane.get("ownership") != "ticket-created":
        reasons.append("ownership provenance is absent or ambiguous")
    if not completion_marker.strip():
        reasons.append("scoped completion marker was not supplied")
    if not evidence_captured:
        reasons.append("required evidence has not been captured")
    if not admin_recorded:
        reasons.append("Admin has not recorded completion")
    if not quiescent:
        reasons.append("worker/session quiescence is not confirmed")
    return reasons


def evaluate_cleanup(panes: list[dict], ticket: str, completion_marker: str,
                     *, evidence_captured: bool, admin_recorded: bool,
                     quiescent: bool) -> dict:
    """Return allowed role-pane IDs and explicit refusal reasons.

    Every input pane is represented in ``refused`` unless it is safe to close.
    The function is intentionally conservative: missing, malformed, unrelated,
    board, or ambiguous-ownership panes are preserved.
    """
    if not isinstance(ticket, str) or not ticket.strip():
        raise ValueError("ticket must be a non-empty string")
    if not isinstance(panes, list):
        raise ValueError("panes must be a list")
    allowed: list[str] = []
    refused: list[dict] = []
    for pane in panes:
        if not isinstance(pane, dict):
            refused.append({"pane_id": "Unavailable", "reasons": ["malformed pane record"]})
            continue
        pane_id = pane.get("pane_id") or pane.get("id") or "Unavailable"
        reasons = _reason(pane, ticket, completion_marker, evidence_captured,
                          admin_recorded, quiescent)
        if reasons:
            refused.append({"pane_id": pane_id, "reasons": reasons})
        else:
            allowed.append(pane_id)
    return {"ticket": ticket, "allowed": allowed, "refused": refused,
            "action": "report-only; no Herdr pane close was attempted"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True,
                        help="JSON object with a panes list, or a JSON pane list")
    parser.add_argument("--ticket", required=True)
    parser.add_argument("--completion-marker", required=True)
    parser.add_argument("--evidence-captured", action="store_true")
    parser.add_argument("--admin-recorded", action="store_true")
    parser.add_argument("--quiescent", action="store_true")
    args = parser.parse_args()
    try:
        payload = json.loads(args.inventory.read_text(encoding="utf-8"))
        panes = payload.get("panes") if isinstance(payload, dict) else payload
        result = evaluate_cleanup(
            panes, args.ticket, args.completion_marker,
            evidence_captured=args.evidence_captured,
            admin_recorded=args.admin_recorded,
            quiescent=args.quiescent,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, AttributeError) as exc:
        parser.exit(1, f"Pane lifecycle check stopped: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
