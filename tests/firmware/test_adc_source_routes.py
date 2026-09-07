import pytest
from fastapi import HTTPException
from oqlos.api import adc_source_routes as api


@pytest.fixture
def config(tmp_path, monkeypatch):
    path = tmp_path / '30-stacknet-pahub.conf'
    path.write_text("[Service]\nEnvironment='STACKNET_ADC_CHANNEL_MAP={\"ai02\":1}'\n")
    monkeypatch.setattr(api, 'CONFIG', path)
    monkeypatch.setattr(api, 'restart', lambda: None)
    return path


def test_apply_and_reload(config):
    initial = api.get_sources()
    result = api.update_sources(api.SourceUpdate(mapping={'ai01':0,'ai03':2}, revision=initial['revision']))
    assert result['mapping'] == {'ai01':0,'ai03':2}
    assert result['revision'] != initial['revision']
    assert 'STACKNET_ADS1100_URL=\n' in config.read_text()
    assert api.get_sources() == result


@pytest.mark.parametrize('mapping',[{'ai04':0},{'ai02':3},{'ai01':1,'ai02':1}])
def test_reject_invalid_map(config, mapping):
    before = config.read_text()
    with pytest.raises(HTTPException) as e:
        api.update_sources(api.SourceUpdate(mapping=mapping,revision=api.get_sources()['revision']))
    assert e.value.status_code == 422
    assert config.read_text() == before


def test_conflict(config):
    with pytest.raises(HTTPException) as e:
        api.update_sources(api.SourceUpdate(mapping={}, revision='stale'))
    assert e.value.status_code == 409


def test_restart_failure_restores_file(config, monkeypatch):
    before = config.read_text()
    calls = []
    def restart():
        calls.append(True)
        if len(calls) == 1: raise OSError('failed')
    monkeypatch.setattr(api,'restart',restart)
    with pytest.raises(HTTPException):
        api.update_sources(api.SourceUpdate(mapping={},revision=api.get_sources()['revision']))
    assert config.read_text() == before
    assert len(calls) == 2
