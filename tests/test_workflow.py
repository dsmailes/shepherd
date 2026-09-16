"""Behavior checks for the portable pack. All output is in temporary projects."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import io

PACK = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(*args, cwd=None, expected=0):
    result = subprocess.run([str(arg) for arg in args], cwd=cwd, input='',
                            text=True, capture_output=True)
    if result.returncode != expected:
        raise AssertionError(f'{args}: exit {result.returncode}, expected {expected}\n'
                             f'{result.stdout}\n{result.stderr}')
    return result


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='shepherd-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / 'project with spaces'

    def install(self, *args, expected=0):
        return run(PACK / 'install.sh', '--project', self.project, *args, expected=expected)

    def setup(self, *args, expected=0):
        return run(PYTHON, PACK / 'scripts/setup-shepherd.py', '--project', self.project,
                   *args, expected=expected)

    def config(self):
        return json.loads((self.project / '.shepherd/project.json').read_text())

    def dashboard(self, *args, expected=0):
        return run(PYTHON, PACK / 'scripts/render-ticket-dashboard.py', '--project', self.project,
                   *args, expected=expected)

    def ticket(self, state='Ready'):
        path = self.project / '.tickets/TASK-001.md'
        path.write_text(f'# TASK-001\n\n## ID\n\n`TASK-001`\n\n## Title\n\nExample <script>\n\n## State\n\n`{state}`\n')
        (self.project / '.tickets/queue.md').write_text(f'# Queue\n\n## {state}\n\n- `TASK-001`\n')


class InstallerTests(ProjectCase):
    def test_fresh_project_clean_board_and_setup_not_assumed(self):
        self.install()
        self.dashboard('--validate')
        self.assertTrue((self.project / 'docs/tickets.html').is_file())
        self.assertTrue((self.project / 'docs/tickets.md').is_file())
        self.assertFalse((self.project / '.shepherd/project.json').exists())
        self.assertTrue((self.project / 'scripts/doctor-shepherd.py').is_file())
        names = sorted(p.name for p in (self.project / '.tickets').iterdir())
        self.assertEqual(names, ['README.md', 'queue.md', 'template.md'])
        self.assertFalse((self.project / 'docs/agent-plans').exists())
        run(PYTHON, self.project / 'scripts/setup-shepherd.py', '--project', self.project,
            '--harness', 'Custom', '--accept')
        self.assertEqual(set(self.config()['assignments'].values()), {'Custom'})

    def test_here_install(self):
        self.project.mkdir()
        run(PACK / 'install.sh', '--here', cwd=self.project)
        self.dashboard('--validate')

    def test_repeat_refuses_all_writes(self):
        self.install()
        instruction = self.project / 'AGENTS.md'
        instruction.write_text('User instructions\n')
        before = {p.relative_to(self.project): p.read_bytes()
                  for p in self.project.rglob('*') if p.is_file()}
        self.install(expected=1)
        after = {p.relative_to(self.project): p.read_bytes()
                 for p in self.project.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_dry_run_absent_and_force_preserve_unmanaged(self):
        self.install('--dry-run')
        self.assertFalse(self.project.exists())
        self.install()
        self.ticket()
        self.setup('--harness', 'Local', '--accept')
        (self.project / 'notes.txt').write_text('keep me')
        (self.project / 'AGENTS.md').write_text('custom')
        self.install('--force', '--dry-run')
        self.assertEqual((self.project / 'AGENTS.md').read_text(), 'custom')
        self.install('--force')
        self.assertNotEqual((self.project / 'AGENTS.md').read_text(), 'custom')
        self.assertEqual((self.project / 'notes.txt').read_text(), 'keep me')
        self.assertTrue((self.project / '.tickets/TASK-001.md').exists())
        self.assertEqual(set(self.config()['assignments'].values()), {'Local'})
        # Documented force resets queue, preserves tickets, and requires reconciliation.
        self.dashboard('--validate', expected=1)

    def test_symlink_destination_and_parent_refused_even_force(self):
        outside = self.root / 'outside'
        outside.mkdir()
        self.project.mkdir()
        (self.project / '.shepherd').symlink_to(outside, target_is_directory=True)
        self.install('--force', expected=1)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.project / 'AGENTS.md').exists())
        (self.project / '.shepherd').unlink()
        (self.project / 'AGENTS.md').symlink_to(outside / 'victim')
        self.install('--force', expected=1)
        self.assertFalse((outside / 'victim').exists())

    def test_directory_collision_preflight(self):
        (self.project / 'AGENTS.md').mkdir(parents=True)
        self.install('--force', expected=1)
        self.assertFalse((self.project / '.tickets').exists())


class SetupTests(ProjectCase):
    def test_empty_and_noninteractive_missing_roster(self):
        self.setup(expected=1)
        self.setup('--harness', '', '--accept', expected=1)
        self.assertFalse(self.project.exists())

    def test_proposal_does_not_write_and_one_harness_acceptance_is_unverified(self):
        self.setup('--harness', 'Custom Agent')
        self.assertFalse(self.project.exists())
        self.setup('--harness', 'Custom Agent', '--accept')
        config = self.config()
        self.assertEqual(set(config['assignments'].values()), {'Custom Agent'})
        self.assertIn('Blocked', config['readiness'])
        self.assertEqual(config['harnesses'][0]['capabilities'], 'Unverified')
        self.assertTrue(config['allocation_accepted'])

    def test_two_three_and_extra_harness_advice(self):
        for names in (['One', 'Two'], ['Codex', 'Claude', 'Antigravity'], ['A', 'B', 'C', 'D']):
            with self.subTest(names=names):
                args = [item for name in names for item in ('--harness', name)]
                self.setup(*args, '--accept', '--force')
                mapping = self.config()['assignments']
                self.assertEqual(mapping['review'], names[1])
                self.assertEqual(mapping['testing'], names[2] if len(names) > 2 else names[0])
                self.assertTrue(set(mapping.values()).issubset(names))

    def test_strength_then_user_override(self):
        self.setup('--harness', 'A', '--harness', 'B', '--strength', 'testing=B',
                   '--strength', 'review=A', '--assign', 'review=B', '--accept')
        self.assertEqual(self.config()['assignments']['testing'], 'B')
        self.assertEqual(self.config()['assignments']['review'], 'B')

    def test_optional_advisors_and_admin_alias_precedence(self):
        self.setup('--harness', 'A', '--harness', 'B', '--strength', 'admin=B',
                   '--assign', 'board=A', '--assign', 'admin=B',
                   '--strength', 'sounding-board=A', '--assign', 'sounding_board=B',
                   '--assign', 'critical-friend=A', '--accept')
        config = self.config()
        self.assertEqual(config['schema_version'], 1)
        self.assertEqual(config['board_writer_role'], 'board')
        self.assertEqual(config['assignments'], {
            'architecture': 'A', 'implementation': 'A', 'design': 'B',
            'review': 'B', 'testing': 'A', 'board': 'B',
            'sounding_board': 'B', 'critical_friend': 'A'})

    def test_unrequested_advisors_omitted_and_alias_owner_checked(self):
        self.setup('--harness', 'A', '--accept')
        before = (self.project / '.shepherd/project.json').read_bytes()
        self.assertNotIn('sounding_board', self.config()['assignments'])
        self.assertNotIn('critical_friend', self.config()['assignments'])
        for role in ('admin', 'sounding-board', 'critical_friend'):
            with self.subTest(role=role):
                self.setup('--harness', 'A', '--assign', role + '=Missing',
                           '--accept', '--force', expected=1)
                self.assertEqual((self.project / '.shepherd/project.json').read_bytes(), before)

    def test_unavailable_invalid_duplicate_rejected(self):
        for args in (['--assign', 'review=Missing'], ['--strength', 'testing=Missing'],
                     ['--assign', 'unknown=A'], ['--harness', 'a'],
                     ['--launcher', 'Missing=cli'], ['--kind', 'Missing=kind']):
            with self.subTest(args=args):
                self.setup('--harness', 'A', *args, '--accept', expected=1)
                self.assertFalse((self.project / '.shepherd/project.json').exists())

    def test_existing_config_and_force(self):
        self.setup('--harness', 'A', '--accept')
        before = (self.project / '.shepherd/project.json').read_bytes()
        self.setup('--harness', 'B', '--accept', expected=1)
        self.setup('--harness', 'B', '--force')
        self.assertEqual((self.project / '.shepherd/project.json').read_bytes(), before)
        self.setup('--harness', 'B', '--force', '--accept')
        self.assertEqual(set(self.config()['assignments'].values()), {'B'})

    def test_interactive_edit_accept_and_cancel(self):
        spec = importlib.util.spec_from_file_location("shepherd_setup", PACK / "scripts/setup-shepherd.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        argv = ["setup", "--project", str(self.project)]
        # Roster, constraints, strengths, explicit edit, acceptance.
        with mock.patch.object(sys, "argv", argv), mock.patch.object(sys.stdin, "isatty", return_value=True), \
                mock.patch("builtins.input", side_effect=["A,B", "Local tools only", "testing=B", "", "", "board=A", "no"]), \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(module.main(), 0)
        self.assertFalse(self.project.exists())
        with mock.patch.object(sys, "argv", argv), mock.patch.object(sys.stdin, "isatty", return_value=True), \
                mock.patch("builtins.input", side_effect=["A,B", "Local tools only", "testing=B", "A=custom-cli", "A=custom", "board=A", "yes"]), \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(module.main(), 0)
        self.assertEqual(self.config()["assignments"]["testing"], "B")
        self.assertEqual(self.config()["assignments"]["board"], "A")
        self.assertEqual(self.config()["preferences"], "Local tools only")
        self.assertEqual(self.config()["harnesses"][0]["executable"], "custom-cli")
        self.assertEqual(self.config()["harnesses"][0]["herdr_kind"], "custom")

    def test_symlink_config_refused(self):
        self.project.mkdir()
        outside = self.root / 'outside'
        outside.mkdir()
        (self.project / '.shepherd').symlink_to(outside, target_is_directory=True)
        self.setup('--harness', 'A', '--accept', '--force', expected=1)
        self.assertEqual(list(outside.iterdir()), [])


class DashboardTests(ProjectCase):
    def setUp(self):
        super().setUp()
        self.install()

    def test_valid_board_and_escaped_html(self):
        self.ticket()
        queue = self.project / '.tickets/queue.md'
        queue.write_text(queue.read_text().replace('- `TASK-001`', '- `TASK-001`: See `TASK-001.md`.'))
        self.dashboard('--validate')
        self.dashboard()
        html = (self.project / 'docs/tickets.html').read_text()
        self.assertIn('Example &lt;script&gt;', html)
        self.assertIn('TASK-001', (self.project / 'docs/tickets.md').read_text())

    def test_state_prose_mismatch_missing_and_duplicate_queue(self):
        cases = ['# Queue\n## Test\n- `TASK-001`\n',
                 '# Queue\n## Ready\n- `TASK-001`\n- `TASK-001`\n',
                 '# Queue\n## Unknown\n- `TASK-001`\n',
                 '# Queue\n## Ready\n- `TASK-999`\n']
        for queue in cases:
            self.ticket()
            (self.project / '.tickets/queue.md').write_text(queue)
            self.dashboard('--validate', expected=1)
        self.ticket('Ready\nExtra prose')
        self.dashboard('--validate', expected=1)
        (self.project / '.tickets/queue.md').unlink()
        self.dashboard('--validate', expected=1)


class FingerprintTests(ProjectCase):
    def setUp(self):
        super().setUp()
        self.project.mkdir()
        run('git', 'init', '-q', self.project)
        (self.project / 'source.txt').write_text('first')

    def fingerprint(self, *extra, expected=0):
        result = run(PYTHON, PACK / 'scripts/source-fingerprint.py', '--project', self.project,
                     *extra, expected=expected)
        return json.loads(result.stdout) if expected == 0 else result

    def test_untracked_content_new_path_and_mode_affect_target(self):
        first = self.fingerprint()
        self.assertEqual(first, self.fingerprint())
        (self.project / 'source.txt').write_text('second')
        second = self.fingerprint()
        self.assertNotEqual(first['value'], second['value'])
        (self.project / 'new.txt').write_text('new untracked')
        third = self.fingerprint()
        self.assertNotEqual(second['value'], third['value'])
        (self.project / 'new.txt').chmod(0o755)
        self.assertNotEqual(third['value'], self.fingerprint()['value'])

    def test_only_named_control_files_excluded(self):
        (self.project / '.tickets').mkdir()
        (self.project / 'docs').mkdir()
        before = self.fingerprint('--ticket', 'TASK-001')
        for name in ('.tickets/TASK-001.md', '.tickets/queue.md', 'docs/tickets.md', 'docs/tickets.html'):
            (self.project / name).write_text('board metadata')
        self.assertEqual(before, self.fingerprint('--ticket', 'TASK-001'))
        self.assertNotEqual(before['value'], self.fingerprint()['value'])
        (self.project / '.tickets/TASK-002.md').write_text('another ticket')
        self.assertNotEqual(before['value'], self.fingerprint('--ticket', 'TASK-001')['value'])
        self.fingerprint('--ticket', '../escape', expected=1)

    def test_gitignore_snapshot_symlink_and_tracked_deletion(self):
        (self.project / '.gitignore').write_text('ignored.txt\n')
        before = self.fingerprint()
        (self.project / 'ignored.txt').write_text('ignored untracked')
        self.assertEqual(before, self.fingerprint())
        snapshot = self.root / 'frozen'
        shutil.copytree(self.project, snapshot, ignore=shutil.ignore_patterns('.git'))
        result = run(PYTHON, PACK / 'scripts/source-fingerprint.py', '--project', snapshot, '--snapshot')
        first = json.loads(result.stdout)
        (snapshot / 'ignored.txt').write_text('snapshot includes ignored')
        second = json.loads(run(PYTHON, PACK / 'scripts/source-fingerprint.py', '--project', snapshot, '--snapshot').stdout)
        self.assertNotEqual(first['value'], second['value'])
        (self.project / 'link').symlink_to('source.txt')
        link = self.fingerprint()
        (self.project / 'link').unlink()
        (self.project / 'link').symlink_to('ignored.txt')
        self.assertNotEqual(link['value'], self.fingerprint()['value'])
        run('git', '-C', self.project, 'add', 'source.txt')
        tracked = self.fingerprint()
        (self.project / 'source.txt').unlink()
        self.assertNotEqual(tracked['value'], self.fingerprint()['value'])

    def test_nested_directory_not_repository_root(self):
        nested = self.project / 'nested'
        nested.mkdir()
        run(PYTHON, PACK / 'scripts/source-fingerprint.py', '--project', nested, expected=1)


if __name__ == '__main__':
    unittest.main()
