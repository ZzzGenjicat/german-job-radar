"""Run the built EXE with no external Python and isolated synthetic user data."""
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docx import Document
from reportlab.pdfgen import canvas


def smoke(executable):
    with tempfile.TemporaryDirectory(prefix='Job Radar 测试 空格 ') as folder:
        root = Path(folder); exe = root / '岗位雷达.exe'
        shutil.copy2(executable, exe)
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
        env = os.environ.copy()
        for key in ('PYTHONPATH', 'PYTHONHOME'): env.pop(key, None)
        env['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        data_dir = root / '用户数据'
        env.pop('JOB_RADAR_DATA_DIR', None)
        env['JOB_RADAR_PORT'] = str(port)
        origin = f'http://127.0.0.1:{port}'
        report = root / 'checks.json'
        subprocess.run([str(exe), '--self-test', str(report)], env=env, cwd=root, check=True, timeout=45)
        checks = json.loads(report.read_text(encoding='utf-8'))
        assert checks['ok'] and checks['checks']['frozen'], checks
        token = None

        def request(path, data=None, content_type='application/json'):
            headers = {'Origin': origin}
            if token: headers['X-Radar-Token'] = token
            if data is not None:
                headers['Content-Type'] = content_type
                if not isinstance(data, bytes): data = json.dumps(data).encode()
            req = urllib.request.Request(origin + path, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read(), response.headers

        def start():
            subprocess.run([str(exe), '--data-dir', str(data_dir), '--no-browser'], env=env, cwd=root, check=True, timeout=40)
            return json.loads(request('/api/health')[0])

        def stop():
            request('/api/desktop/quit', {})
            for _ in range(100):
                try: request('/api/health')
                except (OSError, urllib.error.URLError): break
                time.sleep(.1)
            else: raise AssertionError('Service did not stop')
            # The onefile supervisor can outlive its HTTP child while cleaning up.
            # Windows only permits replacing the EXE after both have exited.
            for _ in range(100):
                try:
                    with exe.open('r+b'): pass
                    return
                except PermissionError: time.sleep(.1)
            raise AssertionError('EXE is still running and cannot be replaced')

        started = False
        try:
            first = start(); started = True
            assert start()['pid'] == first['pid'], 'Repeated launch spawned another service'
            page, headers = request('/')
            assert '搜索设置' in page.decode('utf-8')
            assert "frame-ancestors 'none'" in headers['Content-Security-Policy']
            notices, _ = request('/third-party-notices.txt')
            assert all(name in notices.decode('utf-8') for name in ('OpenSSL', 'libffi', 'libxml2', 'libxslt'))
            state = json.loads(request('/api/state')[0]); token = state['token']
            assert state['desktop_packaged'] and not state['snapshot'] and not state['cv']
            try:
                urllib.request.urlopen(urllib.request.Request(origin + '/api/desktop/quit', data=b'{}'), timeout=5)
            except urllib.error.HTTPError as error: assert error.code == 403
            else: raise AssertionError('Unauthenticated shutdown was accepted')
            request('/api/keywords', {'term': 'SyntheticSmokeKeyword', 'enabled': True})
            document = Document(); document.add_paragraph('Synthetic CRM Agent resume')
            stream = io.BytesIO(); document.save(stream)
            pdfstream = io.BytesIO(); pdf = canvas.Canvas(pdfstream)
            pdf.drawString(72, 720, 'Synthetic PDF Automation'); pdf.save()
            for filename, content, expected in (('synthetic.docx', stream.getvalue(), 'CRM Agent'),
                                                ('synthetic.pdf', pdfstream.getvalue(), 'PDF Automation')):
                boundary = 'jobradarsmoke'
                body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + content + f'\r\n--{boundary}--\r\n'.encode())
                request('/api/cv', body, f'multipart/form-data; boundary={boundary}')
                current = json.loads(request('/api/state')[0])['cv']
                assert current['chars'] > 0
                stored = data_dir / 'cv' / current['stored_name']
                assert stored.is_file()
                from radar.store import Store
                assert expected in Store(data_dir / 'jobs.sqlite').current_cv(include_text=True)['text']
            request('/api/cv/delete', {})
            csv, _ = request('/api/export.csv', {})
            assert csv.startswith(b'\xef\xbb\xbf') and '只作为建议' in csv.decode('utf-8-sig')
            stop(); started = False
            start(); started = True
            state = json.loads(request('/api/state')[0]); token = state['token']
            assert any(k['term'] == 'SyntheticSmokeKeyword' for k in state['keywords'])
            assert not state['cv']
            assert not state['schedule']['installed'] and not state['snapshot']
            stop(); started = False
        finally:
            if started:
                try: stop()
                except Exception: pass
    print('Frozen smoke passed: Python-free launch, Unicode path, embedded assets/TLS context/timezone/CV/SQLite, single service, protected API, CSV, persistent settings and clean restart.')


if __name__ == '__main__': smoke(Path(sys.argv[1]).resolve())
