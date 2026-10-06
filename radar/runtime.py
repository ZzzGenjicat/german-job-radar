"""Separate bundled resources from durable user data."""
import hashlib
import argparse
import os
import sys
from pathlib import Path


def resolve_paths(resource_root, frozen, environ):
    root = Path(resource_root)
    override = environ.get('JOB_RADAR_DATA_DIR')
    if override:
        data = Path(override)
        if not data.is_absolute(): raise ValueError('JOB_RADAR_DATA_DIR must be absolute')
    elif frozen:
        local = environ.get('LOCALAPPDATA')
        data = (Path(local) if local else Path.home() / 'AppData' / 'Local') / 'GermanJobRadar'
    else:
        data = root / 'data'
    return root, data


def app_port(environ):
    port = int(environ.get('JOB_RADAR_PORT', '48218'))
    if not 1024 <= port <= 65535: raise ValueError('JOB_RADAR_PORT must be 1024–65535')
    return port


def credential_target(instance, frozen):
    return f'GermanJobRadar/{instance}/OpenAI' if frozen else 'GermanJobRadar/OpenAI'


FROZEN = bool(getattr(sys, 'frozen', False))
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument('--data-dir')
_options, _ = _parser.parse_known_args()
_environment = os.environ.copy()
if _options.data_dir: _environment['JOB_RADAR_DATA_DIR'] = _options.data_dir
ROOT, DATA = resolve_paths(Path(__file__).resolve().parents[1], FROZEN, _environment)
INSTANCE_ID = hashlib.sha256(str(DATA.resolve()).casefold().encode()).hexdigest()[:24]
