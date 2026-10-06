from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH)
datas = [(str(root / 'web' / name), 'web') for name in ('index.html', 'app.js', 'style.css', 'favicon.svg')]
datas += [(str(root / 'schedule.ps1'), '.')]
datas += [(str(root / 'dist' / 'THIRD_PARTY_NOTICES.txt'), '.')]
datas += collect_data_files('docx') + collect_data_files('tzdata')
a = Analysis([str(root / 'app.py')], pathex=[str(root)], datas=datas,
             hiddenimports=['ctypes.wintypes'], excludes=['tkinter', 'reportlab', 'PIL'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='GermanJobRadar-Windows-x64',
          debug=False, strip=False, upx=False, console=False)
