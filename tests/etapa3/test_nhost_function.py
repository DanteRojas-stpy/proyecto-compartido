import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[2]


def generar_flujos():
    spec = importlib.util.spec_from_file_location('generador_nhost', ROOT / 'n8n/etapa3/generar.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.generate()


def test_n8n_opera_nhost_por_https_sin_credencial_postgres():
    flows = generar_flujos()
    assert len(flows) == 5
    nodes = [node for flow in flows for node in flow['nodes']]

    assert all(node['type'] != 'n8n-nodes-base.postgres' for node in nodes)
    assert all(node.get('notes') != 'CREDENCIAL_E3:postgres' for node in nodes)

    expected = {
        'Tomar eventos pendientes': "operacion:'eventos',datos:{}",
        'Reservar versión por correo': "operacion:'preparar_correo',datos:$json",
        'Operación transaccional Nhost': 'operacion:$json.body.operacion,datos:$json.body.datos||{}',
    }
    for name, body in expected.items():
        node = next(item for item in nodes if item['name'] == name)
        assert node['type'] == 'n8n-nodes-base.httpRequest'
        assert node['parameters']['url'].endswith('.nhost.run/v1/e3-operar')
        assert body in node['parameters']['jsonBody']
        assert node['notes'] == 'CREDENCIAL_E3:internal'
        assert node['parameters']['genericAuthType'] == 'httpHeaderAuth'

    for flow in flows:
        number = flow['id'][-1]
        exported = json.loads((ROOT / f'n8n/etapa3/e3-{number}.json').read_text(encoding='utf-8'))
        assert exported == flow


def test_peticiones_nhost_no_cierran_la_expresion_antes_de_tiempo():
    # El evaluador de n8n toma el primer }} como fin, incluso dentro de un objeto.
    # datos:{} seguido de otra } cortaba la petición y producía HTTP 500.
    calls = [node for flow in generar_flujos() for node in flow['nodes']
             if str(node.get('parameters', {}).get('url', '')).endswith('/v1/e3-operar')]
    assert len(calls) == 3
    for node in calls:
        expression = node['parameters']['jsonBody']
        assert expression.startswith('={{ ')
        assert expression.endswith(' }}')
        assert expression.index('}}') == len(expression) - 2, node['name']


def test_funcion_nhost_protege_la_operacion_interna():
    source = (ROOT / 'functions/e3-operar.ts').read_text(encoding='utf-8')
    assert 'E3_INTERNAL_KEY' in source
    assert "req.header('x-costflow-internal-key')" in source
    assert 'timingSafeEqual' in source
    assert "type: 'run_sql'" in source
    assert 'OPERACIONES.has(operacion)' in source
    assert 'SUBDOMINIO' not in source
    assert 'x-hasura-admin-secret' in source
    assert 'NHOST_GRAPHQL_URL' in source

    block = source.split('const OPERACIONES = new Set([', 1)[1].split('])', 1)[0]
    allowed = set(re.findall(r"'([a-z_]+)'", block))
    sql = (ROOT / 'db/etapa3/013_procesamiento.sql').read_text(encoding='utf-8')
    implemented = set(re.findall(r"WHEN '([a-z_]+)' THEN", sql))
    assert allowed == implemented


def test_instalador_no_sustituye_flujos_si_nhost_no_esta_desplegado(monkeypatch):
    spec = importlib.util.spec_from_file_location('instalador_e3', ROOT / 'scripts/configurar_etapa3_local.py')
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    monkeypatch.setattr(installer, 'bindings', lambda: {'gmail': {'id': 'prueba'}, 'storage': {'id': 'prueba'}})
    monkeypatch.setattr(installer, 'environment', lambda: {
        'NHOST_SUBDOMAIN': 'prueba', 'NHOST_REGION': 'sa-east-1', 'E3_INTERNAL_KEY': 'interna-de-prueba'})
    monkeypatch.setattr(installer.subprocess, 'run', Mock())
    post = Mock(return_value=Mock(json=lambda: {'error': 'no desplegada'}))
    monkeypatch.setattr(installer.requests, 'post', post)
    docker, n8n = Mock(), Mock()
    monkeypatch.setattr(installer, 'docker', docker)
    monkeypatch.setattr(installer, 'n8n', n8n)
    with pytest.raises(RuntimeError, match='Los flujos existentes no se modificaron'):
        installer.install(publicar=True)
    docker.assert_not_called()
    n8n.assert_not_called()
    assert post.call_args.kwargs['json'] == {'operacion': 'configuracion', 'datos': {}}


def test_handler_nhost_con_node():
    node = shutil.which('node')
    if not node:
        pytest.skip('Las pruebas ejecutables de la Function requieren Node.js 22.6 o posterior.')
    version = subprocess.check_output([node, '--version'], text=True).strip().lstrip('v')
    major, minor, *_ = map(int, version.split('.'))
    if (major, minor) < (22, 6):
        pytest.skip('El Node.js instalado no admite TypeScript; usa Node.js 24 para la Function.')
    result = subprocess.run([node, '--experimental-strip-types', '--test',
                             str(ROOT / 'tests/etapa3/nhost_function.test.mjs')],
                            capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
