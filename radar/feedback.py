"""Validated, deterministic application of user-confirmed AI preference rules."""
import re
from .ai import validate_feedback_rule


def validate_rule(value):return validate_feedback_rule(value)


def _contains(text,terms):
    return [term for term in terms if re.search(r'(?<!\w)'+re.escape(term.casefold())+r'(?!\w)',text,re.I)]


def _scopes(text):
    patterns={
        'sales':r'\bvertrieb|\bsales\b|akquise|lead|business development',
        'marketing':r'marketing|content|campaign|kampagne',
        'crm':r'\bcrm\b|customer relationship|kundendaten',
        'ai':r'\bki\b|\bai\b|künstliche intelligenz|agent|llm|rag',
        'data':r'\bdata\b|daten|analytics|analyse|python|sql',
        'operations':r'operations|prozess|workflow|automatisier|digitalisier',
    }
    return {name for name,pattern in patterns.items() if re.search(pattern,text,re.I)}


def apply_learned_rules(job,rules):
    text=' '.join(str(job.get(k,'') or '') for k in ('title','description')).casefold()
    scopes=_scopes(text);hits=[]
    for wrapper in rules or []:
        if wrapper.get('enabled') is False:continue
        rule=wrapper.get('rule') if isinstance(wrapper.get('rule'),dict) else {key:wrapper[key] for key in ('title','scope','negative_any','keep_if_any','hard_exclude_any','confidence','explanation') if key in wrapper}
        rule=validate_rule(rule)
        if rule['scope'] and not scopes.intersection(x.casefold() for x in rule['scope']):continue
        hard=_contains(text,rule['hard_exclude_any'])
        negative=_contains(text,rule['negative_any'])
        keep=_contains(text,rule['keep_if_any'])
        if hard or (negative and not keep):
            hits.append({'id':wrapper.get('id',''),'title':rule['title'],'explanation':rule['explanation'],'signals':hard or negative})
    return hits
