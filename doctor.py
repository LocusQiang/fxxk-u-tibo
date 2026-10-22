"""Read-only compatibility checks. Never submits a conversation message."""
import argparse
from contextlib import closing
import importlib
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys

from app_config import ROOT, DATA_DIR, codex_home, language, runtime_settings


def schema_check(home):
    required = {
        'state_5.sqlite': ('threads', {'id', 'source', 'rollout_path', 'archived'}),
        'thread_history_1.sqlite': ('thread_turns', {'thread_id', 'turn_id', 'status',
                                                  'error_json', 'started_at', 'completed_at', 'rollout_ordinal'}),
    }
    rows = []
    for filename, (table, columns) in required.items():
        path = Path(home) / filename
        if not path.exists():
            rows.append({'check': filename, 'status': 'error',
                         'detail': 'Not found; compatible Codex Desktop history is required. Open Codex or set -CodexHome'})
            continue
        try:
            with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)) as db:
                db.execute('PRAGMA query_only=ON')
                actual = {r[1] for r in db.execute(f'PRAGMA table_info({table})')}
            missing = sorted(columns - actual)
            rows.append({'check': filename, 'status': 'error' if missing else 'ok',
                         'detail': 'Unsupported schema: missing ' + ', '.join(missing) if missing else 'Expected columns present (read-only)'})
        except sqlite3.Error as error:
            rows.append({'check': filename, 'status': 'error', 'detail': str(error)})
    return rows


def diagnose(connect=False):
    checks = []
    def add(name, ok, detail):
        checks.append({'check': name, 'status': 'ok' if ok else 'error', 'detail': detail})
    add('platform', sys.platform == 'win32', platform.platform())
    add('python', (3, 11) <= sys.version_info[:2] <= (3, 14), platform.python_version() + '; supported range: 3.11-3.14')
    for module in ('tkinter', 'PIL'):
        try:
            imported = importlib.import_module(module)
            add(module, True, getattr(imported, '__version__', 'importable'))
        except ImportError:
            add(module, False, 'Missing; rerun install.ps1 with a Python installation that includes tkinter')
    settings = runtime_settings()
    node = settings.get('node') or shutil.which('node')
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    try:
        if not node:
            raise FileNotFoundError('Install Node.js 22 or newer and reopen PowerShell')
        result = subprocess.run([node, '--version'], capture_output=True, text=True, timeout=10, creationflags=flags, check=True)
        major = int(result.stdout.strip().lstrip('v').split('.')[0])
        add('node', major >= 22, result.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        add('node', False, str(error))
    home = codex_home()
    checks.extend(schema_check(home))
    try:
        manifest = json.loads((ROOT / 'assets/kitchen/manifest.json').read_text(encoding='utf-8'))
        valid = len(manifest) == 28 and all((ROOT / 'assets/kitchen' / item['file']).is_file() for item in manifest)
        add('assets', valid, f'{len(manifest)} kitchen sprites')
    except (OSError, ValueError, KeyError) as error:
        add('assets', False, str(error))
    if connect:
        try:
            if sys.platform != 'win32' or not node:
                raise RuntimeError('Windows and Node.js are required for the desktop pipe')
            result = subprocess.run([node, str(ROOT / 'desktop_bridge.cjs'), '--connect'], capture_output=True,
                                    text=True, encoding='utf-8', timeout=20, creationflags=flags)
            reply = json.loads(result.stdout.strip().splitlines()[-1])
            add('desktop_handshake', reply.get('connected') is True, 'Read-only initialization; no turn submitted'
                if reply.get('connected') else reply.get('error', 'Connection failed'))
        except (OSError, ValueError, IndexError, subprocess.SubprocessError, RuntimeError) as error:
            add('desktop_handshake', False, str(error))
    return {'ok': not any(c['status'] == 'error' for c in checks), 'checks': checks,
            'codex_home': str(home), 'runtime_directory': str(DATA_DIR), 'language': language(),
            'messages_sent': 0, 'note': 'Schema/connection checks do not prove end-to-end compatibility with other Codex versions.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connect', action='store_true', help='Also perform a read-only IPC initialization')
    parser.add_argument('--json', action='store_true', help='Output JSON (paths may be private; redact before sharing)')
    args = parser.parse_args()
    result = diagnose(args.connect)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for check in result['checks']:
            print(f"[{check['status'].upper()}] {check['check']}: {check['detail']}")
        print('CODEX_HOME:', result['codex_home'])
        print('Private runtime directory:', result['runtime_directory'])
        print(result['note'])
    raise SystemExit(0 if result['ok'] else 1)


if __name__ == '__main__':
    main()
