"""El lector puede usar Claude sin cambiar el servicio: n8n traduce entre ambos formatos."""
import importlib.util
import json
import shutil
import subprocess

import pytest

from pathlib import Path

from app.etapa3 import contract
from test_contrato import sample

ROOT = Path(__file__).resolve().parents[2]


def flujo_lectura():
    spec = importlib.util.spec_from_file_location('generador', ROOT / 'n8n/etapa3/generar.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return next(f for f in module.generate() if f['id'] == 'costflowEtapa3_2')


def nodo(flujo, nombre):
    return next(n for n in flujo['nodes'] if n['name'] == nombre)


def ejecutar_nodo(codigo, entrada):
    node = shutil.which('node')
    if not node:
        pytest.skip('Esta prueba ejecuta el código de los nodos y requiere Node.js.')
    guion = ('const f = new Function("$json", process.argv[1]);'
             'const out = f(JSON.parse(process.argv[2]));'
             'process.stdout.write(JSON.stringify(out));')
    resultado = subprocess.run([node, '-e', guion, codigo, json.dumps(entrada)],
                               capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert resultado.returncode == 0, resultado.stderr
    return json.loads(resultado.stdout)[0]['json']


def test_el_modelo_decide_entre_claude_y_gemini():
    flujo = flujo_lectura()
    conexiones = flujo['connections']
    assert conexiones['Preparar petición estructurada']['main'][0][0]['node'] == '¿Modelo de Claude?'
    ramas = conexiones['¿Modelo de Claude?']['main']
    assert ramas[0][0]['node'] == 'Convertir a Claude'
    assert ramas[1][0]['node'] == 'Gemini JSON fijo'
    condicion = nodo(flujo, '¿Modelo de Claude?')['parameters']['conditions']['conditions'][0]
    assert condicion['rightValue'] == 'claude-' and condicion['operator']['operation'] == 'startsWith'
    for origen in ('Claude a formato del lector', 'Gemini JSON fijo'):
        assert conexiones[origen]['main'][0][0]['node'] == 'Devolver respuesta del lector'


def test_nodo_de_claude_no_lleva_claves_y_exige_su_credencial():
    nodo_claude = nodo(flujo_lectura(), 'Claude Messages')
    assert nodo_claude['notes'] == 'CREDENCIAL_E3:claude'
    assert 'credentials' not in nodo_claude
    parametros = nodo_claude['parameters']
    assert parametros['url'] == 'https://api.anthropic.com/v1/messages'
    assert parametros['genericAuthType'] == 'httpHeaderAuth'
    assert {'name': 'anthropic-version', 'value': '2023-06-01'} in parametros['headerParameters']['parameters']
    assert 'sk-ant' not in json.dumps(nodo_claude)


def test_la_peticion_se_traduce_al_formato_de_claude():
    flujo = flujo_lectura()
    data, source, context = sample()
    peticion = contract.request([{'id': 'f1', 'documento_id': source['documento_id'], 'texto': 'precio USD 100'}],
                                [{'documento_id': source['documento_id'], 'nombre_original': 'cotizacion.pdf'}])
    salida = ejecutar_nodo(nodo(flujo, 'Convertir a Claude')['parameters']['jsCode'],
                           {'modelo': 'claude-opus-5-5', 'peticion': peticion})
    cuerpo = salida['cuerpo']
    assert cuerpo['model'] == 'claude-opus-5-5' and cuerpo['max_tokens'] == 16000
    assert contract.SYSTEM.strip() in cuerpo['system'] and '"comerciales"' in cuerpo['system']
    assert cuerpo['messages'][0]['role'] == 'user' and 'precio USD 100' in cuerpo['messages'][0]['content']
    # Parámetros que los modelos 5.x rechazan o que no se necesitan.
    assert not {'temperature', 'top_p', 'top_k', 'tool_choice', 'thinking'} & set(cuerpo)
    assert cuerpo['output_config'] == {'effort': 'low'}


def test_esfuerzo_bajo_solo_en_modelos_que_lo_admiten():
    codigo = nodo(flujo_lectura(), 'Convertir a Claude')['parameters']['jsCode']
    peticion = {'contents': [{'parts': [{'text': 'texto'}]}], 'generationConfig': {}}
    for modelo, esperado in (('claude-opus-5-5', True), ('claude-sonnet-5-5', True), ('claude-haiku-5-5', True),
                             ('claude-sonnet-4-6', False), ('claude-haiku-4-5', False)):
        cuerpo = ejecutar_nodo(codigo, {'modelo': modelo, 'peticion': peticion})['cuerpo']
        assert ('output_config' in cuerpo) is esperado, modelo


@pytest.mark.parametrize('envoltura', ['{}', '```json\n{}\n```', 'Aquí está:\n{}\nListo.'])
def test_la_respuesta_de_claude_la_lee_el_servicio_sin_cambios(envoltura):
    flujo = flujo_lectura()
    data, source, context = sample()
    respuesta = {'type': 'message', 'model': 'claude-opus-5-5', 'stop_reason': 'end_turn',
                 'content': [{'type': 'thinking', 'thinking': ''},
                             {'type': 'text', 'text': envoltura.replace('{}', json.dumps(data))}],
                 'usage': {'input_tokens': 10, 'output_tokens': 20}}
    salida = ejecutar_nodo(nodo(flujo, 'Claude a formato del lector')['parameters']['jsCode'], respuesta)
    assert contract.parse_response(salida) == data


def test_errores_de_claude_llegan_como_error_legible():
    codigo = nodo(flujo_lectura(), 'Claude a formato del lector')['parameters']['jsCode']
    saturado = ejecutar_nodo(codigo, {'type': 'error', 'error': {'type': 'overloaded_error', 'message': 'Overloaded'}})
    with pytest.raises(ValueError, match='Overloaded'):
        contract.parse_response(saturado)
    cortado = ejecutar_nodo(codigo, {'type': 'message', 'stop_reason': 'max_tokens',
                                     'content': [{'type': 'text', 'text': '{"a":'}],
                                     'usage': {'output_tokens': 16000}})
    with pytest.raises(ValueError, match=r'respuesta completa \(max_tokens; salida: 16000 tokens\)'):
        contract.parse_response(cortado)
    rechazo = ejecutar_nodo(codigo, {'type': 'message', 'stop_reason': 'refusal', 'content': []})
    with pytest.raises(ValueError, match='seguridad'):
        contract.parse_response(rechazo)
