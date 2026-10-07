"""Conservative evidence rules. No network or storage side effects."""
import copy
import hashlib
import re
from datetime import datetime, timedelta, time, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from zoneinfo import ZoneInfo
from .scheduling import DEFAULT_TIME, scan_time

BERLIN = ZoneInfo('Europe/Berlin')
UTC = timezone.utc


def now_utc():
    return datetime.now(UTC)


def edition_for(now, schedule_time=DEFAULT_TIME):
    local = now.astimezone(BERLIN)
    day = local.date()
    if local.time().replace(tzinfo=None) < scan_time(schedule_time):
        day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day.isoformat()


def canonical_url(url):
    try:
        p = urlsplit(url)
        if p.scheme not in ('http', 'https'):
            return ''
        pairs = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                 if not k.lower().startswith(('utm_', 'pk_')) and k.lower() not in
                 {'ref', 'referrer', 'source', 'campaign', 'gclid', 'fbclid', 'trackingid'}]
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip('/') or '/', urlencode(sorted(pairs)), ''))
    except ValueError:
        return ''


def normalize(value):
    return re.sub(r'[^\w]+', ' ', value.casefold()).strip()


def job_key(job):
    # Employer + title + location merges cross-posts, but never distinct cities.
    values = [normalize(str(job.get(x, ''))) for x in ('company', 'title', 'location')]
    if not all(values[:2]):
        values = [canonical_url(job.get('url', ''))]
    return hashlib.sha256('|'.join(values).encode()).hexdigest()[:24]


def merge_jobs(jobs):
    seen = {}
    for item in jobs:
        j = copy.deepcopy(item)
        key = job_key(j)
        j['key'] = key
        j.setdefault('sources', [{'name': j.get('source', ''), 'url': j.get('url', '')}])
        if key not in seen:
            seen[key] = j
            continue
        old = seen[key]
        old['search_terms'] = sorted(set(old.get('search_terms', []) + j.get('search_terms', [])))
        for s in j['sources']:
            if s not in old['sources']:
                old['sources'].append(s)
        # Preserve contradictions rather than choosing the friendlier record.
        old['employment'] = sorted(set(old.get('employment', []) + j.get('employment', [])))
        if j.get('original_posted'):
            old['original_posted'] = min(x for x in [old.get('original_posted'), j['original_posted']] if x)
        if old.get('posted') and j.get('posted'):
            old['posted'] = min(old['posted'], j['posted'])
        if len(j.get('description', '')) > len(old.get('description', '')):
            old['description'] = j['description']
    return list(seen.values())


def parse_date(value):
    if not value:
        return None, 'unknown'
    value = str(value).strip()
    try:
        simple=re.fullmatch(r'(\d{4})-(\d{1,2})-(\d{1,2})',value)
        if simple:
            value=f'{int(simple[1]):04}-{int(simple[2]):02}-{int(simple[3]):02}'
            return datetime.combine(datetime.fromisoformat(value).date(), time(), BERLIN), 'day'
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return d if d.tzinfo else d.replace(tzinfo=BERLIN), 'second'
    except (ValueError, TypeError):
        return None, 'unknown'


def snippet(text, pattern, radius=100):
    m = re.search(pattern, text, re.I)
    return text[max(0, m.start()-45):m.end()+radius].strip() if m else ''


def clean_role_text(description):
    text=re.sub(r'\s+', ' ', description or '').strip()
    text=re.sub(r'Die(?:se)? Anzeige wurde[^.]*\.', '', text, flags=re.I)
    text=re.sub(r'[^.!?]*(?:KI-Kompetenz|interne Trainings|AI training)[^.!?]*[.!?]?', '', text, flags=re.I)
    return re.split(r'(?:Deine|Unsere|Ihre|Your)\s+(?:Benefits|Vorteile)|Das bieten wir|Was wir bieten|What we offer', text, flags=re.I)[0]


