"""Validated, user-editable job-search configuration."""
import copy
import re


DEFAULT_KEYWORDS = (
    'KI', 'CRM', 'Prozessautomatisierung', 'Digitalisierung',
)

DEFAULT_PROFILE = {
    'role_types': ['regular', 'internship'],
    'fulltime_required': True,
    'locations': ['Deutschland'],
    'relocation': True,
    'themes': ['AI', 'CRM', 'Vertrieb KI', 'Prozessautomatisierung', 'Digitalisierung'],
    'exclusions': ['Pflichtpraktikum', 'unbezahlt'],
    'notes': '',
}

_PROFILE_KEYS = frozenset(DEFAULT_PROFILE)
_ROLE_TYPES = frozenset(('regular', 'internship', 'werkstudent_fulltime'))
STUDENT_PATTERN = r'werkstudent|working student'
INTERN_PATTERN = r'praktik(?:um|ant)|praktika|\bintern\b|internship'


def role_kind(title):
    if re.search(STUDENT_PATTERN, title, re.I):
        return 'werkstudent_fulltime'
    if re.search(INTERN_PATTERN, title, re.I):
        return 'internship'
    return 'regular'


def role_allowed(title, profile):
    return role_kind(title) in profile['role_types']
_CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def clean_text(value, *, minimum=0, maximum=2000):
    if not isinstance(value, str):
        raise ValueError('内容必须是文字')
    value = ' '.join(value.split())
    if _CONTROL.search(value) or len(value) < minimum or len(value) > maximum:
        raise ValueError('文字长度或格式无效')
    return value


def normalize_term(value):
    return clean_text(value, minimum=2, maximum=120)


def validate_profile(value):
    if not isinstance(value, dict) or set(value) != _PROFILE_KEYS:
        raise ValueError('求职目标字段不完整或包含未知字段')
    if type(value['fulltime_required']) is not bool or type(value['relocation']) is not bool:
        raise ValueError('求职目标开关无效')
    result = copy.deepcopy(value)
    for key in ('role_types', 'locations', 'themes', 'exclusions'):
        items = value[key]
        if not isinstance(items, list) or (key in ('role_types', 'locations') and not items) or len(items) > 100:
            raise ValueError(f'{key} 列表格式无效；至少选择一种岗位形式和一个地点')
        result[key] = [clean_text(x, minimum=1, maximum=120) for x in items]
    if not set(result['role_types']).issubset(_ROLE_TYPES):
        raise ValueError('包含未知岗位形式')
    result['notes'] = clean_text(value['notes'], maximum=2000)
    return result
