"""Keep one retry worker alive; honor the user's persistent stop.request."""
import json
import ctypes
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import subprocess
import sys
import time

from lifecycle import acquire_mutex, close_mutex, mutex_exists, SUPERVISOR_MUTEX
from app_config import ROOT, DATA_DIR, ensure_data_dir, runtime_settings, codex_home, app_command

HERE = ROOT


def supervise(command, folder=DATA_DIR, worker_running=mutex_exists, poll=1.0, initial_delay=3.0):
    """Restart after any unrequested exit, even exit code zero."""
    folder = Path(folder)
    stop = folder / 'stop.request'
    failures = 0
    while not stop.exists():
        if worker_running():
            time.sleep(poll)  # An independently launched singleton owns the worker.
            continue
        started = time.monotonic()
        try:
            output = folder / 'worker-stderr.log'
            if output.exists() and output.stat().st_size > 1048576:
                output.replace(folder / 'worker-stderr.log.1')
            with output.open('ab', buffering=0) as stderr:
                if stop.exists():
                    break
                child = subprocess.Popen(command, cwd=folder, stdin=subprocess.DEVNULL,
                                         stdout=stderr, stderr=stderr,
                                         creationflags=subprocess.CREATE_NO_WINDOW)
                logging.info('Worker started pid=%s', child.pid)
                # The stop file is consumed by the worker after its current send finishes.
                code = child.wait()
            runtime = time.monotonic() - started
            logging.info('Worker exited pid=%s exit_code=%s runtime_seconds=%.2f stop_requested=%s',
                         child.pid, code, runtime, stop.exists())
        except Exception:
            runtime = time.monotonic() - started
            logging.exception('Worker launch/wait failed')
        if stop.exists():
            break
        failures = 1 if runtime >= 60 else min(failures + 1, 6)
        delay = min(60, initial_delay * 2 ** (failures - 1))
        logging.warning('Unexpected worker exit; restarting in %.1f seconds', delay)
        deadline = time.monotonic() + delay
        while time.monotonic() < deadline and not stop.exists():
            time.sleep(min(poll, max(0, deadline - time.monotonic())))
    logging.info('Supervisor stopped by stop.request')


def main():
    ensure_data_dir()
    handle = acquire_mutex(SUPERVISOR_MUTEX)
    if not handle:
        return
    logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(
        DATA_DIR / 'supervisor.log', maxBytes=1048576, backupCount=2, encoding='utf-8')],
        format='%(asctime)s %(levelname)s %(message)s')
    pid_file = DATA_DIR / 'supervisor.pid'
    try:
        settings = runtime_settings()
        home = str(codex_home())
        os.environ['CODEX_HOME'] = home
        os.environ['CODEX_RETRY_DATA_DIR'] = str(DATA_DIR)
        os.environ['CODEX_RETRY_LANGUAGE'] = settings.get('language', 'auto')
        # Manual stop lasts for this boot; reboot restores the user's autostart.
        ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
        boot_time = time.time() - ctypes.windll.kernel32.GetTickCount64() / 1000
        stop = DATA_DIR / 'stop.request'
        if stop.exists() and stop.stat().st_mtime < boot_time:
            stop.unlink()
        pid_file.write_text(str(os.getpid()), encoding='ascii')
        logging.info('Supervisor started pid=%s CODEX_HOME=%s', os.getpid(), home)
        supervise(app_command('--worker'))
    except Exception:
        logging.exception('Supervisor fatal error')
        raise
    finally:
        pid_file.unlink(missing_ok=True)
        close_mutex(handle)


if __name__ == '__main__':
    main()
