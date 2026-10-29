"""Flujo de n8n de E4: estructura, lógica de cada paso y el camino completo contra una base real."""
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.homologacion import contrato, entrada
from app.homologacion.construir import build
from conftest import instalar
from datos_ficticios import ALFA, BETA, DELTA, GAMMA, SOLICITUD, V_ALFA, V_BETA, V_GAMMA, paquete, respuesta_modelo

ROOT = Path(__file__).resolve().parents[2]


def flujo():
    spec = importlib.util.spec_from_file_location('generador_e4', ROOT / 'n8n/etapa4/generar.py')
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.generate()[0]


def nodo(nombre):
    return next(n for n in flujo()['nodes'] if n['name'] == nombre)


def ejecutar(codigo, entrada_json, otros=None):
    """Ejecuta el código de un nodo con Node, simulando $json y $('Nodo').first().json."""
    node = shutil.which('node')
    if not node:
        pytest.skip('Esta prueba ejecuta el código de los nodos y requiere Node.js.')
    guion = ('const [codigo, json, otros] = process.argv.slice(1).map((x, i) => i ? JSON.parse(x) : x);'
             'const f = new Function("$json", "$", codigo);'
             'const $ = (n) => ({ first: () => ({ json: otros[n] }) });'
             'process.stdout.write(JSON.stringify(f(json, $)));')
    r = subprocess.run([node, '-e', guion, codigo, json.dumps(entrada_json), json.dumps(otros or {})],
                       capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_estructura_del_flujo():
    f = flujo()
    nombres = {n['name'] for n in f['nodes']}
    for origen, salidas in f['connections'].items():
        assert origen in nombres
        assert all(e['node'] in nombres for rama in salidas['main'] for e in rama)
    assert f['id'] == 'costflowE4_1' and f['active'] is False
    cola = nodo('Revisar la cola cada minuto')
    assert cola['type'] == 'n8n-nodes-base.scheduleTrigger' and cola['parameters']['rule']['interval'][0]['minutesInterval'] == 1
    assert all('credentials' not in n for n in f['nodes'])
    marcas = {n['name']: n['notes'] for n in f['nodes'] if 'notes' in n}
    assert set(marcas.values()) == {'CREDENCIAL_E4:internal', 'CREDENCIAL_E4:claude'}
    assert marcas['Claude Messages'] == 'CREDENCIAL_E4:claude'
    assert 'sk-ant' not in json.dumps(f)


def test_todo_fallo_llega_a_registrar_fallo_y_el_exito_a_guardar():
    f = flujo()['connections']
    for decision in ('¿Petición lista?', '¿Claude respondió bien?', '¿Pasó la validación?'):
        rama_ok, rama_error = f[decision]['main']
        assert rama_error[0]['node'] == 'Registrar fallo', decision
    assert f['¿Pasó la validación?']['main'][0][0]['node'] == 'Guardar homologación'
    assert f['¿Hay algo que homologar?']['main'][0][0]['node'] == 'Consultar entrada en Nhost'
    assert len(f['¿Hay algo que homologar?']['main']) == 1, 'sin trabajo pendiente el flujo termina'


def test_claude_se_llama_sin_parametros_que_los_modelos_5x_rechazan():
    claude = nodo('Claude Messages')['parameters']
    assert claude['url'] == 'https://api.anthropic.com/v1/messages'
    assert {'name': 'anthropic-version', 'value': '2023-06-01'} in claude['headerParameters']['parameters']
    assert claude['jsonBody'] == '={{ JSON.stringify($json.cuerpo_claude) }}', 'el modelo y los parámetros los fija el servicio'
    assert claude['options']['timeout'] >= 120000 and claude['options']['response']['response']['neverError'] is True


def test_las_expresiones_no_cierran_antes_de_tiempo():
    for n in flujo()['nodes']:
        cuerpo = n['parameters'].get('jsonBody', '')
        if cuerpo:
            assert cuerpo.count('{{') == 1 and cuerpo.count('}}') == 1, n['name']


def test_comprobar_entrada_termina_si_el_intento_vencio():
    codigo = nodo('Comprobar entrada')['parameters']['jsCode']
    tomada = {'Tomar homologación pendiente': {'respuesta': {'ejecucion_id': 'e1', 'token': 't1'}}}
    assert ejecutar(codigo, {'respuesta': {'resultado': 'intento_vencido'}}, tomada) == []
    salida = ejecutar(codigo, {'respuesta': {'resultado': 'entrada', 'paquete': {'x': 1}}}, tomada)
    assert salida[0]['json'] == {'ejecucion_id': 'e1', 'token': 't1', 'paquete': {'x': 1}}


def test_verificar_peticion():
    codigo = nodo('Verificar petición')['parameters']['jsCode']
    ctx = {'Comprobar entrada': {'ejecucion_id': 'e1', 'token': 't1', 'paquete': {'x': 1}}}
    ok = ejecutar(codigo, {'cuerpo_claude': {'model': 'm'}, 'modelo': 'claude-sonnet-5-5'}, ctx)[0]['json']
    assert ok['ok'] is True and ok['cuerpo_claude'] == {'model': 'm'} and ok['ejecucion_id'] == 'e1'
    malo = ejecutar(codigo, {'detail': 'Acceso interno no válido.'}, ctx)[0]['json']
    assert malo['ok'] is False and 'Acceso interno' in malo['error'] and malo['token'] == 't1'


@pytest.mark.parametrize('respuesta, texto_error', [
    ({'type': 'error', 'error': {'type': 'overloaded_error', 'message': 'Overloaded'}}, 'Overloaded'),
    ({'type': 'message', 'stop_reason': 'refusal', 'content': []}, 'seguridad'),
    ({'type': 'message', 'stop_reason': 'max_tokens', 'content': [{'type': 'text', 'text': '{'}], 'usage': {'output_tokens': 16000}}, '16000 tokens'),
])
def test_interpretar_los_errores_de_claude(respuesta, texto_error):
    codigo = nodo('Interpretar respuesta de Claude')['parameters']['jsCode']
    ctx = {'Verificar petición': {'ejecucion_id': 'e1', 'token': 't1', 'paquete': {}, 'modelo': 'claude-sonnet-5-5'}}
    salida = ejecutar(codigo, respuesta, ctx)[0]['json']
    assert salida['ok'] is False and texto_error in salida['error'] and salida['ejecucion_id'] == 'e1'


def test_interpretar_una_respuesta_completa():
    codigo = nodo('Interpretar respuesta de Claude')['parameters']['jsCode']
    ctx = {'Verificar petición': {'ejecucion_id': 'e1', 'token': 't1', 'paquete': {'p': 1}, 'modelo': 'claude-sonnet-5-5'}}
    respuesta = {'type': 'message', 'model': 'claude-sonnet-5-5', 'stop_reason': 'end_turn', 'usage': {'input_tokens': 10, 'output_tokens': 20},
                 'content': [{'type': 'thinking', 'thinking': ''}, {'type': 'text', 'text': '{"a":'}, {'type': 'text', 'text': '1}'}]}
    salida = ejecutar(codigo, respuesta, ctx)[0]['json']
    assert salida == {'ejecucion_id': 'e1', 'token': 't1', 'paquete': {'p': 1}, 'ok': True, 'texto': '{"a":1}',
                      'modelo': 'claude-sonnet-5-5', 'tokens_entrada': 10, 'tokens_salida': 20}


def test_evaluar_resultado_del_servicio():
    codigo = nodo('Evaluar resultado')['parameters']['jsCode']
    ctx = {'Interpretar respuesta de Claude': {'ejecucion_id': 'e1', 'token': 't1', 'paquete': {}, 'modelo': 'm', 'tokens_entrada': 1, 'tokens_salida': 2}}
    ok = ejecutar(codigo, {'resultado': 'construida', 'homologacion': {'h': 1}, 'estado_revision': 'requiere_revision',
                           'version_ids': ['v'], 'huella': 'abc'}, ctx)[0]['json']
    assert ok['ok'] is True and ok['resultado'] == {'h': 1} and ok['huella'] == 'abc' and ok['tokens_salida'] == 2
    malo = ejecutar(codigo, {'resultado': 'respuesta_invalida', 'errores': ['Partida X: el ítem no pertenece']}, ctx)[0]['json']
    assert malo['ok'] is False and 'no pasó la validación' in malo['error'] and 'no pertenece' in malo['error']
    caido = ejecutar(codigo, {'detail': 'Internal error'}, ctx)[0]['json']
    assert caido['ok'] is False and 'Internal error' in caido['error']


def test_el_servicio_tiene_imagen_y_compose():
    dockerfile = (ROOT / 'app/homologacion/Dockerfile').read_text(encoding='utf-8')
    assert 'app.homologacion.server:app' in dockerfile and '8094' in dockerfile
    assert 'tesseract' not in dockerfile, 'E4 no lee documentos'
    compose = (ROOT / 'compose.etapa4.yml').read_text(encoding='utf-8')
    for texto in ('costflow-homologacion', 'costflow_e3', 'external: true', 'E4_MODELO: claude-sonnet-5-5', '127.0.0.1:8094:8094', 'env_file: .env.e3'):
        assert texto in compose, texto
    assert 'sk-ant' not in compose and 'KEY=' not in compose


def test_camino_completo_contra_una_base_real(postgres):
    """Lo que entrega Nhost alimenta al servicio, la respuesta del modelo se valida y el resultado se guarda y avisa."""
    sql = postgres
    instalar(sql)
    datos = paquete()
    usuario, proyecto = '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001'
    sentencias = [f"INSERT INTO auth.users VALUES ('{usuario}');",
                  f"INSERT INTO public.proyectos(id,responsable_id,codigo,nombre) VALUES('{proyecto}','{usuario}','P-10','Obra ficticia');",
                  f"INSERT INTO public.solicitudes_cotizacion(id,proyecto_id,creado_por,nombre,moneda,vigencia_dias,fecha_limite,tipo) "
                  f"VALUES('{SOLICITUD}','{proyecto}','{usuario}','Elevadores','USD',30,current_date+30,'MA');",
                  f"SELECT set_config('costflow.e3_actor','{usuario}',false);"]
    for p in datos['proveedores']:
        estado = 'respondio' if p['id'] != DELTA else 'invitado'
        sentencias.append(f"INSERT INTO public.proveedores(id,creado_por,nombre) VALUES('{p['id']}','{usuario}','{p['nombre']}');")
        sentencias.append(f"INSERT INTO public.solicitud_proveedores(solicitud_id,proveedor_id,estado) VALUES('{SOLICITUD}','{p['id']}','{estado}');")
    for n, f in enumerate(datos['finales'], 1):
        correo = f'60000000-0000-0000-0000-00000000000{n}'
        sentencias += [
            f"INSERT INTO public.correos_proveedor(id,solicitud_id,proveedor_id,gmail_message_id,remitente,recibido_at,estado_correo,origen_estado,estado_asignado_por,adjuntos) "
            f"VALUES('{correo}','{SOLICITUD}','{f['proveedor_id']}','e4-{n}','p@example.invalid',now(),'cotizacion_o_ficha_tecnica_recibida','usuario','{usuario}','[{{\"nombre\":\"x.pdf\"}}]'::jsonb);",
            f"INSERT INTO public.versiones_cotizacion(id,solicitud_id,proveedor_id,version,origen,correo_id) VALUES('{f['version_id']}','{SOLICITUD}','{f['proveedor_id']}',1,'correo','{correo}');",
            f"INSERT INTO public.e3_resultados(version_id,correo_id,solicitud_id,proveedor_id,resultado,modelo,uso_ocr,uso_rag) "
            f"VALUES('{f['version_id']}','{correo}','{SOLICITUD}','{f['proveedor_id']}',$j${json.dumps(f['resultado'])}$j$::jsonb,'claude-opus-5-5',false,false);",
            f"UPDATE public.versiones_cotizacion SET es_final=true,estado_procesamiento='completado_con_observaciones',estado='vigente' WHERE id='{f['version_id']}';",
            f"UPDATE public.correos_proveedor SET estado_correo='cotizacion_o_ficha_tecnica_aceptada_final' WHERE id='{correo}';"]
    sql('\n'.join(sentencias))

    def operar(operacion, datos_json):
        return json.loads(sql(f"SELECT public.e4_operar('{operacion}',$j${json.dumps(datos_json)}$j$::jsonb)::text;"))

    # 1. El especialista pulsa «Homologar».
    r = operar('solicitar_e4', {'solicitud_id': SOLICITUD, 'usuario_id_verificado': usuario})
    assert r['ok'] is True and r['finales'] == 3
    # 2. n8n toma la cola y pide la entrada.
    tomada = operar('tomar_e4', {})
    assert tomada['resultado'] == 'tomada'
    entrada_e4 = operar('entrada_e4', {'ejecucion_id': tomada['ejecucion_id'], 'token': tomada['token']})
    assert entrada_e4['resultado'] == 'entrada'
    # 3. El servicio prepara lo que ve el modelo con los datos reales de Nhost.
    preparado = entrada.prepare(entrada_e4['paquete'])
    assert {p['proveedor_id'] for p in preparado['postores']} == {ALFA, BETA, GAMMA}
    assert preparado['sin_final'] == [{'proveedor_id': DELTA, 'nombre': 'Delta SRL'}]
    assert preparado['base']['tipo'] == 'provisional'
    assert sorted(preparado['version_ids']) == sorted([V_ALFA, V_BETA, V_GAMMA])
    assert 'DRAFT' not in json.dumps(preparado['postores'][0]['decisiones'])
    assert all(p['decisiones'] == [] or p['decisiones'][0]['accion'] for p in preparado['postores'])
    cuerpo = contrato.request(preparado, 'claude-sonnet-5-5')
    assert cuerpo['model'] == 'claude-sonnet-5-5'
    # 4. Respuesta del modelo (simulada) -> validación -> guardado.
    homologacion = build(preparado, contrato.parse_text(json.dumps(respuesta_modelo(preparado))), 'claude-sonnet-5-5')
    assert homologacion['estado_revision'] == 'requiere_revision'
    guardada = operar('guardar_e4', {'ejecucion_id': tomada['ejecucion_id'], 'token': tomada['token'], 'estado_revision': homologacion['estado_revision'],
                                      'resultado': homologacion, 'version_ids': preparado['version_ids'], 'huella': preparado['huella'],
                                      'modelo': 'claude-sonnet-5-5', 'tokens_entrada': 10800, 'tokens_salida': 5000})
    assert guardada['resultado'] == 'guardada'
    estado = sql(f"SELECT e4_estado||'|'||estado_revision||'|'||e4_modelo FROM public.e4_estado_solicitud WHERE solicitud_id='{SOLICITUD}';")
    assert estado == 'completado|requiere_revision|claude-sonnet-5-5'
    assert sql(f"SELECT count(*) FROM public.notificaciones WHERE tipo='homologacion_lista' AND usuario_id='{usuario}';") == '1'
    guardado = json.loads(sql(f"SELECT resultado::text FROM public.e4_homologaciones WHERE solicitud_id='{SOLICITUD}';"))
    assert guardado['trazabilidad']['huella'] == preparado['huella'] and len(guardado['postores']) == 3
    # 5. Con una homologación guardada, el especialista puede pedir el cuadro (como borrador por sus pendientes).
    cuadro = operar('solicitar_e5', {'solicitud_id': SOLICITUD, 'usuario_id_verificado': usuario})
    assert cuadro['ok'] is True and 'borrador' in cuadro['mensaje']
