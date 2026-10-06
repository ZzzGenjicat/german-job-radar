"""Build an allowlisted, self-contained Windows release with license notices."""
import hashlib
import importlib.metadata
import os
import shutil
import ssl
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_release import release_files

NAME = 'GermanJobRadar-Windows-x64'


def license_notices():
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.is_file(): raise RuntimeError('CPython LICENSE.txt is required')
    parts = ['German Job Radar third-party notices\n', python_license.read_text(encoding='utf-8')]
    from lxml import etree
    parts.append(f'\nBundled runtime: Python {sys.version}; {ssl.OPENSSL_VERSION}; '
                 f'libxml2 {etree.LIBXML_VERSION}; libxslt {etree.LIBXSLT_VERSION}\n')
    parts.append((ROOT / 'packaging' / 'NATIVE_NOTICES.txt').read_text(encoding='utf-8'))
    for name in ('lxml', 'python-docx', 'pypdf', 'tzdata', 'typing_extensions', 'pyinstaller'):
        distribution = importlib.metadata.distribution(name)
        parts.append(f'\n\n=== {name} {distribution.version} ===\n')
        found = []
        for item in distribution.files or []:
            path = Path(distribution.locate_file(item))
            lower = str(item).lower()
            if path.is_file() and any(word in lower for word in ('license', 'copying', 'notice')):
                try:
                    text = path.read_text(encoding='utf-8')
                except UnicodeError: continue
                if text.strip(): found.append(text)
        if not found: raise RuntimeError(f'License text missing for {name}')
        parts.extend(found)
    return '\n'.join(parts)


def main():
    if os.name != 'nt' or sys.maxsize <= 2**32: raise RuntimeError('Build on 64-bit Windows')
    release_files(ROOT)  # fail before bundling if a release source contains obvious secrets
    dist = ROOT / 'dist'; dist.mkdir(exist_ok=True)
    notices = dist / 'THIRD_PARTY_NOTICES.txt'
    notices.write_text(license_notices(), encoding='utf-8')
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm',
                    '--distpath', str(dist), '--workpath', str(ROOT / 'build'),
                    str(ROOT / 'job-radar.spec')], cwd=ROOT, check=True)
    executable = dist / (NAME + '.exe')
    if not executable.is_file(): raise RuntimeError('Executable was not built')
    readme = dist / 'START_HERE.txt'
    readme.write_text((ROOT / 'docs' / 'WINDOWS.md').read_text(encoding='utf-8'), encoding='utf-8-sig')
    archive = dist / (NAME + '.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for path, target in ((executable, executable.name), (notices, notices.name),
                             (readme, readme.name), (ROOT / 'LICENSE', 'LICENSE')):
            bundle.write(path, NAME + '/' + target)
    checksums = dist / 'SHA256SUMS.txt'
    checksums.write_text(''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n'
                                for path in (executable, archive, notices)), encoding='ascii')
    print(f'Windows executable built: {executable.stat().st_size:,} bytes')


if __name__ == '__main__': main()
