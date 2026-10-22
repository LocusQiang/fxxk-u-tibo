"""Build the unsigned Windows x64 standalone EXE from allowlisted sources.

Downloads the pinned official Node archive and verifies its official SHA256.
Build artifacts, downloads and licenses remain under build/ and dist/.
"""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

from package_release import ROOT, VERSION, release_files

NODE_VERSION = '22.20.0'


def download(url, destination):
    if not destination.exists():
        temporary = destination.with_suffix('.download')
        with urllib.request.urlopen(url, timeout=90) as response, temporary.open('wb') as stream:
            shutil.copyfileobj(response, stream)
        temporary.replace(destination)


def build():
    if sys.platform != 'win32':
        raise SystemExit('Build on Windows x64')
    build_dir = ROOT / 'build'
    os.environ['PYINSTALLER_CONFIG_DIR'] = str(build_dir / 'pyinstaller-cache')
    stage = build_dir / 'source'
    cache = build_dir / 'downloads'
    licenses = build_dir / 'licenses'
    for path in (stage, cache, licenses, ROOT / 'dist'):
        path.mkdir(parents=True, exist_ok=True)
    # Copy only explicit distributable files. No private workspace metadata.
    for source in release_files():
        dest = stage / source.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    archive_name = f'node-v{NODE_VERSION}-win-x64.zip'
    base = f'https://nodejs.org/dist/v{NODE_VERSION}/'
    archive, sums = cache / archive_name, cache / f'node-{NODE_VERSION}-SHASUMS256.txt'
    download(base + archive_name, archive)
    download(base + 'SHASUMS256.txt', sums)
    expected = next(line.split()[0] for line in sums.read_text().splitlines() if line.split()[-1] == archive_name)
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError('Official Node archive checksum mismatch')
    node_dir = build_dir / 'node'
    node_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        prefix = f'node-v{NODE_VERSION}-win-x64/'
        for name, target in [('node.exe', node_dir / 'node.exe'), ('LICENSE', licenses / 'Node-LICENSE.txt')]:
            target.write_bytes(bundle.read(prefix + name))
    # Preserve the complete dependency license files, including included codecs.
    for package in ('pillow', 'pystray', 'six', 'pyinstaller'):
        dist = importlib.metadata.distribution(package)
        for file in dist.files or []:
            if any(term in file.name.lower() for term in ('license', 'copying', 'notice')) and '.dist-info' in str(file):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    dest = licenses / package / Path(str(file))
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, dest)
    # Include the exact LGPL library's Python source alongside its license.
    tray = importlib.metadata.distribution('pystray')
    for file in tray.files or []:
        if str(file).startswith('pystray/') and str(file).endswith('.py'):
            dest = licenses / 'pystray-source' / Path(str(file))
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tray.locate_file(file), dest)
    python_root = Path(sys.base_prefix)
    python_license = python_root / 'LICENSE.txt'
    if not python_license.exists():
        raise FileNotFoundError('Python distribution must include LICENSE.txt')
    shutil.copy2(python_license, licenses / 'Python-LICENSE.txt')
    # Python's Windows Tcl/Tk distribution includes the upstream license.terms.
    for terms in (python_root / 'tcl').rglob('license.terms'):
        dest = licenses / 'tcl-tk' / terms.relative_to(python_root / 'tcl')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(terms, dest)
    if not list((licenses / 'tcl-tk').rglob('license.terms')):
        raise FileNotFoundError('Tcl/Tk license.terms were not found')
    from PIL import Image
    sprite = Image.open(stage / 'assets/kitchen/sprites/frying-pan.png').convert('RGBA')
    sprite.thumbnail((220, 220))
    icon = Image.new('RGBA', (256, 256))
    icon.alpha_composite(sprite, ((256 - sprite.width) // 2, (256 - sprite.height) // 2))
    icon_path = build_dir / 'kitchen.ico'
    icon.save(icon_path, sizes=[(16,16), (32,32), (48,48), (64,64), (256,256)])
    name = f'fxxk-u-tibo-{VERSION}-windows-x64'
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
               '--name', name, '--icon', str(icon_path), '--distpath', str(ROOT / 'dist'),
               '--workpath', str(build_dir / 'pyinstaller'), '--specpath', str(build_dir),
               '--paths', str(stage), '--hidden-import', 'pystray._win32',
               '--add-binary', f'{node_dir / "node.exe"};node']
    for source, target in [(stage / 'assets', 'assets'), (stage / 'desktop_bridge.cjs', '.'),
                           (stage / 'scripts/exe-autostart.ps1', 'scripts'),
                           (stage / 'LICENSE', '.'), (stage / 'THIRD_PARTY_NOTICES.md', '.'),
                           (licenses, 'licenses')]:
        command += ['--add-data', f'{source};{target}']
    command.append(str(stage / 'app.py'))
    subprocess.run(command, cwd=stage, check=True)
    with zipfile.ZipFile(ROOT / 'dist' / f'fxxk-u-tibo-{VERSION}-licenses.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(licenses.rglob('*')):
            if path.is_file():
                bundle.write(path, path.relative_to(licenses).as_posix())
    (ROOT / 'dist' / 'build-info.json').write_text(json.dumps({
        'version': VERSION, 'python': sys.version.split()[0], 'node': NODE_VERSION,
        'node_archive_sha256': actual, 'pyinstaller': importlib.metadata.version('pyinstaller'),
        'signed': False}, indent=2), encoding='utf-8')
    print(ROOT / 'dist' / (name + '.exe'))


if __name__ == '__main__':
    build()
