import copy
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from .core import BERLIN, edition_for, canonical_url, now_utc


class Store:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS scans(
                  id TEXT PRIMARY KEY, started TEXT NOT NULL, finished TEXT,
                  edition_date TEXT, kind TEXT, status TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS scans_date ON scans(started);
                CREATE TABLE IF NOT EXISTS recommendations(
                  job_key TEXT PRIMARY KEY, first_at TEXT NOT NULL, last_at TEXT NOT NULL, title TEXT);
                CREATE TABLE IF NOT EXISTS sightings(
                  job_key TEXT PRIMARY KEY,first_at TEXT NOT NULL,first_run TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS aliases(alias TEXT PRIMARY KEY,job_key TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings(name TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS keywords(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,term TEXT NOT NULL,norm TEXT NOT NULL UNIQUE,
                  enabled INTEGER NOT NULL DEFAULT 1,position INTEGER NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS source_settings(
                  id TEXT PRIMARY KEY,payload TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,
                  custom INTEGER NOT NULL DEFAULT 0,last_test TEXT);
                CREATE TABLE IF NOT EXISTS learned_rules(
                  id TEXT PRIMARY KEY,title TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,
                  payload TEXT NOT NULL,source_job_key TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            ''')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=30);db.row_factory=sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()
    def start(self,now,kind):
        run=uuid.uuid4().hex
        local=now.astimezone(BERLIN)
        edition=local.date().isoformat() if local.weekday()<5 and local.hour>=18 else None
        with self.connect() as db:
            db.execute('INSERT INTO scans VALUES(?,?,NULL,?,?,?,?)',(run,now.isoformat(),edition,kind,'running',json.dumps({'progress':'正在读取招聘来源','completed':0,'total':0})))
        return run
    def progress(self,run,message,completed,total):
        with self.connect() as db:
            db.execute('UPDATE scans SET payload=? WHERE id=? AND status=?',(json.dumps({'progress':message,'completed':completed,'total':total},ensure_ascii=False),run,'running'))
    def finish(self,run,now,status,jobs,queries,stats):
        jobs=copy.deepcopy(jobs);stats=copy.deepcopy(stats)
        today=now.astimezone(BERLIN).date().isoformat();new_count=0
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for j in jobs:
                if status not in ('complete','partial'):continue
                self._record_seen(db,j,run,now.isoformat())
                if j['classification']!='recommended':continue
                prior=db.execute('SELECT first_at FROM recommendations WHERE job_key=?',(j['key'],)).fetchone()
                j['first_recommended_at']=prior['first_at'] if prior else now.isoformat()
                j['new_recommendation']=not bool(prior)
                if prior and prior['first_at'][:10]<today:
                    j['classification']='previous'
                if not prior:new_count+=1
                db.execute('INSERT INTO recommendations VALUES(?,?,?,?) ON CONFLICT(job_key) DO UPDATE SET last_at=excluded.last_at',
                           (j['key'],now.isoformat(),now.isoformat(),j.get('title','')))
            stats['new_count']=new_count
            payload=json.dumps({'jobs':jobs,'queries':queries,'stats':stats},ensure_ascii=False)
            db.execute('UPDATE scans SET finished=?,status=?,payload=? WHERE id=?',(now.isoformat(),status,payload,run))

    @staticmethod
    def _record_seen(db,j,run,stamp):
        aliases=['key:'+j['key']]
        for field in ('url','apply_url'):
            url=canonical_url(j.get(field,''))
            if url and (field=='url' or j.get('apply_status')=='verified'):aliases.append('url:'+url)
        found=None
        for alias in aliases:
            found=db.execute('SELECT s.* FROM aliases a JOIN sightings s ON a.job_key=s.job_key WHERE a.alias=?',(alias,)).fetchone()
            if found:break
        identity=found['job_key'] if found else j['key']
        j['identity_key']=identity
        j['is_new']=not bool(found)
        j['first_seen_at']=found['first_at'] if found else stamp
        j['first_seen_run']=found['first_run'] if found else run
        db.execute('INSERT OR IGNORE INTO sightings VALUES(?,?,?)',(identity,stamp,run))
        for alias in aliases:db.execute('INSERT OR IGNORE INTO aliases VALUES(?,?)',(alias,identity))

    def migrate_history(self):
        """One-time upgrade; preserve original capture timestamps and all evidence."""
        from datetime import datetime
        from .core import evaluate
        with self.connect() as db:
            if db.execute("SELECT 1 FROM settings WHERE name='history_v2'").fetchone():return
            rows=db.execute("SELECT * FROM scans WHERE status IN ('complete','partial') ORDER BY started").fetchall()
            for row in rows:
                payload=json.loads(row['payload'])
                for i,j in enumerate(payload.get('jobs',[])):
                    if 'is_new' not in j:
                        j=evaluate(j,datetime.fromisoformat(row['finished']))
                        self._record_seen(db,j,row['id'],row['finished']);payload['jobs'][i]=j
                db.execute('UPDATE scans SET payload=? WHERE id=?',(json.dumps(payload,ensure_ascii=False),row['id']))
            db.execute("INSERT INTO settings VALUES('history_v2','true')")

    def preference(self,value=None):
        with self.connect() as db:
            if value is not None:
                db.execute("INSERT INTO settings VALUES('display',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(json.dumps(value),))
            row=db.execute("SELECT value FROM settings WHERE name='display'").fetchone()
            return json.loads(row[0]) if row else {'only_new':True,'confirmed':False}

    def ensure_v2_configuration(self, default_keywords, default_sources):
        from .config import DEFAULT_PROFILE, normalize_term
        stamp=now_utc().isoformat()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute("SELECT 1 FROM settings WHERE name='profile_v2'").fetchone():
                db.execute("INSERT INTO settings(name,value) VALUES('profile_v2',?)",(json.dumps(DEFAULT_PROFILE,ensure_ascii=False),))
            if not db.execute("SELECT 1 FROM settings WHERE name='keyword_defaults_seeded_v2'").fetchone():
                # An existing non-empty table may already contain user edits from
                # an earlier V2 build. Never recreate a deleted/renamed default.
                if not db.execute('SELECT 1 FROM keywords LIMIT 1').fetchone():
                    for position,term in enumerate(default_keywords):
                        term=normalize_term(term);norm=term.casefold()
                        db.execute('INSERT INTO keywords(term,norm,enabled,position,created_at) VALUES(?,?,1,?,?)',(term,norm,position,stamp))
                db.execute("INSERT INTO settings(name,value) VALUES('keyword_defaults_seeded_v2','true')")
            db.execute("DELETE FROM source_settings WHERE id='suedwest' AND custom=0")
            for source in default_sources:
                source=dict(source)
                db.execute('INSERT INTO source_settings(id,payload,enabled,custom,last_test) VALUES(?,?,1,0,NULL) '
                           'ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(source['id'],json.dumps(source,ensure_ascii=False)))

    def profile(self,value=None):
        from .config import DEFAULT_PROFILE, validate_profile
        with self.connect() as db:
            if value is not None:
                value=validate_profile(value)
                db.execute("INSERT INTO settings(name,value) VALUES('profile_v2',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(json.dumps(value,ensure_ascii=False),))
            row=db.execute("SELECT value FROM settings WHERE name='profile_v2'").fetchone()
            return json.loads(row['value']) if row else copy.deepcopy(DEFAULT_PROFILE)

    def keywords(self):
        with self.connect() as db:
            return [dict(id=r['id'],term=r['term'],enabled=bool(r['enabled']),position=r['position'])
                    for r in db.execute('SELECT * FROM keywords ORDER BY position,id')]

    @staticmethod
    def _expansion_state(db):
        row = db.execute("SELECT value FROM settings WHERE name='expansion_v3'").fetchone()
        return json.loads(row[0]) if row else {'enabled': True, 'status': 'pending', 'run_id': None, 'added': [], 'blocked': []}

    @staticmethod
    def _save_expansion(db, state):
        db.execute("INSERT INTO settings VALUES('expansion_v3',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value", (json.dumps(state, ensure_ascii=False),))

    def expansion_settings(self, value=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            state = self._expansion_state(db)
            if value is not None:
                if not isinstance(value, dict) or set(value) != {'enabled'} or type(value['enabled']) is not bool:
                    raise ValueError('关键词扩展开关无效')
                state['enabled'] = value['enabled']
                self._save_expansion(db, state)
            return state

    def apply_expansion(self, suggestions, run_id, profile, keywords):
        from .config import normalize_term
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            state = self._expansion_state(db)
            if not state['enabled'] or state['status'] == 'complete':
                return state
            live_keywords = [dict(id=r['id'], term=r['term'], enabled=bool(r['enabled']), position=r['position']) for r in db.execute('SELECT * FROM keywords ORDER BY position,id')]
            live_profile = db.execute("SELECT value FROM settings WHERE name='profile_v2'").fetchone()
            if live_keywords != keywords or not live_profile or json.loads(live_profile[0]) != profile:
                return state
            blocked = set(state['blocked']) | {k['term'].casefold() for k in live_keywords}
            position = db.execute('SELECT COALESCE(MAX(position),-1)+1 FROM keywords').fetchone()[0]
            added = []
            for suggestion in suggestions[:10]:
                term = normalize_term(suggestion['term'])
                if term.casefold() in blocked:
                    continue
                db.execute('INSERT INTO keywords(term,norm,enabled,position,created_at) VALUES(?,?,1,?,?)', (term, term.casefold(), position, now_utc().isoformat()))
                added.append({**suggestion, 'term': term})
                blocked.add(term.casefold()); position += 1
            state.update(status='complete', run_id=run_id, added=added)
            self._save_expansion(db, state)
            return state

    def put_keyword(self,term,enabled=True):
        from .config import normalize_term
        if type(enabled) is not bool:raise ValueError('关键词状态无效')
        term=normalize_term(term);norm=term.casefold()
        with self.connect() as db:
            if db.execute('SELECT 1 FROM keywords WHERE norm=?',(norm,)).fetchone():raise ValueError('关键词已存在')
            position=db.execute('SELECT COALESCE(MAX(position),-1)+1 FROM keywords').fetchone()[0]
            cur=db.execute('INSERT INTO keywords(term,norm,enabled,position,created_at) VALUES(?,?,?,?,?)',(term,norm,int(enabled),position,now_utc().isoformat()))
            keyword_id=cur.lastrowid
        return next(x for x in self.keywords() if x['id']==keyword_id)

    def update_keyword(self,keyword_id,term,enabled):
        from .config import normalize_term
        if type(keyword_id) is not int or type(enabled) is not bool:raise ValueError('关键词更新无效')
        term=normalize_term(term);norm=term.casefold()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT id FROM keywords WHERE norm=? AND id<>?',(norm,keyword_id)).fetchone()
            if existing:raise ValueError('关键词已存在')
            old=db.execute('SELECT norm,enabled FROM keywords WHERE id=?',(keyword_id,)).fetchone()
            if old and old['enabled'] and not enabled and db.execute('SELECT COUNT(*) FROM keywords WHERE enabled=1').fetchone()[0]<=1:
                raise ValueError('至少保留一个启用的关键词')
            if old and old['norm']!=norm:
                state=self._expansion_state(db)
                state['blocked']=sorted(set(state['blocked']) | {old['norm']})
                self._save_expansion(db,state)
            cur=db.execute('UPDATE keywords SET term=?,norm=?,enabled=? WHERE id=?',(term,norm,int(enabled),keyword_id))
            if not cur.rowcount:raise ValueError('关键词不存在')
        return next(x for x in self.keywords() if x['id']==keyword_id)

    def delete_keyword(self,keyword_id):
        if type(keyword_id) is not int:raise ValueError('关键词编号无效')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT enabled,norm FROM keywords WHERE id=?',(keyword_id,)).fetchone()
            if not row:raise ValueError('关键词不存在')
            if row['enabled'] and db.execute('SELECT COUNT(*) FROM keywords WHERE enabled=1').fetchone()[0]<=1:
                raise ValueError('至少保留一个启用的关键词')
            db.execute('DELETE FROM keywords WHERE id=?',(keyword_id,))
            state=self._expansion_state(db)
            state['blocked']=sorted(set(state['blocked']) | {row['norm']})
            self._save_expansion(db,state)

    def source_settings(self):
        with self.connect() as db:
            result=[]
            for row in db.execute('SELECT * FROM source_settings ORDER BY rowid'):
                item=json.loads(row['payload']);item.update(enabled=bool(row['enabled']),custom=bool(row['custom']),last_test=json.loads(row['last_test']) if row['last_test'] else None)
                result.append(item)
            return result

    def set_source_enabled(self,source_id,enabled):
        if not isinstance(source_id,str) or type(enabled) is not bool:raise ValueError('来源设置无效')
        with self.connect() as db:
            row=db.execute('SELECT enabled FROM source_settings WHERE id=?',(source_id,)).fetchone()
            if not row:raise ValueError('来源不存在')
            if row['enabled'] and not enabled and db.execute('SELECT COUNT(*) FROM source_settings WHERE enabled=1').fetchone()[0]<=1:
                raise ValueError('至少保留一个启用来源')
            db.execute('UPDATE source_settings SET enabled=? WHERE id=?',(int(enabled),source_id))
        return next(x for x in self.source_settings() if x['id']==source_id)

    def set_source_test(self,source_id,result):
        if not isinstance(source_id,str) or not isinstance(result,dict):raise ValueError('来源测试结果无效')
        with self.connect() as db:
            cur=db.execute('UPDATE source_settings SET last_test=? WHERE id=?',(json.dumps(result,ensure_ascii=False),source_id))
            if not cur.rowcount:raise ValueError('来源不存在')
        return next(x for x in self.source_settings() if x['id']==source_id)

    def add_custom_source(self,source,result):
        required={'id','name','base','kind'}
        if not isinstance(source,dict) or not required.issubset(source) or set(source)-required-{'region'} or source['kind']!='regional':raise ValueError('自定义来源无效')
        if not all(isinstance(source[k],str) and source[k].strip() for k in required):raise ValueError('自定义来源无效')
        if result.get('status')!='supported' or result.get('detail_parsed') is not True:raise ValueError('只有搜索页和岗位详情测试通过的来源才能添加')
        with self.connect() as db:
            if db.execute('SELECT 1 FROM source_settings WHERE id=? OR json_extract(payload,\'$.base\')=?',(source['id'],source['base'])).fetchone():raise ValueError('该来源已存在')
            db.execute('INSERT INTO source_settings(id,payload,enabled,custom,last_test) VALUES(?,?,1,1,?)',(source['id'],json.dumps(source,ensure_ascii=False),json.dumps(result,ensure_ascii=False)))
        return next(x for x in self.source_settings() if x['id']==source['id'])

    def learned_rules(self):
        with self.connect() as db:
            return [dict(id=r['id'],title=r['title'],enabled=bool(r['enabled']),rule=json.loads(r['payload']),source_job_key=r['source_job_key'],created_at=r['created_at'],updated_at=r['updated_at']) for r in db.execute('SELECT * FROM learned_rules ORDER BY created_at')]

    def add_learned_rule(self,rule,source_job_key):
        from .feedback import validate_rule
        rule=validate_rule(rule);rule_id=uuid.uuid4().hex;stamp=now_utc().isoformat()
        with self.connect() as db:db.execute('INSERT INTO learned_rules VALUES(?,?,1,?,?,?,?)',(rule_id,rule['title'],json.dumps(rule,ensure_ascii=False),source_job_key,stamp,stamp))
        return next(x for x in self.learned_rules() if x['id']==rule_id)

    def update_learned_rule(self,rule_id,rule,enabled):
        from .feedback import validate_rule
        if not isinstance(rule_id,str) or type(enabled) is not bool:raise ValueError('偏好规则更新无效')
        rule=validate_rule(rule)
        with self.connect() as db:
            cur=db.execute('UPDATE learned_rules SET title=?,enabled=?,payload=?,updated_at=? WHERE id=?',(rule['title'],int(enabled),json.dumps(rule,ensure_ascii=False),now_utc().isoformat(),rule_id))
            if not cur.rowcount:raise ValueError('偏好规则不存在')
        return next(x for x in self.learned_rules() if x['id']==rule_id)

    def delete_learned_rule(self,rule_id):
        with self.connect() as db:
            cur=db.execute('DELETE FROM learned_rules WHERE id=?',(rule_id,))
            if not cur.rowcount:raise ValueError('偏好规则不存在')

    def snapshot_job(self,scan_id,job_key):
        with self.connect() as db:
            snap=self.unpack(db.execute("SELECT * FROM scans WHERE id=? AND status IN ('complete','partial')",(scan_id,)).fetchone())
        if not snap:raise ValueError('扫描批次不存在')
        job=next((j for j in snap.get('jobs',[]) if j.get('key')==job_key),None)
        if not job:raise ValueError('岗位不存在')
        return job

    def set_cv(self,metadata):
        required={'id','original_name','stored_name','kind','text','chars'}
        if not isinstance(metadata,dict) or set(metadata)!=required:raise ValueError('简历元数据无效')
        metadata=copy.deepcopy(metadata);text=metadata.pop('text')
        folder=(self.path.parent/'cv').resolve();folder.mkdir(parents=True,exist_ok=True)
        text_name=metadata['id']+'.txt';text_path=(folder/text_name).resolve()
        if text_path.parent!=folder:raise ValueError('简历文字路径无效')
        text_path.write_text(text,encoding='utf-8');metadata['text_name']=text_name
        with self.connect() as db:
            old=db.execute("SELECT value FROM settings WHERE name='current_cv'").fetchone()
            db.execute("INSERT INTO settings(name,value) VALUES('current_cv',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(json.dumps(metadata,ensure_ascii=False),))
        if old:
            old_name=json.loads(old['value']).get('text_name')
            if old_name and old_name!=text_name:
                old_path=(folder/old_name).resolve()
                if old_path.parent==folder and old_path.exists():old_path.unlink()
        return self.current_cv()

    def current_cv(self,include_text=False):
        with self.connect() as db:row=db.execute("SELECT value FROM settings WHERE name='current_cv'").fetchone()
        if not row:return None
        value=json.loads(row['value'])
        if 'text' in value:
            legacy_text=value.pop('text')
            folder=(self.path.parent/'cv').resolve();folder.mkdir(parents=True,exist_ok=True)
            text_name=value['id']+'.txt';path=(folder/text_name).resolve()
            if path.parent!=folder:raise ValueError('简历文字路径无效')
            path.write_text(legacy_text,encoding='utf-8');value['text_name']=text_name
            with self.connect() as db:db.execute("UPDATE settings SET value=? WHERE name='current_cv'",(json.dumps(value,ensure_ascii=False),))
            if include_text:value['text']=legacy_text
        elif include_text:
            folder=(self.path.parent/'cv').resolve();name=value.get('text_name','');path=(folder/name).resolve()
            if not name or path.parent!=folder or not path.exists():raise ValueError('本机简历文字不存在，请重新上传')
            value['text']=path.read_text(encoding='utf-8')
        value.pop('text_name',None)
        return value

    def clear_cv(self):
        with self.connect() as db:
            row=db.execute("SELECT value FROM settings WHERE name='current_cv'").fetchone()
            db.execute("DELETE FROM settings WHERE name='current_cv'")
        if row:
            name=json.loads(row['value']).get('text_name')
            if name:
                folder=(self.path.parent/'cv').resolve();path=(folder/name).resolve()
                if path.parent==folder and path.exists():path.unlink()

    def scheduled_today(self,day):
        with self.connect() as db:
            return bool(db.execute("SELECT 1 FROM scans WHERE edition_date=? AND kind IN ('scheduled','catchup') AND status IN ('complete','partial')",(day,)).fetchone())

    def abandon_running(self):
        # Only call while holding the process-wide scan lock.
        with self.connect() as db:
            db.execute("UPDATE scans SET status='failed',finished=?,payload=? WHERE status='running'",(now_utc().isoformat(),json.dumps({'stats':{'error':'上次扫描进程已结束，保留最近成功批次'}})))
    @staticmethod
    def unpack(row):
        if not row:return None
        result=dict(row);result.update(json.loads(result.pop('payload')));return result
    def view(self,now):
        target=edition_for(now)
        with self.connect() as db:
            latest=self.unpack(db.execute('SELECT * FROM scans ORDER BY started DESC LIMIT 1').fetchone())
            chosen=self.unpack(db.execute("SELECT * FROM scans WHERE status IN ('complete','partial') ORDER BY started DESC LIMIT 1").fetchone())
            mode='initial' if chosen and chosen['kind']=='initial' else 'manual' if chosen and chosen['kind']=='manual' else 'edition'
            history=[dict(x) for x in db.execute('SELECT id,started,finished,edition_date,kind,status FROM scans ORDER BY started DESC LIMIT 20')]
        stale=not chosen or chosen['edition_date']!=target
        if chosen:
            from .feedback import apply_learned_rules
            from .core import evaluate
            rules=[r for r in self.learned_rules() if r['enabled']]
            profile=self.profile()
            scan_time=datetime.fromisoformat(chosen['started'])
            for index,job in enumerate(chosen.get('jobs',[])):
                learned_exclusion=bool(job.get('learned_rule_hits')) or any(str(x).startswith('根据你的反馈排除：') for x in job.get('reasons',[]))
                if learned_exclusion:
                    preserved={k:job[k] for k in ('key','identity_key','is_new','first_seen_at','first_seen_run','new_recommendation','first_recommended_at') if k in job}
                    job=evaluate(job,scan_time,profile=profile);job.update(preserved)
                    job.pop('learned_rule_hits',None);chosen['jobs'][index]=job
                if job.get('classification')=='excluded':continue
                hits=apply_learned_rules(job,rules)
                if hits:
                    job['classification']='excluded';job['learned_rule_hits']=hits
                    job.setdefault('reasons',[]).extend('根据你的反馈排除：'+x['title'] for x in hits)
                    job.setdefault('evidence',[]).extend({'label':'AI 学到的偏好','text':x['explanation']} for x in hits)
        # Latest-attempt metadata remains small; the selected report owns its jobs.
        if latest:
            latest.pop('jobs',None)
            if latest['status']!='failed':latest.pop('queries',None)
        return {'now':now.isoformat(),'timezone':'Europe/Berlin','target_date':target,'mode':mode,
                'snapshot':chosen,'stale':stale,'latest_attempt':latest,'history':history,
                'display':self.preference()}
