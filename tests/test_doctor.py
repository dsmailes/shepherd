"""Synthetic CLI fixtures: no live Herdr APIs or harness launches are exercised."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PACK = Path(__file__).resolve().parents[1]

# Labeled synthetic response matching the observed Herdr 0.9.0 shape; no live IDs.
CALLER = {'id': 'cli:pane:current', 'result': {'type': 'pane_current', 'pane': {
    'pane_id': 'fixture:pane:1', 'tab_id': 'fixture:tab:1', 'workspace_id': 'fixture:workspace:1'}}}

FAKE_BODY = '''
import json
import os
from pathlib import Path
import sys
import time
base = Path(__file__).parent
args = sys.argv[1:]
with (base / "calls.jsonl").open("a") as stream:
    stream.write(json.dumps(args) + "\\n")
case = os.environ.get("SHEPHERD_FAKE_CASE", "valid")
if args == ["--version"]:
    if case == "version_timeout":
        time.sleep(2)
    if case == "version_failure":
        raise SystemExit(7)
    print("herdr fixture-version")
elif args == ["pane", "current", "--current"]:
    if case == "api_timeout":
        time.sleep(2)
    if case == "api_failure":
        raise SystemExit(9)
    if case == "malformed":
        print("not json")
    elif case == "missing_identity":
        print(json.dumps({"result": {"type": "pane_current", "pane": {"pane_id": "alone"}}}))
    else:
        print((base / "caller.json").read_text())
elif args == ["agent", "start", "--help"]:
    if case == "help_timeout":
        time.sleep(2)
    if case == "help_failure":
        raise SystemExit(11)
    if case == "captured_help":
        print((base / "captured-help.txt").read_text())
    elif case == "unknown_help":
        print("Unrecognized help fixture")
    else:
        print("Options:\\n  --kind <KIND>\\n    [possible values: custom, other]\\n  --pane <ID>")
else:
    raise SystemExit("Unexpected command; fake refuses any launch/control")
'''


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='shepherd-doctor-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'project'
        (self.project / '.shepherd').mkdir(parents=True)
        self.config = {'schema_version': 1, 'allocation_accepted': True,
                       'harnesses': [{'name': 'My Tool', 'capabilities': 'Unverified',
                                      'executable': sys.executable, 'herdr_kind': 'custom'}],
                       'assignments': {role: 'My Tool' for role in
                                       ('architecture', 'implementation', 'design', 'review', 'testing', 'board')}}
        self.save()
        self.fake = self.root / 'fake-herdr'
        self.fake.write_text('#!' + sys.executable + '\n' + FAKE_BODY)
        self.fake.chmod(0o755)
        (self.root / 'caller.json').write_text(json.dumps(CALLER))
        # Captured installed CLI help, including the Usage-line --kind occurrence.
        (self.root / 'captured-help.txt').write_text((PACK / 'tests/fixtures/herdr-agent-start-help.txt').read_text())
        self.env = os.environ.copy()
        self.env['HERDR_ENV'] = '1'
        self.env['HERDR_PANE_ID'] = 'stale:caller:before-move'
        self.env.pop('SHEPHERD_FAKE_CASE', None)

    def save(self):
        (self.project / '.shepherd/project.json').write_text(json.dumps(self.config))

    def run_doctor(self, *, case='valid', inside=True, expected=0, executable=None, timeout=1):
        env = self.env.copy()
        env['SHEPHERD_FAKE_CASE'] = case
        if not inside:
            env.pop('HERDR_ENV', None)
        before = (self.project / '.shepherd/project.json').read_bytes()
        result = subprocess.run([sys.executable, str(PACK / 'scripts/doctor-shepherd.py'),
                                 '--project', str(self.project), '--herdr', str(executable or self.fake),
                                 '--timeout', str(timeout)], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertEqual((self.project / '.shepherd/project.json').read_bytes(), before)
        return json.loads(result.stdout)

    def calls(self):
        path = self.root / 'calls.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def check(self, result, name):
        return next(item for item in result['checks'] if item['name'] == name)

    def test_valid_caller_explicit_custom_mapping_no_launch_or_readiness_claim(self):
        result = self.run_doctor()
        self.assertTrue(result['transport_checks_passed'])
        self.assertEqual(result['task_readiness'], 'Unverified')
        self.assertEqual(self.check(result, 'caller_connection')['identity'], CALLER['result']['pane'])
        self.assertEqual(self.calls(), [['--version'], ['pane', 'current', '--current'], ['agent', 'start', '--help']])
        self.assertIn('authentication', result['unverified'])

    def test_captured_real_help_binds_option_declaration_after_usage(self):
        self.config['harnesses'][0]['herdr_kind'] = 'codex'
        self.save()
        result = self.run_doctor(case='captured_help')
        kinds = self.check(result, 'supported_kinds')['kinds']
        self.assertIn('codex', kinds)
        self.assertIn('agy', kinds)
        self.assertEqual(self.check(result, 'My Tool:kind')['status'], 'Pass')

    def test_missing_cli_no_api_and_install_guidance(self):
        result = self.run_doctor(executable=self.root / 'absent', expected=1)
        self.assertEqual(self.calls(), [])
        self.assertIn('https://herdr.dev/docs/install/', self.check(result, 'herdr_cli')['detail'])

    def test_outside_environment_never_inspects_pane_or_session(self):
        result = self.run_doctor(inside=False, expected=1)
        self.assertEqual(self.check(result, 'caller_connection')['status'], 'Unverified')
        self.assertEqual(self.calls(), [['--version'], ['agent', 'start', '--help']])

    def test_version_failure_and_timeout_do_not_probe_api(self):
        for case in ('version_failure', 'version_timeout'):
            with self.subTest(case=case):
                (self.root / 'calls.jsonl').unlink(missing_ok=True)
                result = self.run_doctor(case=case, timeout=0.5 if case.endswith("timeout") else 2, expected=1)
                self.assertEqual(self.check(result, 'herdr_cli')['status'], 'Blocked')
                self.assertEqual(self.calls(), [['--version']])

    def test_failed_timed_out_malformed_and_incomplete_caller(self):
        for case in ('api_failure', 'api_timeout', 'malformed', 'missing_identity'):
            with self.subTest(case=case):
                result = self.run_doctor(case=case, timeout=0.5 if case.endswith("timeout") else 2, expected=1)
                self.assertEqual(self.check(result, 'caller_connection')['status'], 'Blocked')

    def test_unknown_failed_and_timed_out_help_stays_unverified(self):
        for case in ('unknown_help', 'help_failure', 'help_timeout'):
            with self.subTest(case=case):
                result = self.run_doctor(case=case, timeout=0.5 if case.endswith("timeout") else 2, expected=1)
                self.assertEqual(self.check(result, 'supported_kinds')['status'], 'Unverified')
                self.assertEqual(self.check(result, 'My Tool:kind')['status'], 'Unverified')

    def test_unsupported_kind_and_unknown_mapping(self):
        self.config['harnesses'][0]['herdr_kind'] = 'unsupported'
        self.save()
        result = self.run_doctor(expected=1)
        self.assertEqual(self.check(result, 'My Tool:kind')['status'], 'Blocked')
        self.config['harnesses'][0] = {'name': 'My Tool', 'capabilities': 'Unverified'}
        self.save()
        result = self.run_doctor(expected=1)
        self.assertEqual(self.check(result, 'My Tool:kind')['status'], 'Unverified')
        self.assertEqual(self.check(result, 'My Tool:launcher')['status'], 'Unverified')

    def test_missing_declared_launcher(self):
        self.config['harnesses'][0]['executable'] = str(self.root / 'missing-launcher')
        self.save()
        result = self.run_doctor(expected=1)
        self.assertEqual(self.check(result, 'My Tool:launcher')['status'], 'Blocked')

    def test_invalid_unaccepted_and_empty_configuration(self):
        cases = [{'schema_version': 99}, {**self.config, 'allocation_accepted': False},
                 {**self.config, 'harnesses': []},
                 {**self.config, 'assignments': {'review': 'Missing'}}]
        for config in cases:
            with self.subTest(config=config):
                self.config = config
                self.save()
                self.run_doctor(expected=2)
                self.assertEqual(self.calls(), [])

    def test_core_and_optional_roles_accept_legacy_and_new_maps(self):
        # Existing complete six-role configurations need no migration.
        self.run_doctor()
        self.config['assignments'].pop('design')
        self.save()
        self.run_doctor()
        self.config['assignments'].update(sounding_board='My Tool', critical_friend='My Tool')
        self.save()
        self.run_doctor()

    def test_missing_unknown_and_invalid_roles_rejected_before_probes(self):
        original = self.config['assignments'].copy()
        cases = [{key: value for key, value in original.items() if key != role}
                 for role in ('architecture', 'implementation', 'review', 'testing', 'board')]
        cases.extend([{**original, 'admin': 'My Tool'},
                      {**original, 'unknown': 'My Tool'},
                      {**original, 'sounding_board': 'Missing'},
                      {**original, 'critical_friend': None},
                      {**original, 'design': []}])
        for assignments in cases:
            with self.subTest(assignments=assignments):
                self.config['assignments'] = assignments
                self.save()
                self.run_doctor(expected=2)
                self.assertEqual(self.calls(), [])

    def test_installed_doctor_smoke_with_synthetic_cli(self):
        target = self.root / 'installed'
        install = subprocess.run([str(PACK / 'install.sh'), '--project', str(target)], capture_output=True, text=True)
        self.assertEqual(install.returncode, 0, install.stderr)
        (target / '.shepherd/project.json').write_text(json.dumps(self.config))
        result = subprocess.run([sys.executable, str(target / 'scripts/doctor-shepherd.py'),
                                 '--project', str(target), '--herdr', str(self.fake)],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['task_readiness'], 'Unverified')


if __name__ == '__main__':
    unittest.main()
