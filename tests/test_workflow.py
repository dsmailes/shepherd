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

    def test_workflow_only_updates_only_shepherd_documents(self):
        self.install()
        instructions = self.project / 'AGENTS.md'
        instructions.write_text('Project-specific instructions\n')
        script = self.project / 'scripts/setup-workspace.py'
        script_before = script.read_bytes()
        ticket = self.project / '.tickets/queue.md'
        ticket_before = ticket.read_bytes()
        workflow = self.project / '.shepherd/roles.md'
        workflow.write_text('old workflow\n')
        result = self.install('--workflow-only')
        self.assertIn('Workflow documents updated', result.stdout)
        self.assertNotEqual(workflow.read_text(), 'old workflow\n')
        self.assertEqual(instructions.read_text(), 'Project-specific instructions\n')
        self.assertEqual(script.read_bytes(), script_before)
        self.assertEqual(ticket.read_bytes(), ticket_before)

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

    def test_show_displays_persisted_roles_and_optional_absence_without_writes(self):
        self.install()
        self.setup('--harness', 'Codex', '--harness', 'Claude', '--accept')
        config_path = self.project / '.shepherd/project.json'
        before = config_path.read_bytes()
        result = self.setup('--show')
        self.assertIn('Coordinator / Architect: Codex', result.stdout)
        self.assertIn('Executor: Codex', result.stdout)
        self.assertIn('Reviewer: Claude', result.stdout)
        self.assertIn('Sounding Board (optional): Unassigned', result.stdout)
        self.assertIn('Critical Friend (optional): Unassigned', result.stdout)
        self.assertIn('not live worker/session identities or readiness evidence', result.stdout)
        self.assertEqual(config_path.read_bytes(), before)

    def test_show_rejects_missing_invalid_and_mixed_setup_options(self):
        self.install()
        self.setup('--show', expected=1)
        self.assertFalse((self.project / '.shepherd/project.json').exists())
        self.setup('--harness', 'A', '--accept')
        config_path = self.project / '.shepherd/project.json'
        before = config_path.read_bytes()
        for options in (('--accept',), ('--force',), ('--harness', 'B'),
                        ('--assign', 'review=A'), ('--preferences', 'local only')):
            with self.subTest(options=options):
                self.setup('--show', *options, expected=1)
                self.assertEqual(config_path.read_bytes(), before)
        config_path.write_text('{bad json')
        self.setup('--show', expected=1)
        config_path.write_text('{"schema_version": 1, "allocation_accepted": false}')
        self.setup('--show', expected=1)

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


