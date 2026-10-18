"""Open the local interface in an isolated Edge/Chrome application window."""
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


def find_window_browser():
    candidates = []
    for variable in ('ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA'):
        root = os.environ.get(variable)
        if root:
            candidates.extend(Path(root) / relative for relative in (
                'Microsoft/Edge/Application/msedge.exe', 'Google/Chrome/Application/chrome.exe'))
    if os.name == 'nt':
        import winreg
        for name in ('msedge.exe', 'chrome.exe'):
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(hive, rf'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{name}') as key:
                        candidates.append(Path(winreg.QueryValue(key, None).strip('"')))
                except OSError:
                    pass
    return next((p for p in candidates if p.is_absolute() and p.is_file()), None)


def window_command(browser, origin, data):
    parts = urlsplit(origin)
    if (parts.scheme != 'http' or parts.hostname != '127.0.0.1' or parts.username or parts.password
            or not parts.port or parts.path not in ('', '/') or parts.query or parts.fragment):
        raise ValueError('应用窗口只允许打开本机界面')
    return [str(browser), f'--app={origin}', f'--user-data-dir={Path(data).resolve() / "window-profile"}',
            '--no-first-run', '--no-default-browser-check', '--window-size=1360,900']


def open_desktop_window(origin, data):
    browser = find_window_browser()
    if browser is None:
        raise RuntimeError('独立窗口需要已安装的 Microsoft Edge 或 Google Chrome')
    return subprocess.Popen(window_command(browser, origin, data), stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
