"""Build a source ZIP from an explicit allowlist; never include runtime state."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = '0.1.1'
FILES = '''
.gitignore .gitattributes LICENSE README.md README.zh-CN.md CHANGELOG.md
CONTRIBUTING.md SECURITY.md THIRD_PARTY_NOTICES.md requirements.txt
app_config.py doctor.py monitor.py desktop_bridge.cjs desktop_state.py
kitchen_art.py overlay.py retry_kitchen.py lifecycle.py supervisor.py
install.ps1 launch.ps1 install-autostart.ps1 Start.vbs Stop.vbs Preview.vbs
scripts/common.ps1 scripts/setup.ps1 scripts/doctor.ps1 scripts/stop.ps1 scripts/vbs-entry.ps1
scripts/test-scripts.ps1
test_monitor.py test_auto.py test_concurrency.py test_locking.py
test_supervisor.py test_portability.py test_bridge.cjs test_release.py
package_release.py
docs/compatibility.md docs/kitchen-contact-sheet.png docs/slogan-translations.md
assets/kitchen/manifest.json assets/kitchen/PROVENANCE.json
.github/workflows/test.yml .github/ISSUE_TEMPLATE/bug_report.yml
.github/ISSUE_TEMPLATE/feature_request.yml .github/ISSUE_TEMPLATE/config.yml
.github/pull_request_template.md
'''.split()


def release_files(root=ROOT):
    root = Path(root).resolve()
    manifest = json.loads((root / 'assets/kitchen/manifest.json').read_text(encoding='utf-8'))
    names = set(FILES)
    for item in manifest:
        relative = Path('assets/kitchen') / item['file']
        if relative.suffix != '.png' or relative.parts[:3] != ('assets', 'kitchen', 'sprites'):
            raise ValueError('Unexpected sprite path')
        names.add(relative.as_posix())
    paths = []
    for name in sorted(names):
        path = root / name
        if not path.is_file() or not path.resolve().is_relative_to(root) or path.is_symlink():
            raise ValueError(f'Missing or unsafe release file: {name}')
        paths.append(path)
    return paths


def build(root=ROOT, destination=None):
    root = Path(root).resolve()
    files = release_files(root)
    destination = Path(destination) if destination else root / 'dist'
    destination.mkdir(parents=True, exist_ok=True)
    prefix = f'fxxk-u-tibo-{VERSION}'
    archive = destination / f'{prefix}-windows-source.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for path in files:
            info = zipfile.ZipInfo(prefix + '/' + path.relative_to(root).as_posix(), (2026, 10, 22, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            package.writestr(info, path.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = destination / 'SHA256SUMS.txt'
    checksum.write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    return {'archive': str(archive), 'sha256': digest, 'files': len(files), 'bytes': archive.stat().st_size}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    print(json.dumps(build(destination=args.output), indent=2))
