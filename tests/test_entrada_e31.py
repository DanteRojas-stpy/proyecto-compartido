import copy
import importlib.util
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('entrada_e31', ROOT / 'scripts/asegurar_entrada_e31.py')
modulo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modulo)


def ejecutar_js(codigo, items, contexto=None):
    programa = """const p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
try { const result=new Function('$input','$',p.codigo)(
  {all:()=>p.items},name=>({itemMatching:i=>p.contexto[name][i]}));
  console.log(JSON.stringify({resultado:result}));
} catch(error) { console.log(JSON.stringify({error:error.message})); }"""
    r = subprocess.run(['node', '-e', programa],
                       input=json.dumps({'codigo': codigo, 'items': items, 'contexto': contexto or {}}),
                       capture_output=True, encoding='utf-8', check=True)
    return json.loads(r.stdout)


def documento():
    return {'solicitud_id': '11111111-1111-4111-8111-111111111111',
            'proveedor_id': '22222222-2222-4222-8222-222222222222',
            'storage_file_id': '33333333-3333-4333-8333-333333333333',
            'nombre_original': 'ficha.pdf', 'gmail_message_id': 'correo-prueba',
            'tamano_bytes': 123, 'metadata_storage': {'tipo': 'prueba'}}


def test_datos_vacios_producen_un_error_claro():
    resultado = ejecutar_js(modulo.VALIDACION, [{'json': {}}])
    assert 'E3.1 recibió datos vacíos' in resultado['error']
    assert 'storage_file_id' in resultado['error']
    assert 'detector' in resultado['error']


def test_pasa_todos_los_archivos_y_campos_sin_perder_datos():
    items = [{'json': {**documento(), 'gmail_message_id': 'correo-' + str(i)}} for i in range(4)]
    assert ejecutar_js(modulo.VALIDACION, items)['resultado'] == items


def test_lote_mixto_no_descarta_silenciosamente_un_archivo_invalido():
    resultado = ejecutar_js(modulo.VALIDACION, [{'json': documento()}, {'json': {}}])
    assert 'archivo 2' in resultado['error']


def test_detector_espera_a_e31_y_conserva_lote_y_credenciales():
    flujo = {'nodes': [
        {'name': 'PDF guardado y vinculado'}, {'name': 'PDF ya guardado anteriormente'},
        {'name': 'Registrar cotización (E3.1)', 'type': 'n8n-nodes-base.executeWorkflow',
         'credentials': {'ejemplo': {'id': 'referencia'}},
         'parameters': {'workflowId': {'value': 'costflowE3Recep01'}, 'mode': 'each',
                        'options': {'waitForSubWorkflow': False}}},
    ], 'connections': {}}
    for node in flujo['nodes']:
        node.setdefault('type', 'n8n-nodes-base.noOp')
    antes = copy.deepcopy(flujo)
    resultado = modulo.asegurar_detector(flujo)
    assert flujo == antes
    llamada = resultado['nodes'][-1]
    assert llamada['parameters']['mode'] == 'once'
    assert llamada['parameters']['options']['waitForSubWorkflow'] is True
    assert llamada['parameters']['workflowInputs']['convertFieldsToString'] is False
    assert llamada['credentials'] == flujo['nodes'][-1]['credentials']
    assert modulo.asegurar_detector(resultado) == resultado


def test_guardia_y_estado_de_lectura_son_idempotentes_y_no_reescriben_la_recepcion():
    flujo = {'nodes': [
        {'name': 'Desde detección de respuestas', 'parameters': {'inputSource': 'workflowInputs'}},
        {'name': 'Normalizar recepción', 'parameters': {'jsCode': 'codigo existente'}},
        {'name': 'Archivos registrados', 'parameters': {}},
        {'name': 'Leer versión (E3.2)', 'type': 'n8n-nodes-base.executeWorkflow',
         'position': [200, 0], 'parameters': {'workflowId': {'value': 'costflowE3Lectu01'}}},
    ], 'connections': {'Archivos registrados': {'main': [[{'node': 'Leer versión (E3.2)', 'type': 'main', 'index': 0}]]}}}
    for node in flujo['nodes']:
        node.setdefault('type', 'n8n-nodes-base.code')
    resultado = modulo.asegurar_recepcion(flujo)
    assert modulo.asegurar_recepcion(resultado) == resultado
    assert resultado['nodes'][1]['parameters']['jsCode'] == 'codigo existente'
    estado = next(n for n in resultado['nodes'] if n['name'].startswith('Estado de lectura:'))
    contexto = {'Archivos registrados': [{'json': {'version_id': 'version-1'}}]}
    salida = ejecutar_js(estado['parameters']['jsCode'],
                         [{'json': {'error': 'Workflow is not active and cannot be executed.'}}], contexto)['resultado']
    assert salida[0]['json']['estado_recepcion'] == 'registrado'
    assert salida[0]['json']['estado_lectura'] == 'pendiente'
    assert salida[0]['json']['version_id'] == 'version-1'


def test_variante_integrada_conserva_todos_los_nodos_y_no_duplica_la_recepcion():
    flujo = {'nodes': [
        {'name': 'Normalizar recepción', 'position': [1000, 0], 'parameters': {'jsCode': 'original'}},
        {'name': 'Leer con Claude', 'parameters': {'credencial': 'referencia'}},
    ], 'connections': {}}
    for origen in ('PDF guardado y vinculado', 'PDF ya guardado anteriormente'):
        flujo['nodes'].append({'name': origen})
        flujo['connections'][origen] = {'main': [[{'node': 'Normalizar recepción', 'type': 'main', 'index': 0}]]}
    for n in flujo['nodes']:
        n['type'] = 'n8n-nodes-base.code'
    resultado = modulo.asegurar_detector(flujo)
    assert len(resultado['nodes']) == len(flujo['nodes']) + 1
    assert resultado['nodes'][:len(flujo['nodes'])] == flujo['nodes']
    assert not any(n['type'] == 'n8n-nodes-base.executeWorkflow' for n in resultado['nodes'])
    assert modulo.asegurar_detector(resultado) == resultado
