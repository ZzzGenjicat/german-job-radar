import tempfile
import unittest
from pathlib import Path


class ReleaseTests(unittest.TestCase):
    def test_release_uses_allowlist_and_excludes_private_files(self):
        from tools.build_release import release_files, build_release
        root = Path(__file__).resolve().parents[1]
        paths = release_files(root)
        for private in ('data/jobs.sqlite', 'sync_queue.py', 'radar/sheets.py', 'jd_audit.py', 'docs/sheets-sync.md', 'output/report.csv'):
            self.assertNotIn(private, paths)
        self.assertIn('LICENSE', paths)
        self.assertIn('setup.ps1', paths)
        self.assertIn('.github/workflows/tests.yml', paths)
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / 'public'
            build_release(root, destination)
            self.assertFalse((destination / 'data').exists())
            self.assertEqual(set(paths), {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()})

    def test_setup_and_launch_do_not_depend_on_codex_runtime(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('setup.ps1', 'launch.ps1', 'runtime.ps1', 'schedule.ps1'):
            text = (root / name).read_text(encoding='utf-8')
            self.assertNotIn('Administrator', text)
            self.assertNotIn('codex-runtimes', text)

    def test_build_refuses_nonempty_destination_and_private_source_paths(self):
        from tools.build_release import build_release
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / 'public'
            destination.mkdir()
            (destination / 'keep.txt').write_text('user data')
            with self.assertRaises(ValueError):
                build_release(root, destination)
            self.assertEqual((destination / 'keep.txt').read_text(), 'user data')
        with self.assertRaises(ValueError):
            build_release(root, root / 'data' / 'release')

    def test_google_sync_is_not_part_of_app_storage_api(self):
        from radar.store import Store
        self.assertFalse(hasattr(Store, 'enqueue'))
        self.assertFalse(hasattr(Store, 'acknowledge'))


if __name__ == '__main__':
    unittest.main()
