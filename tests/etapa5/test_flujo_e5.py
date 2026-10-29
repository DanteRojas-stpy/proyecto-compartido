"""Flujo de n8n de E5: estructura y lógica de los pasos con código."""
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def generar():
    spec = importlib.util.spec_from_file_location('generador_e5', ROOT / 'n8n/etapa5/generar.py')
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.generate()[0]


def nodo(nombre):
    return next(n for n in generar()['nodes'] if n['name'] == nombre)


def ejecutar(codigo, entrada_json, otros=None):
    node = shutil.which('node')
    if not node:
        pytest.skip('Esta prueba ejecuta el código de los nodos y requiere Node.js.')
    guion = ('const [codigo, json, otros] = process.argv.slice(1).map((x, i) => i ? JSON.parse(x) : x);'
             'const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;'
             'const f = new AsyncFunction("$json", "$", codigo);'
             'const $ = (n) => ({ first: () => ({ json: otros[n] }) });'
             'f.call({ helpers: { prepareBinaryData: async (b, n, m) => ({ fileName: n, mimeType: m, bytes: b.length }) } }, json, $)'
             '.then((r) => process.stdout.write(JSON.stringify(r)));')
    r = subprocess.run([node, '-e', guion, codigo, json.dumps(entrada_json), json.dumps(otros or {})],
                       capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_el_flujo_publicado_es_el_que_genera_el_script():
    assert json.loads((ROOT / 'n8n/etapa5/e5-1.json').read_text(encoding='utf-8')) == generar()


def test_estructura_conexiones_y_sin_secretos():
    f = generar()
    nombres = {n['name'] for n in f['nodes']}
    assert f['id'] == 'costflowE5_1' and f['active'] is False
    assert set(f['connections']) <= nombres
    assert all(d['node'] in nombres for c in f['connections'].values() for rama in c['main'] for d in rama)
    texto = json.dumps(f)
    assert 'x-api-key' not in texto and 'admin-secret' not in texto.lower()
    assert {n['notes'] for n in f['nodes'] if n.get('notes')} == {'CREDENCIAL_E4:internal', 'CREDENCIAL_E4:storage'}
    assert nodo('Generar cuadro')['parameters']['url'] == 'http://costflow-cuadro:8095/e5/generar'
    assert 'guardar_e5' in json.dumps(nodo('Guardar cuadro')) and 'fallo_e5' in json.dumps(nodo('Registrar fallo'))


def test_sin_plantilla_el_fallo_no_es_reintentable():
    codigo = nodo('Comprobar entrada')['parameters']['jsCode']
    tomada = {'Tomar cuadro pendiente': {'respuesta': {'cuadro_id': 'c1', 'token': 't1'}}}
    r = ejecutar(codigo, {'respuesta': {'resultado': 'entrada', 'plantilla': None}}, tomada)
    assert r[0]['json']['ok'] is False and r[0]['json']['recuperable'] is False and 'plantilla' in r[0]['json']['error']
    r = ejecutar(codigo, {'respuesta': {'resultado': 'entrada', 'plantilla': {'storage_file_id': 'f1'}}}, tomada)
    assert r[0]['json']['ok'] is True and r[0]['json']['storage_file_id'] == 'f1'
    assert ejecutar(codigo, {'respuesta': {'resultado': 'intento_vencido'}}, tomada) == []


def test_el_error_del_servicio_conserva_si_es_reintentable_y_el_exito_arma_el_archivo():
    codigo = nodo('Evaluar cuadro')['parameters']['jsCode']
    otros = {'Armar petición': {'cuadro_id': 'c1', 'token': 't1', 'codigo': 'MA-001', 'revision': 2}}
    r = ejecutar(codigo, {'ok': False, 'recuperable': False, 'error': 'Varias partidas'}, otros)
    assert r[0]['json'] == {'cuadro_id': 'c1', 'token': 't1', 'ok': False, 'recuperable': False, 'error': 'Varias partidas'}
    r = ejecutar(codigo, {'detail': 'caído'}, otros)
    assert r[0]['json']['recuperable'] is True
    r = ejecutar(codigo, {'ok': True, 'estado': 'borrador', 'validacion': {'avisos': []}, 'archivo_b64': 'AAAA'}, otros)
    assert r[0]['json']['nombre_archivo'] == 'cuadro-MA-001-rev2.xlsx' and r[0]['binary']['data']['fileName'] == 'cuadro-MA-001-rev2.xlsx'
    assert json.loads(r[0]['json']['metadata'])['metadata']['cuadro_id'] == 'c1'


def test_sin_identificador_de_storage_se_reintenta():
    codigo = nodo('Evaluar subida')['parameters']['jsCode']
    otros = {'Evaluar cuadro': {'cuadro_id': 'c1', 'token': 't1', 'estado': 'validado', 'validacion': {}, 'nombre_archivo': 'x.xlsx'}}
    assert ejecutar(codigo, {'error': 'x'}, otros)[0]['json']['recuperable'] is True
    r = ejecutar(codigo, {'processedFiles': [{'id': 'f9'}]}, otros)
    assert r[0]['json']['ok'] is True and r[0]['json']['storage_file_id'] == 'f9' and r[0]['json']['estado'] == 'validado'
