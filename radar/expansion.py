"""Offline, once-only keyword expansion from related terms in multiple JDs."""
from .config import role_kind
from .core import clean_role_text
from .terms import find_term, related_groups


def responsibility_text(job):
    text = clean_role_text(job.get('description', ''))
    return job.get('title', '') + ' ' + text


def expand_keywords(store, jobs, run_id, *, profile=None, keywords=None):
    state = store.expansion_settings()
    if not state['enabled'] or state['status'] == 'complete':
        return state
    profile = profile if profile is not None else store.profile()
    keywords = keywords if keywords is not None else store.keywords()
    eligible = {j['key']: j for j in jobs if j.get('key') and j.get('classification') in ('recommended', 'review', 'previous')}
    if len(eligible) < 2:
        return state
    seeds = [k['term'] for k in keywords if k['enabled']]
    vocabulary = list(dict.fromkeys(term for group in related_groups(seeds + profile['themes']) for term in group))
    # An all-internship search must not introduce unrestricted regular searches.
    prefixes = [('', None)] if 'regular' in profile['role_types'] else [
        (prefix, kind) for prefix, kind in (('Praktikum ', 'internship'), ('Werkstudent ', 'werkstudent_fulltime')) if kind in profile['role_types']]
    existing = {k['term'].casefold() for k in keywords} | set(state['blocked'])
    suggestions = []
    for term in vocabulary:
        for prefix, kind in prefixes:
            proposed = prefix + term
            if proposed.casefold() in existing:
                continue
            hits = [(key, find_term(responsibility_text(j), term)) for key, j in eligible.items() if kind is None or role_kind(j['title']) == kind]
            hits = [(key, hit) for key, hit in hits if hit]
            if len(hits) < 2:
                continue
            suggestions.append({'term': proposed, 'job_keys': sorted(key for key, _ in hits),
                                'reason': f'与初始方向相关，本轮 {len(hits)} 份候选 JD 明确提到 {term}',
                                'evidence': hits[0][1][:180]})
    return store.apply_expansion(suggestions[:10], run_id, profile, keywords)