class WorkspaceSetupTests(ProjectCase):
    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location('workspace_setup', PACK / 'scripts/setup-workspace.py')
        self.workspace_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.workspace_module)

    def workspace(self, *args, expected=0, env=None):
        merged = os.environ.copy()
        if env:
            merged.update(env)
        return subprocess.run([PYTHON, PACK / 'scripts/setup-workspace.py', '--project', self.project,
                               *args], env=merged, text=True, capture_output=True, check=False)

    def accepted(self, kind='codex'):
        self.install()
        self.setup('--harness', 'Codex', '--kind', f'Codex={kind}', '--accept')

    def test_preview_reads_assignments_and_is_mutation_free(self):
        self.accepted()
        before = {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        result = self.workspace()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('No live changes', result.stdout)
        self.assertIn('Shepherd architecture', result.stdout)
        self.assertIn('Lazygit', result.stdout)
        self.assertIn('Ticket Board', result.stdout)
        self.assertIn('Role Board', result.stdout)
        self.assertEqual(before, {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob('*') if p.is_file()})

    def test_preview_defers_unrequested_role_panes(self):
        self.accepted()
        result = self.workspace()
        self.assertNotIn('Shepherd implementation', result.stdout)
        self.assertNotIn('Shepherd review', result.stdout)
        result = self.workspace('--role', 'implementation', '--role', 'review')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Shepherd implementation', result.stdout)
        self.assertIn('Shepherd review', result.stdout)

    def test_accept_refuses_outside_herdr_before_cli(self):
        self.accepted()
        result = self.workspace('--accept', env={'HERDR_ENV': '0'})
        self.assertEqual(result.returncode, 1)
        self.assertIn('actual HERDR_ENV=1', result.stderr)

    def test_accept_refuses_unmapped_harness_before_mutation(self):
        self.accepted()
        config = self.config()
        config['harnesses'][0].pop('herdr_kind')
        (self.project / '.shepherd/project.json').write_text(json.dumps(config))
        result = self.workspace('--accept', env={'HERDR_ENV': '1'})
        self.assertEqual(result.returncode, 1)
        self.assertIn('No Herdr kind mapping', result.stderr)

    def test_observed_layout_area_and_rects_are_validated(self):
        module = self.workspace_module
        response = {'result': {'layout': {
            'area': {'x': 0, 'y': 0, 'width': 120, 'height': 40},
            'panes': [{'pane_id': 'base', 'rect': {'x': 0, 'y': 0, 'width': 120, 'height': 40}}],
        }}}
        self.assertEqual(module.validate_geometry(response, 8), (120.0, 40.0))
        response['result']['layout']['panes'][0]['rect']['width'] = 10
        with self.assertRaisesRegex(RuntimeError, 'below usable minimums'):
            module.validate_geometry(response, 8)

    def test_foreground_shell_child_and_pid_mismatch_are_busy(self):
        module = self.workspace_module
        busy = {'result': {'process_info': {'shell_pid': 42, 'foreground_processes': [
            {'pid': 42, 'command': 'zsh'}, {'pid': 99, 'command': 'python worker.py'}]}}}
        with self.assertRaisesRegex(RuntimeError, 'multiple foreground'):
            module.shell_ready(busy, 'p1')
        mismatch = {'result': {'process_info': {'shell_pid': 42, 'foreground_processes': [
            {'pid': 99, 'command': 'zsh'}]}}}
        with self.assertRaisesRegex(RuntimeError, 'differs from shell PID'):
            module.shell_ready(mismatch, 'p1')
        unknown = {'result': {'process_info': {'shell_pid': 42, 'foreground_processes': [
            {'command': 'zsh'}]}}}
        with self.assertRaisesRegex(RuntimeError, 'unknown foreground process PID'):
            module.shell_ready(unknown, 'p1')

    def test_created_pane_geometry_uses_captured_layout_shape_and_minimums(self):
        module = self.workspace_module
        good = {'result': {'layout': {
            'area': {'x': 0, 'y': 0, 'width': 245, 'height': 59},
            'panes': [{'pane_id': 'created-1', 'rect': {'x': 123, 'y': 0, 'width': 122, 'height': 59}}],
        }}}
        self.assertEqual(module.validate_created_pane(good, 'created-1'), (122.0, 59.0))
        undersized = {'result': {'layout': {
            'area': {'x': 0, 'y': 0, 'width': 245, 'height': 59},
            'panes': [{'pane_id': 'created-1', 'rect': {'x': 123, 'y': 0, 'width': 15, 'height': 7.38}}],
        }}}
        with self.assertRaisesRegex(RuntimeError, 'below usable minimums'):
            module.validate_created_pane(undersized, 'created-1')

    def test_mocked_accept_uses_explicit_ids_geometry_and_safe_argv(self):
        self.accepted()
        module = self.workspace_module
        help_result = subprocess.CompletedProcess([], 0, 'Usage: pane run <PANE_ID> <COMMAND>... --direction right|down\n', '')
        start_help = subprocess.CompletedProcess([], 0, '[possible values: codex]\n  --kind <KIND>\n  --pane <ID>', '')
        responses = []
        rects = {'base': {'width': 1000.0, 'height': 200.0}}
        def fake_run(argv, **kwargs):
            responses.append(argv)
            if argv[-1] == '--help':
                if argv[1:3] == ['agent', 'start']:
                    return start_help
                return help_result
            if argv[1:3] == ['pane', 'current']:
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'pane': {'pane_id': 'base', 'workspace_id': 'ws'}}}), '')
            if argv[1:3] == ['pane', 'layout']:
                pane_id = argv[-1]
                rect = rects[pane_id]
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'layout': {
                    'area': {'x': 0, 'y': 0, 'width': 1000, 'height': 200},
                    'panes': [{'pane_id': pane_id, 'rect': {'x': 0, 'y': 0, **rect}}],
                }}}), '')
            if argv[1:3] == ['pane', 'list']:
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'panes': [{'pane_id': 'base'}]}}), '')
            if argv[1:2] == ['agent']:
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'agents': []}}), '')
            if argv[1:3] == ['pane', 'process-info']:
                if argv[-1] == 'base':
                    return subprocess.CompletedProcess(argv, 1, '', 'busy coordinator pane')
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'process_info': {'shell_pid': 42, 'foreground_processes': [{'pid': 42, 'command': 'zsh'}]}}}), '')
            if argv[1:3] == ['pane', 'split']:
                pane_id = f'p{sum(item[1:3] == ["pane", "split"] for item in responses)}'
                source = argv[argv.index('--pane') + 1]
                direction = argv[argv.index('--direction') + 1]
                source_rect = rects[source]
                rects[pane_id] = dict(source_rect)
                if direction == 'right':
                    rects[source]['width'] /= 2
                    rects[pane_id]['width'] /= 2
                else:
                    rects[source]['height'] /= 2
                    rects[pane_id]['height'] /= 2
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'pane': {'pane_id': pane_id}}}), '')
            return subprocess.CompletedProcess(argv, 0, '', '')
        with mock.patch.dict(os.environ, {'HERDR_ENV': '1'}), mock.patch.object(module.shutil, 'which', return_value='/bin/herdr'), mock.patch.object(module.subprocess, 'run', side_effect=fake_run):
            self.assertEqual(module.execute(self.config_with_launcher(), self.project, 'herdr'), 0)
        splits = [argv for argv in responses if argv[1:3] == ['pane', 'split'] and '--direction' in argv]
        directions = [argv[argv.index('--direction') + 1] for argv in splits]
        self.assertEqual(directions, ['right', 'down', 'right', 'down'])
        self.assertLess(min(rect['height'] for name, rect in rects.items() if name != 'base'), 200)
        self.assertGreaterEqual(min(rect['width'] for rect in rects.values()), module.MIN_WIDTH)
        self.assertTrue(any(argv[1:3] == ['pane', 'run'] and 'lazygit' in ' '.join(argv) for argv in responses))
        self.assertTrue(any(argv[1:3] == ['pane', 'run'] and str(self.project) in ' '.join(argv) for argv in responses))

    def test_mocked_accept_balances_roles_before_board_run(self):
        self.accepted()
        module = self.workspace_module
        help_result = subprocess.CompletedProcess([], 0, 'pane run --direction right|down\n', '')
        start_help = subprocess.CompletedProcess([], 0, '[possible values: codex]\n  --kind <KIND>\n  --pane <ID>', '')
        responses = []
        rects = {'base': {'width': 245.0, 'height': 59.0}}
        def fake_run(argv, **kwargs):
            responses.append(argv)
            if argv[-1] == '--help':
                return start_help if argv[1:3] == ['agent', 'start'] else help_result
            if argv[1:3] == ['pane', 'current']:
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'pane': {'pane_id': 'base', 'workspace_id': 'ws'}}}), '')
            if argv[1:3] == ['pane', 'layout']:
                pane_id = argv[-1]
                rect = rects[pane_id]
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'layout': {
                    'area': {'x': 0, 'y': 0, 'width': 245, 'height': 59},
                    'panes': [{'pane_id': pane_id, 'rect': {'x': 0, 'y': 0, **rect}}],
                }}}), '')
            if argv[1:3] == ['pane', 'list']:
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'panes': [{'pane_id': 'base'}]}}), '')
            if argv[1:2] == ['agent']:
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'agents': []}}), '')
            if argv[1:3] == ['pane', 'process-info']:
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'process_info': {'shell_pid': 42, 'foreground_processes': [{'pid': 42, 'command': 'zsh'}]}}}), '')
            if argv[1:3] == ['pane', 'split']:
                pane_id = f'p{sum(item[1:3] == ["pane", "split"] for item in responses)}'
                source = argv[argv.index('--pane') + 1]
                direction = argv[argv.index('--direction') + 1]
                source_rect = rects[source]
                rects[pane_id] = dict(source_rect)
                if direction == 'right':
                    rects[source]['width'] /= 2
                    rects[pane_id]['width'] /= 2
                else:
                    rects[source]['height'] /= 2
                    rects[pane_id]['height'] /= 2
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'pane': {'pane_id': pane_id}}}), '')
            return subprocess.CompletedProcess(argv, 0, '', '')
        with mock.patch.dict(os.environ, {'HERDR_ENV': '1'}), mock.patch.object(module.shutil, 'which', return_value='/bin/herdr'), mock.patch.object(module.subprocess, 'run', side_effect=fake_run):
            self.assertEqual(module.execute(self.config_with_launcher(), self.project, 'herdr'), 0)
        self.assertTrue(any(argv[1:3] == ['pane', 'run'] and 'render-ticket-dashboard.py' in ' '.join(argv)
                          for argv in responses))

    def config_with_launcher(self):
        config = self.config()
        config['harnesses'][0]['executable'] = 'codex'
        return config

    def test_mocked_partial_failure_reports_created_ids_and_diagnostic(self):
        self.accepted()
        module = self.workspace_module
        def fake_run(argv, **kwargs):
            if argv[-1] == '--help':
                text = '[possible values: codex] --kind <KIND> --pane <ID>' if argv[1:3] == ['agent', 'start'] else 'pane run --direction'
                return subprocess.CompletedProcess(argv, 0, text, '')
            if argv[1:3] == ['pane', 'current']:
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'pane': {'pane_id': 'base', 'workspace_id': 'ws'}}}), '')
            if argv[1:3] == ['pane', 'layout']:
                pane_id = argv[-1]
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'layout': {
                    'area': {'x': 0, 'y': 0, 'width': 120, 'height': 40},
                    'panes': [{'pane_id': pane_id, 'rect': {'x': 0, 'y': 0, 'width': 120, 'height': 40}}],
                }}}), '')
            if argv[1:3] == ['pane', 'list']:
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'panes': [{'pane_id': 'base'}]}}), '')
            if argv[1:2] == ['agent']:
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'agents': []}}), '')
            if argv[1:3] == ['pane', 'process-info']:
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'process_info': {'shell_pid': 42, 'foreground_processes': [{'pid': 42, 'command': 'zsh'}]}}}), '')
            if argv[1:3] == ['pane', 'split']:
                if any(item[1:3] == ['pane', 'split'] for item in calls):
                    return subprocess.CompletedProcess(argv, 1, '', 'split denied')
                calls.append(argv)
                return subprocess.CompletedProcess(argv, 0, json.dumps({'result': {'pane': {'pane_id': 'created-1'}}}), '')
            return subprocess.CompletedProcess(argv, 0, '', '')
        calls = []
        with mock.patch.dict(os.environ, {'HERDR_ENV': '1'}), mock.patch.object(module.shutil, 'which', return_value='/bin/herdr'), mock.patch.object(module.subprocess, 'run', side_effect=fake_run):
            with self.assertRaisesRegex(RuntimeError, r'created pane IDs: \[.created-1.\].*split denied'):
                module.execute(self.config_with_launcher(), self.project, 'herdr')


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

    def test_superseded_is_valid_terminal_state_in_all_projections(self):
        self.ticket('Superseded')
        self.dashboard('--validate')
        self.dashboard()
        html = (self.project / 'docs/tickets.html').read_text()
        markdown = (self.project / 'docs/tickets.md').read_text()
        self.assertIn('data-state="Superseded"', html)
        self.assertIn('state-superseded', html)
        self.assertIn('Superseded', markdown)
        self.assertIn('- **Superseded:** 1', markdown)
        terminal = self.dashboard('--terminal', '--width', '120', '--height', '12')
        self.assertIn('Superseded', terminal.stdout)
        self.assertIn('0 active', terminal.stdout)


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
