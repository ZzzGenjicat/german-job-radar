"""Local-only app and scheduled-task entrypoint."""
import argparse
import hashlib
import json
import logging
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from email import policy
from email.parser import BytesParser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from radar.core import BERLIN, now_utc
from radar.scan import DATA, DB, ROOT, AlreadyRunning, ScanLock, run_scan
from radar.sources import SOURCES, KEYWORDS, Fetcher, test_source
from radar.store import Store
from radar.security import validate_external_url
from radar.credentials import CredentialStore
from radar.cv import save_and_extract_cv
from radar.ai import OpenAIClient, FEEDBACK_CATEGORIES
from radar.export_csv import build_csv
from radar.presentation import numbered_jobs
from radar.runtime import FROZEN, INSTANCE_ID, app_port, credential_target
from radar.scheduling import read_schedule, scan_time, validate_time

PORT=app_port(os.environ)
ORIGIN=f'http://127.0.0.1:{PORT}'
APP_ID='german-job-radar-local-v1'
TOKEN=secrets.token_urlsafe(32)
STOP=threading.Event()
WORKER_GUARD=threading.Lock()
ACTIVE_WORKERS=set()
SCHEDULE_GUARD=threading.Lock()
CREDENTIAL_TARGET=credential_target(INSTANCE_ID,FROZEN)


class LocalHTTPServer(ThreadingHTTPServer):
    allow_reuse_address=False
    allow_reuse_port=False

    def server_bind(self):
        if os.name=='nt':
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        return super().server_bind()


def custom_source(data):
    if not isinstance(data,dict) or set(data)!= {'url','name'}:raise ValueError('自定义来源字段无效')
    if not all(isinstance(data.get(k),str) and data[k].strip() for k in ('url','name')):raise ValueError('请填写来源名称和网址')
    url=validate_external_url(data['url'].strip())
    parts=urlsplit(url)
    if parts.scheme!='https':raise ValueError('自定义来源必须使用 HTTPS')
    base=f'{parts.scheme}://{parts.netloc}'.rstrip('/')
    return {'id':'custom-'+hashlib.sha256(base.encode()).hexdigest()[:12],
            'name':data['name'].strip()[:100],'base':base,'kind':'regional'}


def due(now=None):
    config=read_schedule(DATA)
    if not config['installed']:return False
    now=now or now_utc();local=now.astimezone(BERLIN)
    if local.weekday()>=5 or local.time().replace(tzinfo=None)<scan_time(config['time']):return False
    store=Store(DB);view=store.view(now)
    if store.scheduled_today(local.date().isoformat()):return False
    attempt=view['latest_attempt']
    if attempt:
        age=now-datetime.fromisoformat(attempt['started'])
        if age<timedelta(minutes=30) and attempt['kind'] in ('scheduled','catchup'):return False
    return True


def scan_background(kind):
    def work():
        try:run_scan(kind)
        except AlreadyRunning:pass
        except Exception:logging.exception('scan failed')
        finally:
            with WORKER_GUARD:ACTIVE_WORKERS.discard(threading.current_thread())
    with WORKER_GUARD:
        if STOP.is_set():return False
        worker=threading.Thread(target=work,daemon=True)
        ACTIVE_WORKERS.add(worker)
        worker.start()
    return True


def begin_shutdown():
    with WORKER_GUARD:
        if ACTIVE_WORKERS:raise ValueError('正在扫描，请等扫描完成后退出')
        try:
            with ScanLock():STOP.set()
        except AlreadyRunning:raise ValueError('正在扫描，请等扫描完成后退出') from None


def automatic_loop():
    while not STOP.wait(30):
        if due():scan_background('scheduled')


