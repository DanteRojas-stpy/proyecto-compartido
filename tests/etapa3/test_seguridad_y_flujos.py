import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.etapa3 import server

ROOT = Path(__file__).resolve().parents[2]


def test_clave_interna_obligatoria(monkeypatch):
    monkeypatch.setenv('E3_INTERNAL_KEY', 'prueba')
    with pytest.raises(HTTPException) as error:
        server.internal('otra')
    assert error.value.status_code == 401
    server.internal('prueba')


def test_identidad_del_cuerpo_nunca_autoriza(monkeypatch):
    real = '11111111-1111-4111-8111-111111111111'
    fake = '22222222-2222-4222-8222-222222222222'
    monkeypatch.setenv('NHOST_SUBDOMAIN', 'proyecto-prueba')
    monkeypatch.setenv('E3_INTERNAL_KEY', 'prueba')
    response = Mock(status_code=200)
    response.json.return_value = {'id': real, 'roles': ['user'], 'defaultRole': 'user', 'isAnonymous': False}
    monkeypatch.setattr(server.requests, 'get', Mock(return_value=response))
    call = Mock(return_value={'ok': True})
    monkeypatch.setattr(server.Bridge, 'call', call)
    assert server.action({'accion': 'aceptar_version', 'version_id': fake, 'usuario_id': fake}, 'Bearer prueba')['ok']
    assert call.call_args.args[1]['usuario_id_verificado'] == real
    assert 'usuario_id' not in call.call_args.args[1]['accion']
    assert server.action({'usuario_id': real}, None)['http_code'] == 401


def test_sesion_invalida_no_llega_a_la_base(monkeypatch):
    monkeypatch.setenv('NHOST_SUBDOMAIN', 'prueba')
    response = Mock(status_code=401)
    monkeypatch.setattr(server.requests, 'get', Mock(return_value=response))
    call = Mock()
    monkeypatch.setattr(server.Bridge, 'call', call)
    assert server.action({}, 'Bearer vencido')['http_code'] == 401
    call.assert_not_called()


def test_cinco_flujos_sin_excel_ollama_ni_envio_gmail():
    spec = importlib.util.spec_from_file_location('generador', ROOT / 'n8n/etapa3/generar.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    flows = module.generate()
    assert len(flows) == 5
    for flow in flows:
        names = {node['name'] for node in flow['nodes']}
        for source, edges in flow['connections'].items():
            assert source in names
            assert all(edge['node'] in names for branch in edges['main'] for edge in branch)
        for node in flow['nodes']:
            assert not any(x in node['type'].lower() for x in ['ollama', 'spreadsheet', 'converttofile'])
            if node['type'] == 'n8n-nodes-base.gmail':
                assert node['parameters']['operation'] == 'get'
                assert node['parameters']['options']['downloadAttachments']
            assert 'credentials' not in node
