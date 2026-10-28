import importlib.util
import json
import re
from pathlib import Path


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
    sql = (ROOT / 'db/etapa3/002_procesamiento.sql').read_text(encoding='utf-8')
    implemented = set(re.findall(r"WHEN '([a-z_]+)' THEN", sql))
    assert allowed == implemented
