"""Readers for public HTML. The BA REST API is deliberately not used (403)."""
import hashlib
import ipaddress
import json
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit, urlencode
from lxml import html
from .core import canonical_url, now_utc, normalize
from .config import DEFAULT_KEYWORDS
from .http_fetch import fetch_html, public_addresses

KEYWORDS = list(DEFAULT_KEYWORDS)
SOURCES = [
    {'id':'ba','name':'Arbeitsagentur','base':'https://www.arbeitsagentur.de','region':'德国全国','kind':'ba'},
    {'id':'bayern','name':'bayern.jobs','base':'https://www.bayern.jobs','region':'Bayern','kind':'regional'},
    {'id':'hessen','name':'hessen.jobs','base':'https://www.hessen.jobs','region':'Hessen','kind':'regional'},
    {'id':'rheinland','name':'rheinland.jobs','base':'https://www.rheinland.jobs','region':'Rheinland / NRW / RLP','kind':'regional'},
    {'id':'berlin','name':'berliner.jobs','base':'https://www.berliner.jobs','region':'Berlin','kind':'regional'},
    {'id':'hamburg','name':'hamburger.jobs','base':'https://www.hamburger.jobs','region':'Hamburg','kind':'regional'},
    {'id':'niedersachsen','name':'Jobs für Niedersachsen','base':'https://www.jobsfuerniedersachsen.de','region':'Niedersachsen / Hannover','kind':'regional'},
    {'id':'brandenburg','name':'MAZ Job','base':'https://www.maz-job.de','region':'Brandenburg / Berlin','kind':'regional'},
    {'id':'sachsen','name':'Rosinenpicker','base':'https://www.rosinenpicker.de','region':'Sachsen / Leipzig / Dresden','kind':'regional'},
    {'id':'norden','name':'Küstenfischer','base':'https://www.kuestenfischer.de','region':'Schleswig-Holstein / Mecklenburg-Vorpommern','kind':'regional'},
    {'id':'suedwest-jobs','name':'suedwest.jobs','base':'https://www.suedwest.jobs','region':'Südwest / Baden-Württemberg','kind':'regional'},
]


def source_catalog():
    return [dict(source) for source in SOURCES]


def doc(text):
    return html.fromstring(text or '<html></html>')


def plain(text):
    if not text:
        return ''
    try:
        d = doc(text)
        for x in d.xpath('//script|//style|//noscript'):
            x.drop_tree()
        return ' '.join(d.text_content().replace('\\n', ' ').split())
    except (ValueError, TypeError):
        return ' '.join(str(text).split())


def postings(d):
    out = []
    def visit(x):
        if isinstance(x, list):
            for v in x: visit(v)
        elif isinstance(x, dict):
            if x.get('@type') == 'JobPosting' or 'JobPosting' in (x.get('@type') or []):
                out.append(x)
            if '@graph' in x: visit(x['@graph'])
    for element in d.xpath('//script[@type="application/ld+json"]'):
        try: visit(json.loads(element.text or 'null'))
        except (ValueError, TypeError): pass
    return out


def state(d):
    values = d.xpath('//script[@id="ng-state"]/text()')
    if not values: return {}
    try: return json.loads(values[0])
    except ValueError: return {}


def german_date(value):
    m = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', value or '')
    return f'{m[3]}-{m[2]}-{m[1]}' if m else None


def parse_search(body, url, keyword):
    d = doc(body)
    items = []
    a = state(d).get('suchergebnis')
    if isinstance(a, dict) and 'ergebnisliste' in a:
        for j in a['ergebnisliste']:
            locations = [l.get('adresse', {}).get('ort','') for l in j.get('stellenlokationen', [])]
            items.append({'title':j.get('stellenangebotsTitel',''), 'company':j.get('firma',''),
                          'location':', '.join(dict.fromkeys(locations)),
                          'url':'https://www.arbeitsagentur.de/jobsuche/jobdetail/'+str(j.get('referenznummer','')),
                          'posted':j.get('datumErsteVeroeffentlichung') or j.get('veroeffentlichungszeitraum',{}).get('von'),
                          'search_terms':[keyword], 'reference':j.get('referenznummer')})
        total = a.get('maxErgebnisse') or a.get('anzahlErgebnisse') or a.get('gesamtAnzahl')
        return {'parsed':True,'items':items,'has_more':len(items)>=25,'total':total}
    for anchor in d.xpath('//a[contains(@class,"recruiter-job-link") and contains(@href,"/job/")]'):
        parents = anchor.xpath('ancestor::*[contains(concat(" ",normalize-space(@class)," ")," job__content ")]')
        row = parents[0] if parents else anchor.getparent().getparent()
        names = row.xpath('.//*[contains(@class,"recruiter-company-profile-job-organization")]/text()')
        loc = row.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," location ")]')
        dates = row.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," date ")]/text()')
        items.append({'title':' '.join(anchor.text_content().split()),'url':urljoin(url,anchor.get('href')),
                      'company':' '.join(names).strip() or anchor.get('data-gtm-employer_name',''),
                      'location':' '.join(loc[0].text_content().split()) if loc else '',
                      'posted':german_date(' '.join(dates)), 'search_terms':[keyword]})
    page_links=d.xpath('//a[contains(@href,"page=")]')
    content=plain(body).lower()
    empty = bool(re.search(r'(?:0\s+(?:jobs|stellen|ergebnisse)|keine\s+(?:jobs|stellen|ergebnisse)|keine passenden)', content))
    return {'parsed':bool(items) or empty,'items':items,'has_more':bool(page_links),'total':None}


