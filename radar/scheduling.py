"""Local schedule settings shared by the app, scan history and desktop task."""
import json
import re
from datetime import time
from pathlib import Path

DEFAULT_TIME = '18:00'


def validate_time(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', value):
        raise ValueError('自动搜索时间须为 00:00–23:59，格式 HH:MM')
    return value


def scan_time(value=DEFAULT_TIME):
    hour, minute = map(int, validate_time(value).split(':'))
    return time(hour, minute)


def read_schedule(folder):
    defaults = {'installed': False, 'time': DEFAULT_TIME, 'timezone': 'Europe/Berlin', 'days': 'Monday-Friday'}
    path = Path(folder) / 'schedule.json'
    if not path.exists(): return defaults
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(value, dict) or type(value.get('installed')) is not bool:
            raise ValueError('配置格式无效')
        validate_time(value.get('time', DEFAULT_TIME))
        return {**defaults, **value, 'timezone': 'Europe/Berlin', 'days': 'Monday-Friday'}
    except (ValueError, OSError):
        return {**defaults, 'error': '自动搜索配置无法读取，请重新保存设置。'}
