"""Build public source through an explicit allowlist, never runtime data."""
import argparse
import re
import shutil
import zipfile
from pathlib import Path

TOP_LEVEL = ('app.py', 'setup.ps1', 'runtime.ps1', 'launch.ps1', 'schedule.ps1',
             '打开德国岗位雷达.cmd', 'requirements.txt', 'requirements-dev.txt',
             'README.md', 'LICENSE', '.gitignore', 'CONTRIBUTING.md', 'SECURITY.md', 'requirements-build.txt', 'job-radar.spec')
MODULES = ('__init__', 'ai', 'config', 'core', 'credentials', 'cv', 'expansion', 'export_csv',
           'feedback', 'http_fetch', 'presentation', 'scan', 'security', 'sources', 'store', 'terms', 'runtime', 'diagnostics')
TESTS = ('ai', 'app_api', 'config', 'core', 'credentials', 'cv', 'due', 'expansion', 'export_csv',
         'external', 'feedback', 'http_fetch', 'incremental', 'public_features', 'release', 'server', 'sources', 'store', 'desktop', 'schedule_script')
FIXTURES = ('regional-search', 'regional-repost', 'ba-search', 'ba-detail')


def release_files(root):
    root = Path(root).resolve()
    files = list(TOP_LEVEL)
    files += [f'radar/{name}.py' for name in MODULES]
    files += [f'tests/test_{name}.py' for name in TESTS]
    files += [f'tests/fixtures/synthetic-{name}.html' for name in FIXTURES]
    files += ['web/index.html', 'web/app.js', 'web/style.css', 'web/favicon.svg',
              'tools/__init__.py', 'tools/build_release.py', 'tools/build_exe.py', 'tools/smoke_exe.py',
              'docs/USAGE.zh-CN.md', 'docs/WINDOWS.md', 'docs/RELEASE.md', 'packaging/NATIVE_NOTICES.txt', '.github/workflows/tests.yml', '.github/workflows/release.yml']
    for name in files:
        path = root / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError(f'Unsafe or missing release file: {name}')
        text = path.read_text(encoding='utf-8-sig')
        if re.search(r'sk-(?:proj-)?[A-Za-z0-9_-]{25,}|C:[\\/]+Users[\\/]+Administrator|\b1-[A-Za-z0-9_-]{30,}\b', text, re.I):
            raise ValueError(f'Possible private data in release file: {name}')
    return sorted(files)


def build_release(root, destination, archive=None):
    root = Path(root).resolve(); destination = Path(destination).resolve()
    if destination.is_relative_to(root) or root.is_relative_to(destination):
        raise ValueError('Release destination must be outside the source tree')
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError('Release destination must be empty; existing files are preserved')
    files = release_files(root)
    if archive is not None:
        archive = Path(archive).resolve()
        if archive.exists() or archive.is_relative_to(root) or archive.is_relative_to(destination):
            raise ValueError('Archive must be a new path outside source and destination')
    for name in files:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, target)
    if archive is not None:
        archive.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
            for name in files:
                z.write(destination / name, destination.name + '/' + name)
    return files


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--zip', type=Path)
    args = parser.parse_args()
    files = build_release(Path(__file__).resolve().parents[1], args.destination, args.zip)
    print(f'Public release prepared: {len(files)} files')