class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args):logging.info(fmt,*args)
    def valid_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{PORT}',f'localhost:{PORT}')
    def respond(self,status,data,content_type='application/json; charset=utf-8'):
        if isinstance(data,(dict,list)):data=json.dumps(data,ensure_ascii=False).encode('utf-8')
        if isinstance(data,str):data=data.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if not self.valid_host():return self.respond(403,{'error':'仅允许本机访问'})
        path=urlsplit(self.path).path
        if path=='/api/health':return self.respond(200,{'app':APP_ID,'instance':INSTANCE_ID,'pid':os.getpid()})
        if path=='/third-party-notices.txt' and FROZEN:
            return self.respond(200,(ROOT/'THIRD_PARTY_NOTICES.txt').read_bytes(),'text/plain; charset=utf-8')
        if path=='/api/state':
            store=Store(DB);store.ensure_v2_configuration(KEYWORDS,SOURCES)
            value=store.view(now_utc());value.pop('sync_queue',None)
            value['expansion']=store.expansion_settings()
            if value.get('snapshot'):value['snapshot']['jobs']=numbered_jobs(value['snapshot'].get('jobs',[]))
            value.update(token=TOKEN,sources=store.source_settings(),keywords=store.keywords(),profile=store.profile(),learned_rules=store.learned_rules(),openai=CredentialStore().status(CREDENTIAL_TARGET),cv=store.current_cv())
            value['schedule']=read_schedule(DATA)
            value['schedule_supported']=os.name=='nt'
            value['desktop_packaged']=FROZEN
            return self.respond(200,value)
        files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8'),'/favicon.svg':('favicon.svg','image/svg+xml')}
        if path not in files:return self.respond(404,{'error':'页面不存在'})
        filename,typ=files[path]
        return self.respond(200,(ROOT/'web'/filename).read_bytes(),typ)
    def do_POST(self):
        if not self.valid_host():return self.respond(403,{'error':'仅允许本机访问'})
        if self.headers.get('Origin')!=ORIGIN or not secrets.compare_digest(self.headers.get('X-Radar-Token',''),TOKEN):
            return self.respond(403,{'error':'请从应用页面发起更新'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            limit=9*1024*1024 if self.path=='/api/cv' else 16384
            if size<0 or size>limit:return self.respond(413,{'error':'请求过大'})
            raw=self.rfile.read(size) if size else b''
            if self.path=='/api/cv':
                content_type=self.headers.get('Content-Type','')
                if not content_type.lower().startswith('multipart/form-data'):raise ValueError('请上传 PDF 或 DOCX 文件')
                message=BytesParser(policy=policy.default).parsebytes(b'Content-Type: '+content_type.encode('ascii')+b'\r\nMIME-Version: 1.0\r\n\r\n'+raw)
                part=next((p for p in message.iter_parts() if p.get_param('name',header='content-disposition')=='file'),None)
                if part is None or not part.get_filename():raise ValueError('没有收到简历文件')
                store=Store(DB);old=store.current_cv()
                result=save_and_extract_cv(part.get_filename(),part.get_payload(decode=True) or b'',DATA/'cv')
                store.set_cv(result)
                if old and old.get('stored_name')!=result['stored_name']:
                    previous=(DATA/'cv'/old['stored_name']).resolve()
                    if previous.parent==(DATA/'cv').resolve() and previous.exists():previous.unlink()
                return self.respond(200,store.current_cv())
            data=json.loads(raw) if raw else {}
            if self.path=='/api/schedule':
                if not isinstance(data,dict) or set(data)!= {'enabled','time'} or type(data['enabled']) is not bool:raise ValueError('自动搜索设置字段无效')
                configure_schedule(data['enabled'],data['time'])
                return self.respond(200,{'schedule':read_schedule(DATA),'message':f"已保存：工作日德国时间 {data['time']} 自动搜索" if data['enabled'] else f"自动搜索已停用，时间 {data['time']} 已保存"})
            if self.path=='/api/desktop/quit':
                if not FROZEN or data:raise ValueError('此操作只用于 Windows 下载版')
                begin_shutdown()
                self.respond(200,{'message':'应用已退出，可关闭这个页面'})
                threading.Thread(target=self.server.shutdown,daemon=True).start()
                return
            if self.path=='/api/scan':
                if not scan_background('manual'):raise ValueError('应用正在退出')
                return self.respond(202,{'message':'近24小时扫描已启动'})
            if self.path=='/api/display':
                if type(data.get('only_new')) is not bool:raise ValueError('请选择显示规则')
                value=Store(DB).preference({'only_new':data['only_new'],'confirmed':True})
                return self.respond(200,value)
            if self.path=='/api/export.csv':
                if data:raise ValueError('导出请求不接受额外字段')
                snapshot=Store(DB).view(now_utc()).get('snapshot') or {}
                jobs=numbered_jobs(snapshot.get('jobs',[]))
                return self.respond(200,build_csv(jobs),'text/csv; charset=utf-8')
            store=Store(DB);store.ensure_v2_configuration(KEYWORDS,SOURCES)
            if self.path=='/api/profile':
                return self.respond(200,store.profile(data))
            if self.path=='/api/expansion':
                return self.respond(200,store.expansion_settings(data))
            if self.path=='/api/keywords':
                if set(data)!= {'term','enabled'}:raise ValueError('关键词字段无效')
                return self.respond(200,store.put_keyword(data['term'],data['enabled']))
            if self.path=='/api/keywords/update':
                if set(data)!= {'id','term','enabled'}:raise ValueError('关键词字段无效')
                return self.respond(200,store.update_keyword(data['id'],data['term'],data['enabled']))
            if self.path=='/api/keywords/delete':
                if set(data)!= {'id'}:raise ValueError('关键词字段无效')
                store.delete_keyword(data['id']);return self.respond(200,{'message':'关键词已删除'})
            if self.path=='/api/sources/toggle':
                if set(data)!= {'id','enabled'}:raise ValueError('来源字段无效')
                return self.respond(200,store.set_source_enabled(data['id'],data['enabled']))
            if self.path=='/api/sources/test':
                if set(data)=={'id'}:
                    source=next((s for s in store.source_settings() if s['id']==data['id']),None)
                    if not source:raise ValueError('来源不存在')
                else:
                    source=custom_source(data)
                keyword=next((k['term'] for k in store.keywords() if k['enabled']),'Praktikum KI')
                result=test_source(source,keyword,Fetcher())
                if set(data)=={'id'}:store.set_source_test(source['id'],result)
                return self.respond(200,{'source':source,'test':result})
            if self.path=='/api/sources/custom':
                source=custom_source(data)
                keyword=next((k['term'] for k in store.keywords() if k['enabled']),'Praktikum KI')
                result=test_source(source,keyword,Fetcher())
                if result['status']!='supported':raise ValueError(result['message'])
                return self.respond(200,store.add_custom_source(source,result))
            if self.path=='/api/openai/credential':
                if set(data)!= {'api_key'}:raise ValueError('凭据字段无效')
                CredentialStore().set(CREDENTIAL_TARGET,data['api_key'])
                return self.respond(200,{'configured':True,'message':'OpenAI 凭据已安全保存'})
            if self.path=='/api/openai/delete':
                if data:raise ValueError('删除凭据不接受额外字段')
                CredentialStore().delete(CREDENTIAL_TARGET)
                return self.respond(200,{'configured':False,'message':'OpenAI 凭据已删除'})
            if self.path=='/api/cv/delete':
                if data:raise ValueError('删除简历不接受额外字段')
                current=store.current_cv()
                if current:
                    path=(DATA/'cv'/current['stored_name']).resolve()
                    if path.parent==(DATA/'cv').resolve() and path.exists():path.unlink()
                store.clear_cv();return self.respond(200,{'message':'本机简历已删除'})
            if self.path=='/api/cv/analyze':
                if data:raise ValueError('分析请求不接受额外字段')
                current=store.current_cv(include_text=True)
                if not current:raise ValueError('请先上传简历')
                client=OpenAIClient(lambda:CredentialStore().get(CREDENTIAL_TARGET))
                return self.respond(200,client.generate_keyword_draft(current['text'],store.profile()))
            if self.path=='/api/cv/apply-keywords':
                if set(data)!= {'keywords'} or not isinstance(data['keywords'],list) or len(data['keywords'])>50:raise ValueError('关键词选择无效')
                added=[]
                existing={k['term'].casefold() for k in store.keywords()}
                for term in data['keywords']:
                    if not isinstance(term,str):raise ValueError('关键词选择无效')
                    if term.strip().casefold() not in existing:
                        added.append(store.put_keyword(term.strip()));existing.add(term.strip().casefold())
                return self.respond(200,{'added':added,'message':f'已添加 {len(added)} 个关键词'})
            if self.path=='/api/feedback/analyze':
                if set(data)!= {'scan_id','job_key','category','note'}:raise ValueError('反馈字段无效')
                if data['category'] not in FEEDBACK_CATEGORIES or not isinstance(data['note'],str) or len(data['note'])>1000:raise ValueError('反馈原因无效')
                job=store.snapshot_job(data['scan_id'],data['job_key'])
                profile_summary={'profile':store.profile()}
                client=OpenAIClient(lambda:CredentialStore().get(CREDENTIAL_TARGET))
                rule=client.generate_feedback_rule(job,{'category':data['category'],'note':data['note']},profile_summary,[r['rule'] for r in store.learned_rules() if r['enabled']])
                return self.respond(200,{'scan_id':data['scan_id'],'job_key':data['job_key'],'rule':rule})
            if self.path=='/api/feedback/accept':
                if set(data)!= {'scan_id','job_key','rule'}:raise ValueError('反馈确认字段无效')
                store.snapshot_job(data['scan_id'],data['job_key'])
                saved=store.add_learned_rule(data['rule'],data['job_key'])
                return self.respond(200,{'rule':saved,'message':'偏好规则已保存并应用'})
            if self.path=='/api/rules/update':
                if set(data)!= {'id','rule','enabled'}:raise ValueError('偏好规则字段无效')
                return self.respond(200,store.update_learned_rule(data['id'],data['rule'],data['enabled']))
            if self.path=='/api/rules/delete':
                if set(data)!= {'id'}:raise ValueError('偏好规则字段无效')
                store.delete_learned_rule(data['id']);return self.respond(200,{'message':'偏好规则已删除'})
            if self.path=='/api/open-external':
                url=validate_external_url(data.get('url'))
                threading.Thread(target=webbrowser.open,args=(url,),kwargs={'new':2},daemon=True).start()
                return self.respond(202,{'message':'已在默认浏览器打开'})
            return self.respond(404,{'error':'操作不存在'})
        except (ValueError,TypeError,KeyError) as exc:return self.respond(400,{'error':str(exc) or '请求无效，请刷新后重试'})
        except (RuntimeError,OSError) as exc:return self.respond(502,{'error':str(exc)})


def serve():
    DATA.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=DATA/'app.log',level=logging.INFO,encoding='utf-8',format='%(asctime)s %(levelname)s %(message)s')
    server=LocalHTTPServer(('127.0.0.1',PORT),Handler)
    store=Store(DB);store.migrate_history();store.ensure_v2_configuration(KEYWORDS,SOURCES)
    try:
        with ScanLock():store.abandon_running()
    except AlreadyRunning:pass
    if due():scan_background('catchup')
    threading.Thread(target=automatic_loop,daemon=True).start()
    try:server.serve_forever()
    finally:STOP.set();server.server_close()


def healthy():
    try:
        with urllib.request.urlopen(ORIGIN+'/api/health',timeout=1) as r:
            value=json.load(r)
            return value.get('app')==APP_ID and value.get('instance')==INSTANCE_ID
    except Exception:return False


def open_app(open_browser=True):
    if not healthy():
        env=os.environ.copy()
        env['JOB_RADAR_DATA_DIR']=str(DATA)
        if getattr(sys,'frozen',False):
            command=[sys.executable,'--serve']
            working=Path(sys.executable).parent
            env['PYINSTALLER_RESET_ENVIRONMENT']='1'
        else:
            executable=Path(sys.executable).with_name('pythonw.exe')
            command=[str(executable if executable.exists() else sys.executable),str(ROOT/'app.py'),'--serve']
            working=ROOT
        subprocess.Popen(command,cwd=working,env=env,
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,
                         stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(80):
            if healthy():break
            time.sleep(.25)
        else:raise RuntimeError(f'本地服务未启动，请查看 {DATA / "app.log"}；端口 {PORT} 可能被另一安装占用，请先退出旧版本')
    if open_browser:webbrowser.open(ORIGIN)


def configure_schedule(enabled,schedule_time):
    validate_time(schedule_time)
    if type(enabled) is not bool:raise ValueError('自动搜索开关无效')
    if os.name!='nt':raise ValueError('自动搜索计划任务目前仅支持 Windows')
    command=[str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),
             '-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'schedule.ps1'),'-DataDirectory',str(DATA),'-Time',schedule_time]
    if FROZEN:command.extend(['-Executable',sys.executable])
    if not enabled:command.append('-Remove')
    env=os.environ.copy();env['JOB_RADAR_PYTHON']=sys.executable
    try:
        # PowerShell's filesystem provider can misresolve a Unicode working
        # directory reached through a Windows short-name TEMP alias. Use the
        # known resource directory instead of inheriting the launch directory.
        with SCHEDULE_GUARD:result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired:raise RuntimeError('更新计划任务超时，请稍后重试') from None
    if result.returncode:
        logging.error('Schedule update failed: %s',result.stderr.decode('utf-8',errors='replace'))
        raise RuntimeError('无法更新 Windows 计划任务，请查看本机日志')


def main():
    p=argparse.ArgumentParser();p.add_argument('--serve',action='store_true');p.add_argument('--scan',action='store_true');p.add_argument('--due',action='store_true');p.add_argument('--open',action='store_true');p.add_argument('--no-browser',action='store_true');p.add_argument('--self-test',type=Path);p.add_argument('--data-dir',type=Path)
    args=p.parse_args()
    if args.self_test:
        from radar.diagnostics import self_test
        self_test(args.self_test)
    elif args.serve:serve()
    elif args.scan or args.due:
        if args.due and not due():return
        try:
            result=run_scan('scheduled' if args.due else 'manual')
            if sys.stdout:print(json.dumps(result,ensure_ascii=True))
            if result['status']=='failed':raise SystemExit(1)
        except AlreadyRunning:return
    else:open_app(open_browser=not args.no_browser)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        DATA.mkdir(parents=True,exist_ok=True)
        logging.basicConfig(filename=DATA/'app.log',level=logging.INFO,encoding='utf-8')
        logging.exception('Application startup failed')
        if FROZEN and '--self-test' not in sys.argv:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,f'{exc}\n\n日志：{DATA / "app.log"}','德国岗位雷达',0x10)
        raise SystemExit(1)
