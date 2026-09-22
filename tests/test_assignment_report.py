"""Focused checks for the read-only assignment report. No live Herdr, no launches."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PACK = Path(__file__).resolve().parents[1]
SCRIPT = PACK / "scripts/assignment-report.py"
spec = importlib.util.spec_from_file_location("assignment_report", SCRIPT)
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)

REQUIRED = ("architecture", "implementation", "design", "review", "testing", "board")

# Refuses anything except "pane list"; logs every call so tests can assert no
# mutating/other subcommand was ever attempted.
FAKE_BODY = '''
import json
import os
import sys
from pathlib import Path
base = Path(__file__).parent
args = sys.argv[1:]
with (base / "calls.jsonl").open("a") as stream:
    stream.write(json.dumps(args) + "\\n")
if args != ["pane", "list"]:
    raise SystemExit("fake herdr refuses any command other than read-only pane list")
case = os.environ.get("FAKE_CASE", "one_match")
panes = {
    "one_match": [{"pane_id": "w1:p1", "label": "Codex", "agent": "codex",
                   "agent_session": {"value": "sess-123"}, "agent_status": "idle"}],
    "none": [{"pane_id": "w1:p9", "label": "Someone Else", "agent": "codex", "agent_status": "idle"}],
    "duplicate": [{"pane_id": "w1:p1", "label": "Codex", "agent": "codex", "agent_status": "idle"},
                  {"pane_id": "w1:p2", "label": "Codex", "agent": "codex", "agent_status": "idle"}],
    "working": [{"pane_id": "w1:p1", "label": "Codex", "agent": "codex",
                "agent_session": {"value": "sess-999"}, "agent_status": "working"}],
    "malformed": "not-json",
}[case]
if case == "malformed":
    print(panes)
else:
    print(json.dumps({"result": {"panes": panes}}))
'''

# Always refuses; used to prove the script never even invokes herdr when it should not.
POISON_BODY = 'raise SystemExit("herdr must not be invoked in this case")\n'


class AssignmentReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='shepherd-assignment-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'project'
        (self.project / '.shepherd').mkdir(parents=True)
        self.config = {
            'schema_version': 1, 'allocation_accepted': True,
            'harnesses': [{'name': 'Codex', 'capabilities': 'Unverified'},
                          {'name': 'Claude', 'capabilities': 'Unverified'}],
            'assignments': {role: 'Codex' for role in REQUIRED},
        }
        self.env = os.environ.copy()
        self.env.pop('HERDR_ENV', None)
        self.env.pop('FAKE_CASE', None)

    def save_config(self):
        (self.project / '.shepherd/project.json').write_text(json.dumps(self.config))

    def fake_herdr(self, body=FAKE_BODY):
        fake = self.root / 'fake-herdr'
        fake.write_text('#!' + sys.executable + '\n' + body)
        fake.chmod(0o755)
        return fake

    def run_report(self, *, herdr=None, env=None, expected=0):
        args = [sys.executable, str(SCRIPT), '--project', str(self.project)]
        if herdr is not None:
            args += ['--herdr', str(herdr)]
        merged = self.env.copy()
        if env:
            merged.update(env)
        result = subprocess.run(args, env=merged, text=True, capture_output=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def snapshot(self):
        return {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_no_accepted_config_reports_clear_error(self):
        result = self.run_report(expected=1)
        self.assertIn('No accepted setup configuration found', result.stderr)

    def test_config_only_without_herdr_env_never_invokes_herdr_and_writes_nothing(self):
        self.save_config()
        poison = self.fake_herdr(POISON_BODY)
        before = self.snapshot()
        result = self.run_report(herdr=poison)
        self.assertIn('no live Herdr observation available', result.stdout)
        self.assertIn('Executor: harness=Codex pane=Unverified agent=Unverified '
                      'session=Unverified state=Unverified (no live Herdr observation)', result.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_live_match_reports_observed_facts_and_calls_only_pane_list(self):
        self.save_config()
        fake = self.fake_herdr()
        result = self.run_report(herdr=fake, env={'HERDR_ENV': '1', 'FAKE_CASE': 'one_match'})
        self.assertIn('Executor: harness=Codex pane=w1:p1 agent=codex session=sess-123 state=idle', result.stdout)
        calls = (self.root / 'calls.jsonl').read_text().splitlines()
        self.assertEqual(calls, ['["pane", "list"]'])  # never anything mutating

    def test_ownership_stays_unavailable_without_manifest_cross_reference(self):
        # Herdr facts and coordinator manifest facts have different provenance.
        # Even if a fixture injects similarly named keys, this read-only report
        # must not present them as Herdr-observed ownership.
        self.save_config()
        fake = self.fake_herdr(FAKE_BODY.replace(
            '"agent_status": "idle"}',
            '"agent_status": "idle", "ownership": "ticket-created", '
            '"creating_ticket": "HERDR-010"}'))
        result = self.run_report(herdr=fake, env={'HERDR_ENV': '1', 'FAKE_CASE': 'one_match'})
        self.assertIn('ownership and creating-ticket provenance are not Herdr fields', result.stdout)
        self.assertIn('cross-reference the external assignment manifest separately', result.stdout)
        self.assertNotIn('ownership=ticket-created', result.stdout)
        self.assertNotIn('creating_ticket=HERDR-010', result.stdout)

    def test_idle_state_reported_verbatim_never_relabeled_as_running(self):
        self.save_config()
        fake = self.fake_herdr()
        result = self.run_report(herdr=fake, env={'HERDR_ENV': '1', 'FAKE_CASE': 'one_match'})
        self.assertIn('state=idle', result.stdout)
        self.assertNotIn('state=running', result.stdout)
        self.assertNotIn('state=dispatched', result.stdout)

    def test_working_state_is_reported_as_herdr_reports_it(self):
        self.save_config()
        fake = self.fake_herdr()
        result = self.run_report(herdr=fake, env={'HERDR_ENV': '1', 'FAKE_CASE': 'working'})
        self.assertIn('state=working', result.stdout)

    def test_no_unique_match_stays_unverified_not_guessed(self):
        self.save_config()
        fake = self.fake_herdr()
        for case in ('none', 'duplicate'):
            with self.subTest(case=case):
                result = self.run_report(herdr=fake, env={'HERDR_ENV': '1', 'FAKE_CASE': case})
                self.assertIn('Unverified (no unique observed pane labeled for this harness)', result.stdout)

    def test_optional_role_absent_from_accepted_config_is_unassigned(self):
        self.save_config()
        result = self.run_report()
        self.assertIn('Sounding Board (optional): harness=Unassigned', result.stdout)
        self.assertIn('Critical Friend (optional): harness=Unassigned', result.stdout)

    def test_missing_required_role_is_rejected_before_any_report_is_printed(self):
        del self.config['assignments']['board']
        self.save_config()
        result = self.run_report(expected=1)
        self.assertIn('Incomplete role assignments', result.stderr)

    def test_required_role_absence_renders_as_missing_at_the_function_level(self):
        # load_accepted_config refuses an incomplete accepted config outright (tested
        # above); this exercises correlate()/render()'s own defensive wording directly.
        config = {'assignments': {role: 'Codex' for role in REQUIRED if role != 'board'}}
        rows = report.correlate(config, panes=None)
        text = report.render(rows, live=False)
        self.assertIn('Admin / board writer: harness=Missing', text)

    def test_unaccepted_or_malformed_config_rejected(self):
        self.config['allocation_accepted'] = False
        self.save_config()
        self.run_report(expected=1)
        (self.project / '.shepherd/project.json').write_text('{bad json')
        self.run_report(expected=1)

    def test_never_writes_any_file(self):
        self.save_config()
        fake = self.fake_herdr()
        before = self.snapshot()
        self.run_report(herdr=fake, env={'HERDR_ENV': '1', 'FAKE_CASE': 'one_match'})
        after = {p: v for p, v in self.snapshot().items() if 'calls.jsonl' not in str(p)}
        before = {p: v for p, v in before.items() if 'calls.jsonl' not in str(p)}
        self.assertEqual(after, before)


if __name__ == '__main__':
    unittest.main()
