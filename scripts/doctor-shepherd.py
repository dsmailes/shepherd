#!/usr/bin/env python3
"""Read-only installation/transport checks; never launches agents or authenticates readiness."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


INSTALL_URL = 'https://herdr.dev/docs/install/'
REQUIRED_ROLES = {'architecture', 'implementation', 'review', 'testing', 'board'}
OPTIONAL_ROLES = {'design', 'sounding_board', 'critical_friend'}


def invoke(executable, arguments, timeout):
    """No shell, user prompts, retries, or fallback commands."""
    try:
        result = subprocess.run([executable, *arguments], stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f'Timed out after {timeout:g} seconds'
    except OSError as error:
        return None, str(error)
    if result.returncode:
        return None, f'Exit {result.returncode}: {result.stderr.strip() or result.stdout.strip()}'
    return result.stdout, None


def load_config(project):
    path = project / '.shepherd/project.json'
    try:
        config = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ValueError(f'Cannot read accepted project configuration {path}: {error}') from error
    if not isinstance(config, dict) or config.get('schema_version') != 1:
        raise ValueError('Expected project configuration schema_version 1')
    if config.get('allocation_accepted') is not True:
        raise ValueError('Role allocation has not been explicitly accepted')
    roster = config.get('harnesses')
    if not isinstance(roster, list) or not roster:
        raise ValueError('Accepted configuration needs a nonempty harness roster')
    seen = set()
    for entry in roster:
        if not isinstance(entry, dict) or not isinstance(entry.get('name'), str) or not entry['name'].strip():
            raise ValueError('Every declared harness needs a nonempty name')
        if entry['name'].casefold() in seen:
            raise ValueError('Duplicate declared harness name')
        seen.add(entry['name'].casefold())
        for field in ('executable', 'herdr_kind'):
            value = entry.get(field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f'{entry["name"]}: {field} must be nonempty text when declared')
    assignments = config.get('assignments')
    if not isinstance(assignments, dict) or not assignments:
        raise ValueError('Accepted configuration needs role assignments')
    missing = REQUIRED_ROLES - assignments.keys()
    unknown = assignments.keys() - REQUIRED_ROLES - OPTIONAL_ROLES
    if missing or unknown:
        raise ValueError(f'Invalid role assignments: missing {sorted(missing)}; unknown {sorted(unknown)}')
    names = {entry['name'] for entry in roster}
    if any(owner not in names for owner in assignments.values() if isinstance(owner, str)) or any(
            not isinstance(owner, str) for owner in assignments.values()):
        raise ValueError('Role assignments must reference declared harnesses')
    return config


def caller_identity(output):
    try:
        payload = json.loads(output)
        result = payload['result']
        pane = result['pane']
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError('Current-pane response does not contain result.pane') from error
    if not isinstance(result, dict) or result.get('type') != 'pane_current' or not isinstance(pane, dict):
        raise ValueError('Unexpected current-pane response shape/type')
    fields = ('pane_id', 'tab_id', 'workspace_id')
    if any(not isinstance(pane.get(field), str) or not pane[field].strip() for field in fields):
        raise ValueError('Current-pane response lacks caller pane/tab/workspace identity')
    # Canonical response identity may differ from stale HERDR_PANE_ID after a move.
    return {field: pane[field] for field in fields}


def supported_kinds(output):
    block = re.search(r'^[ \t]*--kind[ \t]+<[^>]+>[ \t]*$(.*?)(?=^[ \t]*--[a-z]|\Z)', output, re.S | re.M)
    values = re.search(r'\[possible values:\s*([^\]]+)\]', block.group(1), re.S) if block else None
    if not values:
        return None
    kinds = {value.strip() for value in values.group(1).split(',')}
    if not kinds or any(not re.fullmatch(r'[a-z][a-z0-9_-]*', value) for value in kinds):
        return None
    return kinds


def doctor(config, herdr, timeout, environment):
    checks = []

    def record(name, status, detail, **extra):
        checks.append(dict(name=name, status=status, detail=detail, **extra))

    executable = shutil.which(herdr)
    version_ok = False
    if not executable:
        record('herdr_cli', 'Blocked', f'Herdr executable unavailable. Install/setup guidance: {INSTALL_URL}')
    else:
        output, error = invoke(executable, ['--version'], timeout)
        if error or not output.strip():
            record('herdr_cli', 'Blocked', error or 'Herdr --version returned no version text')
        else:
            record('herdr_cli', 'Pass', output.strip(), executable=executable)
            version_ok = True

    inside = environment.get('HERDR_ENV') == '1'
    if not inside:
        record('herdr_environment', 'Blocked', 'Run doctor from a terminal inside Herdr. Do not set HERDR_ENV to bypass this gate; no caller/API check was attempted.')
    else:
        record('herdr_environment', 'Pass', 'HERDR_ENV=1 observed; caller/API connection still requires verification.')

    if version_ok and inside:
        output, error = invoke(executable, ['pane', 'current', '--current'], timeout)
        if error:
            record('caller_connection', 'Blocked', error)
        else:
            try:
                identity = caller_identity(output)
                record('caller_connection', 'Pass', 'Caller/API returned canonical identity.', identity=identity)
            except ValueError as error:
                record('caller_connection', 'Blocked', str(error))
    else:
        record('caller_connection', 'Unverified', 'Skipped: Herdr CLI/version and in-Herdr environment are required.')

    kinds = None
    if version_ok:
        # --help only: this does not start a process or inspect any pane/session.
        output, error = invoke(executable, ['agent', 'start', '--help'], timeout)
        if error:
            record('supported_kinds', 'Unverified', error)
        else:
            kinds = supported_kinds(output)
            if kinds is None:
                record('supported_kinds', 'Unverified', 'Installed --kind help format was not recognized; no kind catalog was assumed.')
            else:
                record('supported_kinds', 'Pass', 'Read installed agent start --help; no agent launch.', kinds=sorted(kinds))
    else:
        record('supported_kinds', 'Unverified', 'Skipped: Herdr CLI/version check did not pass.')

    for entry in config['harnesses']:
        name = entry['name']
        launcher = entry.get('executable')
        resolved = shutil.which(launcher) if launcher else None
        if not launcher:
            record(f'{name}:launcher', 'Unverified', 'No explicit launcher mapping; no executable name inferred.')
        elif not resolved:
            record(f'{name}:launcher', 'Blocked', f'Declared executable not found/executable: {launcher}')
        else:
            record(f'{name}:launcher', 'Pass', 'Declared executable resolves; it was not run.', executable=resolved)
        kind = entry.get('herdr_kind')
        if not kind:
            record(f'{name}:kind', 'Unverified', 'No explicit Herdr kind mapping; custom names are not inferred.')
        elif kinds is None:
            record(f'{name}:kind', 'Unverified', f'Cannot verify declared kind {kind} against installed help.')
        elif kind not in kinds:
            record(f'{name}:kind', 'Blocked', f'Declared kind {kind} is not supported by installed help.')
        else:
            record(f'{name}:kind', 'Pass', f'Declared kind {kind} appears in installed help; launcher/kind compatibility still needs live preflight.')

    passed = all(check['status'] == 'Pass' for check in checks)
    return dict(
        checks=checks,
        transport_checks_passed=passed,
        overall='Installation/transport checks passed; task readiness remains Unverified' if passed else
                'Blocked or Unverified installation/transport checks; task readiness remains Unverified',
        task_readiness='Unverified',
        unverified=['authentication', 'permissions and task tool access', 'launcher/kind runtime compatibility',
                    'independent worker identities', 'agent readiness', 'model activation'],
        limitations='Read-only local observations. Executable presence, environment variables and unauthenticated API responses do not authenticate workers or prove a task can run.'
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path('.'))
    parser.add_argument('--herdr', default='herdr', help='Explicit installed Herdr executable path or command name')
    parser.add_argument('--timeout', type=float, default=5, help='Per-command timeout in seconds (0 < n <= 60)')
    args = parser.parse_args()
    if not 0 < args.timeout <= 60:
        parser.error('--timeout must be greater than 0 and at most 60 seconds')
    try:
        config = load_config(args.project)
    except ValueError as error:
        print(json.dumps(dict(overall='Invalid or missing project setup', task_readiness='Unverified',
                              error=str(error)), indent=2))
        return 2
    result = doctor(config, args.herdr, args.timeout, os.environ)
    print(json.dumps(result, indent=2))
    return 0 if result['transport_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