def parse_detail(body, url):
    d = doc(body)
    jobs = postings(d)
    if not jobs:
        raise ValueError('详情页没有可识别的 JobPosting，不能把普通页面当岗位')
    # Match the visible heading if a page contains more than one schema.
    h1 = ' '.join(d.xpath('//h1//text()')).strip()
    j = next((x for x in jobs if normalize(x.get('title','')) == normalize(h1)), jobs[0])
    desc = plain(j.get('description',''))
    locations = j.get('jobLocation', [])
    if isinstance(locations, dict): locations = [locations]
    cities = []
    for loc in locations:
        address = loc.get('address') or {}
        cities.append(address.get('addressLocality') or address.get('addressRegion') or '')
    typ = j.get('employmentType') or []
    if isinstance(typ, str): typ = [typ]
    original = None
    m = re.search(r'(?:Publication Date|Veröffentlichungsdatum|erstmals veröffentlicht|Date posted)\s*:?\s*(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})', desc, re.I)
    if m: original = german_date(m[1]) or m[1]
    ba = state(d).get('jobdetail') or {}
    if isinstance(ba, dict):
        original = ba.get('datumErsteVeroeffentlichung') or original
    salary = '薪资待确认'
    pay = j.get('baseSalary') or {}
    if isinstance(pay, dict):
        value=pay.get('value') or {}
        if isinstance(value,dict) and any(value.get(k) not in (None,'') for k in ['value','minValue','maxValue']):
            amounts=[str(value[k]) for k in ['minValue','maxValue'] if value.get(k) not in (None,'')]
            salary=(' – '.join(amounts) or str(value.get('value'))) + ' ' + pay.get('currency','') + ' / ' + value.get('unitText','周期待确认')
    apply = ''
    for anchor in d.xpath('//a[@href]'):
        href=urljoin(url,anchor.get('href'))
        if '/apply-external' in href:
            apply=href;break
    if not apply:
        linked = j.get('url')
        if linked and canonical_url(linked) != canonical_url(url): apply=linked
    if not apply:
        for anchor in d.xpath('//a[@href]'):
            label=' '.join(anchor.text_content().split())
            if re.search(r'^(?:Jetzt\s+)?(?:online\s+)?bewerben|apply now|externe seite öffnen',label,re.I):
                href=urljoin(url,anchor.get('href'))
                if href.startswith('https://'):apply=href;break
    ident=j.get('identifier') or {}
    ref=ident.get('value') if isinstance(ident,dict) else str(ident)
    return {'title':j.get('title',''),'company':(j.get('hiringOrganization') or {}).get('name',''),
            'location':', '.join(dict.fromkeys(cities)), 'description':desc,
            'employment':typ, 'posted':j.get('datePosted'), 'original_posted':original,
            'valid_through':j.get('validThrough'), 'salary':salary, 'url':url,
            'apply_url':apply, 'apply_status':'unverified','reference':ref,
            'checked_at':now_utc().isoformat(),'content_hash':hashlib.sha256(body.encode()).hexdigest()}


