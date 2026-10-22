"""Opt-in per-user scheduled task; never silently replace another installation."""
import os
from pathlib import Path
import subprocess
import sys
from app_config import ROOT, DATA_DIR

TASK_NAME = 'FxxkUTibo'


def powershell():
    return str(Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe')


def task_operation(action):
    if not getattr(sys, 'frozen', False):
        raise RuntimeError('Use install-autostart.ps1 for a source checkout. The dashboard startup control requires the EXE.')
    args = [powershell(), '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden',
            '-ExecutionPolicy', 'RemoteSigned', '-File', str(ROOT / 'scripts/exe-autostart.ps1'),
            '-Exe', sys.executable, '-DataDir', str(DATA_DIR), '-Action', action]
    result = subprocess.run(args, capture_output=True, timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace').strip() or 'Startup operation failed')
    return result.stdout.decode('utf-8-sig', errors='replace').strip()


def autostart_installed():
    return task_operation('Status') == 'installed'


def change_autostart(remove=False):
    return task_operation('Remove' if remove else 'Install')
