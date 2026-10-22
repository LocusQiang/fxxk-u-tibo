"""Portable paths and presentation settings; no credentials are read."""
import json
import locale
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INSTALL_DIR = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else ROOT
DATA_DIR = Path(os.environ.get('CODEX_RETRY_DATA_DIR', str(INSTALL_DIR / '.runtime'))).expanduser().resolve()


def node_executable():
    bundled = ROOT / 'node' / 'node.exe'
    return str(bundled) if bundled.is_file() else runtime_settings().get('node', 'node')


def app_command(*args):
    entry = [sys.executable] if getattr(sys, 'frozen', False) else [sys.executable, str(ROOT / 'app.py')]
    return [*entry, '--data-dir', str(DATA_DIR), *args]


def runtime_settings():
    path = DATA_DIR / 'runtime.json'
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}


def codex_home():
    return Path(runtime_settings().get('codex_home') or os.environ.get('CODEX_HOME')
                or str(Path.home() / '.codex')).expanduser().resolve()


def language():
    value = os.environ.get('CODEX_RETRY_LANGUAGE') or runtime_settings().get('language', 'auto')
    if value not in ('auto', 'en', 'zh'):
        raise ValueError('Language must be auto, en, or zh')
    if value != 'auto':
        return value
    current = locale.getlocale()[0] or ''
    fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    chinese_font = any((fonts / name).exists() for name in ('msyhbd.ttc', 'msyh.ttc', 'simhei.ttf'))
    return 'zh' if current.lower().startswith(('zh', 'chinese')) and chinese_font else 'en'


def translate(en, zh):
    return zh if language() == 'zh' else en


def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
