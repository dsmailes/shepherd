"""Fixture-driven checks for the read-only evidence verifier."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PACK = Path(__file__).resolve().parents[1]
SCRIPT = PACK / "scripts/verify-evidence.py"
FIXTURES = PACK / "tests/fixtures/verify-evidence"


class VerifyEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="verify-evidence-")
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        (self.root / ".tickets").mkdir()
        shutil.copy(PACK / "scripts/source-fingerprint.py", self.root / "scripts/source-fingerprint.py")
        (self.root / ".tickets/TASK-001.md").write_text("# TASK-001\n\n## State\n\n`In Progress`\n")
        (self.root / "src").mkdir()
        (self.root / "src/example.py").write_text("value = 1\n")
        (self.root / ".shepherd").mkdir()
        (self.root / ".shepherd/verify.json").write_text(json.dumps({
            "source_prefixes": ["src/"],
            "snapshot_paths": ["snapshots/"],
            "protected_files": ["src/protected.py"],
            "coordinator_prefixes": [".tickets/", ".shepherd/"],
        }))
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "base"], check=True)
        (self.root / "src/example.py").write_text("value = 2\n")
        self.artifacts = self.root.parent / ("artifacts-" + self.root.name)
        self.artifacts.mkdir()
        self.build_log = self.artifacts / "build.log"
        self.test_log = self.artifacts / "test.log"
        shutil.copy(FIXTURES / "pass-build.log", self.build_log)
        shutil.copy(FIXTURES / "pass-test.log", self.test_log)

    def tearDown(self):
        self.temp.cleanup()

    def run_tool(self, *args):
        return subprocess.run(["python3", str(SCRIPT), *map(str, args)],
                              text=True, capture_output=True, check=False)

    def common(self, command="verify-executor"):
        return [command, "--project", self.root, "--ticket", "TASK-001",
                "--build-log", self.build_log, "--test-log", self.test_log]

    def test_executor_pass_and_nonfrozen_mismatch_is_info(self):
        result = self.run_tool(*self.common(), "--expect-fingerprint", "wrong-value")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RESULT: PASS", result.stdout)
        self.assertIn("target may have changed", result.stdout)

    def test_frozen_fingerprint_mismatch_fails(self):
        result = self.run_tool(*self.common(), "--expect-fingerprint", "wrong-value", "--frozen")
        self.assertEqual(result.returncode, 1)
        self.assertIn("frozen target", result.stdout)

    def test_tester_zero_test_rerun_fails(self):
        zero = self.artifacts / "zero.log"
        shutil.copy(FIXTURES / "zero-test.log", zero)
        result = self.run_tool(*self.common("verify-tester"), "--rerun", f"filtered={zero}")
        self.assertEqual(result.returncode, 1)
        self.assertIn("rerun filtered tests ran", result.stdout)

    def test_duplicate_warning_fails(self):
        shutil.copy(FIXTURES / "duplicate-test.log", self.test_log)
        result = self.run_tool(*self.common())
        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate warnings", result.stdout)

    def test_missing_log_fails(self):
        result = self.run_tool(*self.common(), "--test-log", self.root / "missing.log")
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing", result.stdout)

    def test_wait_success_and_timeout(self):
        result = self.run_tool("wait", "--file", self.test_log, "--contains", "TEST SUCCEEDED", "--timeout", "1", "--interval", "1")
        self.assertEqual(result.returncode, 0)
        result = self.run_tool("wait", "--file", self.root / "missing", "--timeout", "0")
        self.assertEqual(result.returncode, 1)

    def test_codex_report_extracts_unique_fixture_and_rejects_ambiguity(self):
        sessions = self.root / "sessions"
        sessions.mkdir()
        shutil.copy(FIXTURES / "session.jsonl", sessions / "rollout-one.jsonl")
        output = self.root / "report.md"
        result = self.run_tool("codex-report", "--sessions", sessions, "--token", "probe-token-verify",
                               "--out", output, "--marker", r"SHEPHERD-REVIEW-COMPLETE:.*Pass$")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("NOT Herdr-observed", output.read_text())
        shutil.copy(FIXTURES / "session.jsonl", sessions / "rollout-two.jsonl")
        result = self.run_tool("codex-report", "--sessions", sessions, "--token", "probe-token-verify")
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
