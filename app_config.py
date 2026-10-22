"""Portable paths and presentation settings; no credentials are read."""
import json
import locale
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get('CODEX_RETRY_DATA_DIR', str(ROOT / '.runtime'))).expanduser().resolve()


def runtime_settings():
    path = DATA_DIR / 'runtime.json'
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}


def codex_home():
    return Path(os.environ.get('CODEX_HOME') or runtime_settings().get('codex_home')
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
