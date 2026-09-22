"""Focused tests for conservative, report-only pane cleanup."""
import importlib.util
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

PACK = Path(__file__).resolve().parents[1]
SCRIPT = PACK / "scripts/pane-lifecycle.py"
spec = importlib.util.spec_from_file_location("pane_lifecycle", SCRIPT)
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


class PaneLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.panes = [
            {"pane_id": "role-1", "role": "implementation",
             "creating_ticket": "HERDR-010", "ownership": "ticket-created"},
            {"pane_id": "board-1", "kind": "board", "board": True,
             "creating_ticket": "HERDR-010", "ownership": "ticket-created"},
            {"pane_id": "other-1", "role": "review", "creating_ticket": "HERDR-009",
             "ownership": "ticket-created"},
            {"pane_id": "ambiguous-1", "role": "testing",
             "creating_ticket": "HERDR-010", "ownership": "unknown"},
        ]

    def test_only_owned_quiescent_role_pane_is_allowed(self):
        result = lifecycle.evaluate_cleanup(
            self.panes, "HERDR-010", "SHEPHERD-REVIEW-COMPLETE: HERDR-010 / implementation / a1 / Pass",
            evidence_captured=True, admin_recorded=True, quiescent=True)
        self.assertEqual(result["allowed"], ["role-1"])
        refused = {item["pane_id"]: item["reasons"] for item in result["refused"]}
        self.assertIn("board panes remain until Done", refused["board-1"])
        self.assertIn("creating ticket is absent or does not match", refused["other-1"])
        self.assertIn("ownership provenance is absent or ambiguous", refused["ambiguous-1"])
        self.assertIn("no Herdr pane close was attempted", result["action"])

    def test_missing_gate_refuses_owned_pane(self):
        result = lifecycle.evaluate_cleanup(
            [self.panes[0]], "HERDR-010", "marker",
            evidence_captured=False, admin_recorded=False, quiescent=False)
        self.assertEqual(result["allowed"], [])
        reasons = result["refused"][0]["reasons"]
        self.assertIn("required evidence has not been captured", reasons)
        self.assertIn("Admin has not recorded completion", reasons)
        self.assertIn("worker/session quiescence is not confirmed", reasons)

    def test_cli_is_report_only_and_accepts_object_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            inventory = Path(temp) / "inventory.json"
            inventory.write_text(json.dumps({"panes": [self.panes[0]]}))
            result = subprocess.run([
                sys.executable, str(SCRIPT), "--inventory", str(inventory),
                "--ticket", "HERDR-010", "--completion-marker", "marker",
                "--evidence-captured", "--admin-recorded", "--quiescent",
            ], text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["allowed"], ["role-1"])
        self.assertEqual(payload["action"], "report-only; no Herdr pane close was attempted")


if __name__ == "__main__":
    unittest.main()
