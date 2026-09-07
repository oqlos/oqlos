"""Persist and apply the allowlisted ADC source map on the local BoardNet."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, StrictInt

router = APIRouter(prefix='/adc-sources', tags=['adc-sources'])
CONFIG = Path.home() / '.config/systemd/user/usb-adc-stack.service.d/30-stacknet-pahub.conf'
LOCK = threading.Lock()


class SourceUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mapping: dict[str, StrictInt]
    revision: str


def validate_mapping(mapping):
    if any(k not in ('ai01', 'ai02', 'ai03') or type(v) is not int or v not in (0, 1, 2)
           for k, v in mapping.items()):
        raise HTTPException(422, 'Nieprawidłowa mapa kanałów ADC')
    if len(set(mapping.values())) != len(mapping):
        raise HTTPException(422, 'Kanał StackNet może być przypisany tylko do jednego wejścia AI')


def snapshot():
    if not CONFIG.exists():
        raise HTTPException(503, 'Brak zarządzanej konfiguracji ADC na tym urządzeniu')
    content = CONFIG.read_text()
    match = re.search(r'STACKNET_ADC_CHANNEL_MAP=(\{[^\n]*\})', content)
    if not match:
        raise HTTPException(503, 'Nie można odczytać bieżącej mapy ADC')
    mapping = json.loads(match.group(1))
    validate_mapping(mapping)
    return {'mapping': mapping, 'revision': hashlib.sha256(content.encode()).hexdigest(),
            'controller': 'BoardNet', 'stacknet_url': 'http://stacknet.local:8080'}


def restart():
    for args in [('daemon-reload',), ('restart', 'usb-adc-stack'), ('is-active', 'usb-adc-stack')]:
        subprocess.run(['systemctl', '--user', *args], check=True, capture_output=True, timeout=20)


@router.get('')
def get_sources():
    with LOCK:
        return snapshot()


@router.put('')
def update_sources(payload: SourceUpdate):
    validate_mapping(payload.mapping)
    with LOCK:
        current = snapshot()
        if current['revision'] != payload.revision:
            raise HTTPException(409, 'Ustawienia zmieniły się. Odśwież formularz.')
        if current['mapping'] == payload.mapping:
            return current
        previous = CONFIG.read_text()
        content = ('[Service]\nEnvironment=STACKNET_ADC_URL=http://stacknet.local:8080\n'
                   'Environment=STACKNET_ADS1100_URL=\n'
                   "Environment='STACKNET_ADC_CHANNEL_MAP="
                   + json.dumps(payload.mapping, separators=(',', ':')) + "'\n"
                   'Environment=STACKNET_ADC_TIMEOUT=0.8\n')
        temporary = CONFIG.with_suffix('.pending')
        try:
            temporary.write_text(content)
            temporary.replace(CONFIG)
            restart()
        except (OSError, subprocess.SubprocessError) as error:
            temporary.write_text(previous)
            temporary.replace(CONFIG)
            try:
                restart()
            except (OSError, subprocess.SubprocessError):
                raise HTTPException(503, 'Nie udało się zastosować ani uruchomić poprzedniej konfiguracji') from error
            raise HTTPException(503, 'Nie udało się zastosować zmiany; przywrócono poprzednią konfigurację') from error
        return snapshot()
