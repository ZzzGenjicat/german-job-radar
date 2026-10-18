"""The Windows launcher opens only the local app in its own window."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class WindowTests(unittest.TestCase):
    def test_default_open_uses_a_standalone_window(self):
        with patch.object(app, 'healthy', return_value=True), patch('app.webbrowser.open') as browser, patch.object(app, 'open_desktop_window', create=True) as window:
            app.open_app()
        browser.assert_not_called()
        window.assert_called_once_with(app.ORIGIN, app.DATA)

    def test_window_command_uses_a_separate_profile_and_preserves_safety(self):
        from radar.desktop import window_command
        with tempfile.TemporaryDirectory(prefix='radar window ') as tmp:
            command = window_command(Path('C:/Program Files/Edge/msedge.exe'), 'http://127.0.0.1:48218', Path(tmp))
            self.assertIn('--app=http://127.0.0.1:48218', command)
            self.assertIn('--user-data-dir=' + str(Path(tmp).resolve() / 'window-profile'), command)
            self.assertFalse(any('disable-web-security' in part or 'no-sandbox' in part or 'remote-debugging' in part for part in command))

    def test_window_rejects_external_or_credential_urls(self):
        from radar.desktop import window_command
        for url in ('https://example.test', 'file:///C:/private', 'http://user@127.0.0.1:48218', 'http://127.0.0.1:48218/?next=remote'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                window_command(Path('C:/Edge/msedge.exe'), url, Path('C:/data'))

    def test_missing_window_browser_is_an_explicit_error(self):
        from radar.desktop import open_desktop_window
        with patch('radar.desktop.find_window_browser', return_value=None), patch('radar.desktop.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'Edge|Chrome'):
                open_desktop_window('http://127.0.0.1:48218', Path('C:/data'))
        spawn.assert_not_called()


if __name__ == '__main__':
    unittest.main()
