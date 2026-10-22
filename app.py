"""Standalone executable entry; default is a read-only statistics/control window."""
import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir')
    group = parser.add_mutually_exclusive_group()
    for flag in ('stats', 'start', 'ensure', 'worker', 'preview', 'doctor', 'stop', 'install-autostart', 'remove-autostart'):
        group.add_argument('--' + flag, action='store_true')
    parser.add_argument('--connect', action='store_true')
    parser.add_argument('--output')
    parser.add_argument('--screenshot')
    parser.add_argument('--close-after', type=int, help='Close statistics after N milliseconds (UI verification only)')
    args, rest = parser.parse_known_args()
    if args.data_dir:
        os.environ['CODEX_RETRY_DATA_DIR'] = str(Path(args.data_dir).expanduser().resolve())
    from app_config import DATA_DIR, ensure_data_dir, node_executable
    ensure_data_dir()
    if args.doctor:
        import json
        from doctor import diagnose
        report = diagnose(args.connect)
        Path(args.output or DATA_DIR / 'doctor.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return 0 if report['ok'] else 1
    if args.stop:
        (DATA_DIR / 'stop.request').write_text('manual stop', encoding='utf-8')
    elif args.install_autostart or args.remove_autostart:
        from startup import change_autostart
        change_autostart(args.remove_autostart)
    elif args.start or args.ensure:
        from lifecycle import mutex_exists, SUPERVISOR_MUTEX
        if args.start:
            (DATA_DIR / 'stop.request').unlink(missing_ok=True)
        if mutex_exists(SUPERVISOR_MUTEX):
            return 0
        from supervisor import main as supervise
        supervise()
    elif args.worker or args.preview:
        from retry_kitchen import main as worker
        sys.argv = [sys.argv[0], '--node', node_executable(), *(['--demo'] if args.preview else []), *rest]
        if args.screenshot:
            sys.argv += ['--screenshot', args.screenshot]
        worker()
    else:
        import ctypes
        import tkinter as tk
        from dashboard import Dashboard
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        root = tk.Tk()
        panel = Dashboard(root)
        if args.screenshot:
            root.lift()
            root.attributes('-topmost', True)
            def capture():
                from PIL import ImageGrab
                root.update_idletasks()
                x, y = root.winfo_rootx(), root.winfo_rooty()
                ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save(args.screenshot)
                root.attributes('-topmost', False)
            root.after(1000, capture)
        if args.close_after:
            root.after(args.close_after, panel.close)
        root.mainloop()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        import traceback
        from app_config import DATA_DIR, ensure_data_dir
        ensure_data_dir()
        (DATA_DIR / 'launch-error.log').write_text(traceback.format_exc(), encoding='utf-8')
        if not any(flag in sys.argv for flag in ('--ensure', '--worker')):
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(error), 'fxxk u tibo', 0x10)
        raise SystemExit(1)
