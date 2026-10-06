"""Bounded, rate-limited scans with query-level evidence and atomic snapshots."""
import json
import logging
import re
import threading
import urllib.error
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path
from .core import BERLIN, now_utc, evaluate, merge_jobs
from .sources import SOURCES, KEYWORDS, Fetcher, parse_search, parse_detail, query_url, check_application
from .store import Store
from .config import role_allowed

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'data'
DB=DATA/'jobs.sqlite'
PAGES_PER_QUERY=2
DETAILS_PER_SOURCE=35


class AlreadyRunning(Exception):pass


class ScanLock:
    def __enter__(self):
        DATA.mkdir(exist_ok=True)
        self.file=open(DATA/'scan.lock','a+b')
        self.file.seek(0);self.file.write(b'0');self.file.flush();self.file.seek(0)
        try:
            import msvcrt
            msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            self.file.close();raise AlreadyRunning('已有扫描正在执行')
        return self
    def __exit__(self,*args):
        import msvcrt
        self.file.seek(0);msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1);self.file.close()


def run_scan(kind='manual',source_ids=None):
    with ScanLock():
        store=Store(DB);store.migrate_history();store.ensure_v2_configuration(KEYWORDS,SOURCES);started=now_utc();run=store.start(started,kind)
        fetcher=Fetcher();queries=[];candidates=[];detail_errors=[];guard=threading.Lock()
        configured_sources=[s for s in store.source_settings() if s['enabled']]
        sources=[s for s in configured_sources if not source_ids or s['id'] in source_ids]
        keyword_snapshot=store.keywords()
        keywords=[k['term'] for k in keyword_snapshot if k['enabled']]
        learned_rules=[r for r in store.learned_rules() if r['enabled']]
        profile=store.profile()
        total=len(sources)*len(keywords);done=0;truncated=[]
        try:
            def search_source(source):
                nonlocal done
                found={};failures=0
                terms=keywords
                for keyword in terms:
                    for page in range(PAGES_PER_QUERY):
                        url=query_url(source,keyword,page,fulltime_required=profile['fulltime_required']);check={'source':source['name'],'region':source.get('region',''),'keyword':keyword,'url':url,'page':page+1,'at':now_utc().isoformat()}
                        try:
                            response=fetcher.get(url)
                            result=parse_search(response['body'],url,keyword)
                            if not result['parsed']:raise ValueError('搜索页结构未识别；不将其算作零结果')
                            check.update(status='ok',http_status=response['status'],count=len(result['items']),has_more=result['has_more'])
                            for item in result['items']:
                                if not role_allowed(item['title'],profile):continue
                                # Keep older results in query counts, but avoid re-fetching stale listings.
                                if item.get('posted') and item['posted'][:10]<(started.astimezone(BERLIN).date()-timedelta(days=2)).isoformat():continue
                                item.update(source=source['name'],source_id=source['id'])
                                if item['url'] in found:
                                    found[item['url']]['search_terms']=sorted(set(found[item['url']]['search_terms']+[keyword]))
                                else:found[item['url']]=item
                            failures=0
                            if page==PAGES_PER_QUERY-1 and result['has_more']:check['limited']=True
                            with guard:queries.append(check)
                            if not result['has_more']:break
                        except Exception as e:
                            check.update(status='error',error=str(e)[:240],count=0)
                            with guard:queries.append(check)
                            failures+=1
                            break
                    with guard:
                        done+=1
                        store.progress(run,f'检索 {source["name"]} · {keyword}',done,total+3)
                    # Do not repeatedly hammer a source that is down.
                    if failures>=2:
                        with guard:queries.append({'source':source['name'],'region':source.get('region',''),'status':'skipped','keyword':'后续关键词','count':0,'url':source['base'],'error':'连续两次读取失败，本轮停止该来源','at':now_utc().isoformat()})
                        break
                rows=sorted(found.values(),key=lambda j:(j.get('posted') or '',bool(re.search(r'KI|CRM|AI|automatis|automation',j['title'],re.I))),reverse=True)
                if len(rows)>DETAILS_PER_SOURCE:
                    with guard:truncated.append({'source':source['name'],'found':len(rows),'checked_limit':DETAILS_PER_SOURCE})
                return rows[:DETAILS_PER_SOURCE]
            with ThreadPoolExecutor(max_workers=4) as pool:
                for future in as_completed([pool.submit(search_source,s) for s in sources]):candidates.extend(future.result())
            # Same URL appearing in multiple keyword/source queries is read once.
            unique={}
            for c in candidates:
                if c['url'] in unique:
                    unique[c['url']]['search_terms']=sorted(set(unique[c['url']]['search_terms']+c['search_terms']))
                else:unique[c['url']]=c
            def detail(c):
                try:
                    r=fetcher.get(c['url']);j=parse_detail(r['body'],r['url'])
                    j.update(source=c['source'],source_id=c['source_id'],search_terms=c['search_terms'])
                    if not j.get('posted'):j['posted']=c.get('posted')
                    if c.get('reference'):j['reference']=c['reference']
                    if c['source_id']=='ba' and c.get('posted'):j['original_posted']=c['posted']
                    return j
                except Exception as e:
                    with guard:detail_errors.append({'source':c['source'],'url':c['url'],'title':c['title'],'error':str(e)[:220]})
                    return None
            jobs=[]
            with ThreadPoolExecutor(max_workers=6) as pool:
                futures=[pool.submit(detail,c) for c in unique.values()]
                for number,future in enumerate(as_completed(futures),1):
                    j=future.result()
                    if j:jobs.append(j)
                    store.progress(run,'核验岗位详情与原始发布日期',number,len(futures))
            merged=merge_jobs(jobs)
            eligible=[j for j in merged if evaluate(j,started,learned_rules,profile)['classification']!='excluded']
            def verify(j):
                result=check_application(fetcher,j);j.update(result)
                if result.get('application_posted'):
                    j['original_posted']=min(x for x in [j.get('original_posted'),result['application_posted']] if x)
                return j
            with ThreadPoolExecutor(max_workers=5) as pool:
                for number,_ in enumerate(as_completed([pool.submit(verify,j) for j in eligible]),1):
                    _.result();store.progress(run,'核验申请入口是否仍可用',number,len(eligible))
            finished=now_utc();evaluated=[evaluate(j,started,learned_rules,profile) for j in merged]
            evaluated.sort(key=lambda j:(j['classification']=='recommended',j['classification']=='review',j['rank'],j.get('posted') or ''),reverse=True)
            good={q['source'] for q in queries if q['status']=='ok'}
            errors=[q for q in queries if q['status']!='ok']
            status='failed' if not good or (unique and not jobs) else 'partial' if errors or detail_errors else 'complete'
            stats={'source_ok':len(good),'source_total':len(sources),'query_count':len(queries),
                   'raw_result_count':sum(q.get('count',0) for q in queries),'candidate_count':len(unique),
                   'detail_count':len(jobs),'dedup_count':len(jobs)-len(merged),'detail_errors':detail_errors,
                   'limited_queries':sum(bool(q.get('limited')) for q in queries),'source_limits':truncated,
                   'window_start':(started-timedelta(hours=24)).isoformat(),'window_end':started.isoformat(),
                   'pages_per_query':PAGES_PER_QUERY,'detail_limit_per_source':DETAILS_PER_SOURCE,
                   'classification_counts':dict(Counter(j['classification'] for j in evaluated))}
            store.finish(run,finished,status,evaluated,queries,stats)
            if status in ('complete','partial'):
                try:
                    from .expansion import expand_keywords
                    expand_keywords(store,evaluated,run,profile=profile,keywords=keyword_snapshot)
                except Exception:
                    logging.exception('Offline keyword expansion failed; completed scan preserved')
            report=store.view(finished)
            summary={'run_id':run,'status':status,**{k:v for k,v in stats.items() if k not in ('detail_errors',)}}
            (DATA/'last-run-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
            return summary
        except Exception as e:
            store.finish(run,now_utc(),'failed',[],queries,{'error':str(e)})
            raise