def application_evidence(body, title):
    d=doc(body)
    # Remove unrelated recommendations/navigation before checking closure.
    for x in d.xpath('//nav|//footer|//script|//style'):
        x.drop_tree()
    text=' '.join(d.text_content().split())
    closed=re.search(r'(?:this (?:job|position|vacancy) (?:is |has been )?(?:no longer available|closed|filled)|stelle (?:ist |wurde )?(?:nicht mehr verfügbar|besetzt|geschlossen)|stellenangebot (?:ist )?nicht mehr|job (?:ist )?nicht mehr verfügbar|keine bewerbungen mehr)',text,re.I)
    if closed:return 'closed',closed.group(0)
    tokens=[t for t in normalize(title).split() if len(t)>3 and t not in {'praktikum','praktikant','werkstudent','internship','intern','student','working'}]
    headings=' '.join(d.xpath('//h1//text()|//h2//text()'))
    normalized=normalize(headings)
    title_match = normalize(title) in normalize(text) or (len(tokens)>0 and sum(t in normalized.split() for t in tokens)/len(tokens)>=0.8)
    action=bool(d.xpath('//input[@type="file"]'))
    for element in d.xpath('//a|//button|//input[@type="submit"]'):
        label=element.text_content()+' '+(element.get('value') or '')
        if re.search(r'bewerben|apply(?:\s+now|\s+for)?|bewerbung starten|submit application',label,re.I): action=True
    if title_match and action and len(text)>120:
        return 'verified','申请目标页可读取，岗位名称匹配且存在申请入口（核验时有效）'
    return 'unverified','目标页可读取，但岗位身份或可申请入口未同时确认'


def safe_url(url):
    public_addresses(url)
    return url


class Fetcher:
    def __init__(self):
        self.lock=threading.Lock();self.host_times={};self.cache={}

    def wait_host(self,url):
        with self.lock:
            host=urlsplit(url).hostname
            delay=max(0,self.host_times.get(host,0)-time.monotonic())
            self.host_times[host]=time.monotonic()+delay+0.6
        if delay:time.sleep(delay)

    def get(self,url,timeout=12):
        with self.lock:
            if url in self.cache:return self.cache[url]
        result=fetch_html(url,timeout,before_request=self.wait_host)
        with self.lock:self.cache[url]=result
        return result


def query_url(source, keyword, page=0, fulltime_required=True):
    if source['kind']=='ba':
        params={'was':keyword,'veroeffentlichtseit':'1','page':page+1,'suchbereich':'jobs'}
        if fulltime_required:params['arbeitszeit']='vz'
        return source['base']+'/jobsuche/suche?'+urlencode(params)
    params={'search':keyword}
    if page:params['page']=page
    return source['base']+'/jobs?'+urlencode(params)


def test_source(source, keyword, fetcher):
    """Probe a source without treating an unreadable page as zero results."""
    result = {
        'status': 'error', 'search_parsed': False, 'result_count': 0,
        'detail_parsed': None, 'date_found': None,
        'application_found': None, 'message': '',
    }
    try:
        url = query_url(source, keyword, 0)
        response = fetcher.get(url)
        search = parse_search(response['body'], response.get('url', url), keyword)
        if not search['parsed']:
            result.update(status='unsupported', message='搜索页结构未识别，未将其当作零结果')
            return result
        result.update(
            status='unverified', search_parsed=True,
            result_count=len(search['items']), message='搜索页可读取',
        )
        if search['items']:
            item = search['items'][0]
            detail_response = fetcher.get(item['url'])
            job = parse_detail(detail_response['body'], detail_response.get('url', item['url']))
            result.update(
                status='supported' if job.get('title') else 'unverified',
                detail_parsed=bool(job.get('title')),
                date_found=bool(job.get('posted') or job.get('original_posted')),
                application_found=bool(job.get('apply_url')),
                message='搜索页和岗位详情可读取',
            )
        else:
            result['message']='本关键词未返回岗位，无法实测详情；请先用能返回岗位的关键词再测试'
        return result
    except Exception as exc:
        result['status'] = 'error'
        result['message'] = ('来源测试失败：' + str(exc))[:240]
        return result


def check_application(fetcher, job):
    url=job.get('apply_url')
    if not url:
        return {'apply_status':'unverified','apply_note':'来源没有公开可直接核验的申请地址'}
    try:
        result=fetcher.get(url,timeout=9)
        status,note=application_evidence(result['body'],job['title'])
        extra={}
        try:
            primary=parse_detail(result['body'],result['url'])
            if normalize(primary['title'])==normalize(job['title']):
                extra={'application_posted':primary.get('original_posted') or primary.get('posted'),
                       'application_employment':primary.get('employment',[]),'application_location':primary.get('location')}
                if primary.get('salary')!='薪资待确认':extra['application_salary']=primary.get('salary')
                if primary.get('location') and normalize(primary['location'])!=normalize(job.get('location','')):
                    extra['location']=primary['location']
        except ValueError:pass
        return {'apply_status':status,'apply_note':note,'apply_url':result['url'],'apply_checked_at':result['at'],**extra}
    except urllib.error.HTTPError as e:
        return {'apply_status':'closed' if e.code in (404,410) else 'unverified','apply_note':f'申请入口返回 HTTP {e.code}，未通过核验'}
    except Exception as e:
        return {'apply_status':'unverified','apply_note':'申请入口读取失败：'+str(e)[:180]}