def evaluate(item, now, learned_rules=None, profile=None):
    j = copy.deepcopy(item)
    text = re.sub(r'\s+', ' ', j.get('description', '')).strip()
    # A site's AI-written-ad disclaimer is never evidence of an AI position.
    text = re.sub(r'Die(?:se)? Anzeige wurde[^.]*\.', '', text, flags=re.I)
    title = j.get('title', '')
    role_text = clean_role_text(text)
    combined = title + ' ' + role_text
    hard, review, evidence, matches = [], [], [], []
    employment = [str(e).upper() for e in j.get('employment', [])]
    exclusions = {x.casefold() for x in profile.get('exclusions', [])} if profile is not None else {'junior', 'pflichtpraktikum', 'unbezahlt'}
    if 'junior' in exclusions and re.search(r'\bjunior\b', title, re.I):
        hard.append('Junior 岗位不在本次范围')
    is_student = bool(re.search(r'werkstudent|working student', title, re.I))
    is_intern = bool(re.search(r'praktik(?:um|ant)|praktika|\bintern\b|internship', title, re.I))
    if profile is None and not is_student and not is_intern:
        hard.append('岗位名称未明确为 Praktikum / Intern / Werkstudent')
    j['role_type'] = 'Werkstudent' if is_student else 'Praktikum / Intern' if is_intern else '正式岗位'
    if profile:
        allowed=set(profile.get('role_types') or [])
        if not is_student and not is_intern and 'regular' not in allowed:
            hard.append('根据你的求职目标，当前不接收正式岗位')
        if is_student and 'werkstudent_fulltime' not in allowed:
            hard.append('根据你的求职目标，当前不接收 Werkstudent 岗位')
        if is_intern and 'internship' not in allowed:
            hard.append('根据你的求职目标，当前不接收 Praktikum / Intern 岗位')
        folded=combined.casefold()
        for term in profile.get('exclusions') or []:
            # These defaults have context-aware checks below (for example
            # "Pflichtpraktikum oder freiwilliges Praktikum möglich").
            if term.casefold() in {'pflichtpraktikum','junior','unbezahlt','unpaid'}:
                continue
            if term.casefold() in folded:
                hard.append(f'命中你的排除词：{term}')
    body_full = bool(re.search(r'\bvollzeit\b|full[ -]?time|(?:3[5-9]|40)\s*(?:h|stunden)\s*(?:/|pro|je)\s*(?:woche|week)', text, re.I))
    application_full='FULL_TIME' in [str(e).upper() for e in j.get('application_employment', [])]
    full = body_full or application_full or ((is_student or not is_intern) and 'FULL_TIME' in employment)
    j['fulltime_confirmed']=full
    short_hours = re.search(r'(?:\b(?:[1-9]|[12]\d|3[0-4])\s*(?:wochenstunden|std\.?\s*(?:/|pro|je|in der)?\s*(?:woche|week)|h(?:ours?)?\s*(?:/|pro|je|in der)?\s*(?:woche|week)|stunden\s*(?:/|pro|je|in der)\s*(?:woche|week))|(?:bis zu|max\.?|maximal)\s*(?:[1-9]|[12]\d|3[0-4])\s*(?:h\b|std\.?|stunden|wochenstunden))', text, re.I)
    body_part=bool(re.search(r'\bteilzeit\b|part[ -]?time',text,re.I)) and not body_full
    holiday = re.search(r'(?:semesterferien|vorlesungsfreie\w* zeit|vorlesungsfrei)[^.]{0,180}(?:vollzeit|40\s*(?:h|stunden))', text, re.I)
    fulltime_required = profile.get('fulltime_required', True) if profile is not None else True
    if fulltime_required and (('PART_TIME' in employment and 'FULL_TIME' not in employment) or short_hours or body_part) and not holiday:
        hard.append('Teilzeit / 每周约20小时，与全职要求不符或相互矛盾')
    elif fulltime_required and not full:
        if is_student:
            hard.append('Werkstudent 岗位没有明确 Vollzeit 或约40小时依据')
        else:
            review.append('缺少明确 Vollzeit 依据')
    if full:
        evidence.append({'label':'全职依据', 'text':snippet(text, r'vollzeit|full[ -]?time') or '来源结构化字段：FULL_TIME（未由正文独立确认）'})
    if fulltime_required and holiday:
        review.append('仅假期全职；需确认用户可工作的时段')
        evidence.append({'label':'时段限制','text':holiday.group(0)})
    if is_intern and 'pflichtpraktikum' in exclusions:
        voluntary = re.search(r'freiwillig\w*\s+(?:orientierungs)?praktikum|voluntary internship|kein\w*\s+pflichtpraktikum|pflichtpraktikum\s+(?:oder|und/oder)\s+(?:ein\s+)?freiwillig', text, re.I)
        compulsory = re.search(r'pflichtpraktik', text, re.I)
        if compulsory and not voluntary:
            hard.append('涉及 Pflichtpraktikum，未证明接受 freiwilliges Praktikum')
        elif not voluntary:
            review.append('尚未确认接受 freiwilliges Praktikum')
        else:
            evidence.append({'label':'实习性质','text':snippet(text, voluntary.re.pattern)})
    if exclusions.intersection({'unbezahlt', 'unpaid'}) and re.search(r'\bunbezahlt\b|unpaid|ohne vergütung|keine vergütung|nur\s+(?:fahrtkosten|aufwandsentschädigung)|symbolische\s+vergütung', text, re.I):
        hard.append('明确无薪或仅象征性补贴')
    j.setdefault('salary', '薪资待确认')
    relevant = [
        (r'\bCRM\b|customer relationship|kunden(?:daten|segment)|lead.?scoring|lead.?management', 'CRM / 客户数据', '对应你的 CRM 清理、客户分群与线索评分经验'),
        (r'automatisier|automation|prozessoptimier|workflow|digitalisier', '流程自动化', '对应你的销售跟进、周报与传统业务流程数字化经验'),
        (r'\bKI\b|\bAI\b|künstliche\w* intelligenz|artificial intelligence|\bLLM\b|\bRAG\b|agentic|ki.agent|ai.agent', 'AI / Agent', '对应你的 AI Agent、MCP、RAG 与应用落地经验'),
        (r'vertrieb|\bsales\b|marketing automation|revenue operations', '销售与营销', '对应你的 Pipeline 汇总、自动化 Follow-up 和数据驱动营销经验'),
        (r'\bpython\b|\bjava\b', '开发能力', '对应你的 Python / Java 技能'),
    ]
    for pattern, label, reason in relevant:
        hit = snippet(combined, pattern, 100)
        if hit:
            matches.append({'label':label, 'reason':'岗位原文提到：' + label, 'evidence':hit})
    theme_hits = []
    if profile is not None:
        from .terms import theme_matches
        for term in profile.get('themes', []):
            hit = theme_matches(combined, term)
            if hit:
                theme_hits.append(term)
                matches.append({'label':'目标方向：' + term, 'reason':'命中已设置方向：' + term, 'evidence':hit})
        if profile.get('themes') and not theme_hits:
            hard.append('岗位职责未命中你设置的优先方向；可调整方向或留空取消此筛选')
    elif not any(m['label'] in ('CRM / 客户数据','流程自动化','AI / Agent') for m in matches):
        hard.append('职责未显示 AI、CRM、销售自动化或相关数字化匹配')
    portal_date = j.get('posted')
    original = j.get('original_posted')
    if not original:
        review.append('仅有门户发布日期，原始发布时间尚未独立确认')
    j['portal_posted'] = portal_date
    if original and portal_date and original[:10] != portal_date[:10]:
        evidence.append({'label':'日期冲突','text':f'门户：{portal_date}；正文/原站原始发布：{original}'})
        review.append('门户与原始发布日期不一致')
    dated=[(parse_date(x)[0],x) for x in (portal_date,original) if x]
    parsed_dates=[pair for pair in dated if pair[0] is not None]
    if any(pair[0] is None for pair in dated):review.append('有发布日期无法解析，需要核对原文')
    effective=min(parsed_dates,key=lambda pair:pair[0])[1] if parsed_dates else None
    if effective and parse_date(effective)[1]=='day':effective=parse_date(effective)[0].date().isoformat()
    j['posted'] = effective
    posted, precision = parse_date(effective)
    j['date_precision'] = precision
    if not posted:
        review.append('原始发布日期缺失或无法解析')
        j['freshness'] = 'unknown'
    else:
        now = now.astimezone(BERLIN)
        lower = now - timedelta(hours=24)
        if posted > now:
            review.append('发布日期在未来，无法确认')
            j['freshness'] = 'future'
        elif precision == 'day' and posted.date() < lower.date():
            hard.append('发布日期超过24小时窗口；旧职位/转载不作为新增推荐')
            j['freshness'] = 'old'
        elif precision == 'day' and posted < lower:
            review.append('仅提供昨日日期，无法确认在过去24小时内')
            j['freshness'] = 'uncertain'
        elif precision != 'day' and posted < lower:
            hard.append('发布日期超过24小时窗口')
            j['freshness'] = 'old'
        else:
            j['freshness'] = 'confirmed'
        evidence.append({'label':'发布时间','text':f'{effective}（仅日期）' if precision == 'day' else str(effective)})
    expired, expiry_precision = parse_date(j.get('valid_through'))
    if expired and (expired.date() < now.astimezone(BERLIN).date() if expiry_precision=='day' else expired<now):
        hard.append('招聘截止日期已过')
    if j.get('apply_status') == 'closed':
        hard.append('申请入口显示已关闭或岗位已下线')
    elif j.get('apply_status') != 'verified':
        review.append('尚未独立确认申请入口仍有效')
    if j.get('apply_note'):
        evidence.append({'label':'申请核验','text':j['apply_note']})
    j['reasons'] = list(dict.fromkeys(hard + review))
    j['classification'] = 'excluded' if hard else 'review' if review else 'recommended'
    j['evidence'] = evidence
    j['matches'] = matches
    j['rank'] = sum({'CRM / 客户数据':5,'流程自动化':5,'AI / Agent':4,'销售与营销':3,'开发能力':1}.get(m['label'], 2) for m in matches)
    if profile:
        j['profile_theme_hits']=theme_hits
        j['rank']+=min(6,len(theme_hits)*2)
    if j['classification']!='excluded' and learned_rules:
        from .feedback import apply_learned_rules
        learned_hits=apply_learned_rules(j,learned_rules)
        if learned_hits:
            j['classification']='excluded';j['learned_rule_hits']=learned_hits
            for hit in learned_hits:
                j['reasons'].append('根据你的反馈排除：'+hit['title'])
                j['evidence'].append({'label':'AI 学到的偏好','text':hit['explanation']})
    j['key'] = job_key(j)
    return j
