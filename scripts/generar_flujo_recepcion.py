"""Genera el JSON importable de n8n con las reglas de app/correo/deteccion.js."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


ROOT = Path(__file__).resolve().parents[1]
DESTINO = ROOT / 'n8n/flujos/detectar-respuestas-proveedores.json'
REGLAS = (ROOT / 'app/correo/deteccion.js').read_text(encoding='utf-8').split('module.exports =')[0]
REGLAS_PDF = (ROOT / 'app/recepcion/adjuntos.js').read_text(encoding='utf-8').split('module.exports =')[0]
URL_NHOST = 'https://zgorsmkvfyytsouacrpa.hasura.sa-east-1.nhost.run/v1/graphql'
URL_STORAGE = 'https://zgorsmkvfyytsouacrpa.storage.sa-east-1.nhost.run/v1/files'


def nodo(nombre, tipo, version, posicion, parametros, **extra):
    return dict(name=nombre, type='n8n-nodes-base.' + tipo, typeVersion=version,
                id=str(uuid5(NAMESPACE_URL, 'costflow-recepcion/' + nombre)),
                position=posicion, parameters=parametros, **extra)


def codigo(nombre, posicion, cuerpo):
    return nodo(nombre, 'code', 2, posicion, {'jsCode': REGLAS + '\n' + cuerpo})


def codigo_pdf(nombre, posicion, cuerpo):
    return nodo(nombre, 'code', 2, posicion, {'jsCode': REGLAS_PDF + '\n' + cuerpo})


def condicion(nombre, posicion, campo, valor):
    return nodo(nombre, 'if', 2.2, posicion, {
        'conditions': {'options': {'caseSensitive': True, 'leftValue': '',
                                    'typeValidation': 'strict', 'version': 2},
                       'conditions': [{'id': campo, 'leftValue': '={{ $json.' + campo + ' }}',
                                       'rightValue': valor, 'operator': {'type': 'string', 'operation': 'equals'}}],
                       'combinator': 'and'}, 'options': {},
    })


def consulta(nombre, posicion, cuerpo):
    return nodo(nombre, 'httpRequest', 4.2, posicion, {
        'method': 'POST', 'url': URL_NHOST,
        'authentication': 'genericCredentialType', 'genericAuthType': 'httpHeaderAuth',
        'sendBody': True, 'specifyBody': 'json', 'jsonBody': cuerpo,
        'options': {'timeout': 30000},
    })


def generar():
    query_envios = '''query EnviosDelRemitente($correo: String!) {
  envios_solicitud(where: {
    destinatario: { _ilike: $correo }, estado: { _in: ["enviado", "respondido"] }
  }) { id solicitud_id proveedor_id destinatario mensaje_id estado enviado_at }
}'''
    query_detalle = '''query DetalleRespuesta($solicitudId: uuid!, $proveedorId: uuid!) {
  solicitudes_cotizacion_by_pk(id: $solicitudId) {
    codigo nombre estado proyecto_asociado { nombre }
  }
  proveedores_by_pk(id: $proveedorId) { nombre }
}'''
    nodos = [
        nodo('Leer respuestas en Gmail', 'gmailTrigger', 1.4, [0, 0], {
            'pollTimes': {'item': [{'mode': 'everyMinute'}]}, 'event': 'messageReceived',
            'simple': True, 'maxResults': 50,
            'filters': {'readStatus': 'both', 'includeSpamTrash': False,
                        'includeDrafts': False, 'q': '-in:sent -in:drafts -in:spam -in:trash'},
            'options': {},
        }),
        codigo('Normalizar correo', [240, 0], '''return $input.all().flatMap((item, index) => {
  const correo = normalizarCorreo(item.json);
  return correo ? [{ json: { correo, patron_correo: patronCorreo(correo.remitente) }, pairedItem: { item: index } }] : [];
});'''),
        consulta('Buscar envíos al proveedor', [480, 0],
                 '={{ { query: ' + json.dumps(query_envios, ensure_ascii=False)
                 + ', variables: { correo: $json.patron_correo } } }}'),
        codigo('Preparar candidatos', [720, 0], '''return $input.all().flatMap((item, index) => {
  const correo = $('Normalizar correo').itemMatching(index).json.correo;
  return prepararCandidatos(item.json, correo).map(candidato => ({ json: candidato, pairedItem: { item: index } }));
});'''),
        nodo('Consultar envío original en Gmail', 'gmail', 2.1, [960, 0], {
            'resource': 'message', 'operation': 'get', 'messageId': '={{ $json.envio.mensaje_id }}',
            'simple': True, 'options': {},
        }, onError='continueRegularOutput'),
        codigo('Identificar respuestas', [1200, 0], '''const registros = $input.all().map((item, index) => ({
  ...$('Preparar candidatos').itemMatching(index).json, original: item.json,
}));
return identificarRespuestas(registros).map(deteccion => {
  const index = registros.findIndex(item => item.correo.gmail_message_id === deteccion.gmail_message_id);
  return { json: deteccion, pairedItem: { item: index } };
});'''),
        nodo('¿Solicitud identificada?', 'if', 2.2, [1440, 0], {
            'conditions': {'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'strict', 'version': 2},
                           'conditions': [{'id': 'es-respuesta', 'leftValue': '={{ $json.estado_deteccion }}',
                                           'rightValue': 'detectado', 'operator': {'type': 'string', 'operation': 'equals'}}],
                           'combinator': 'and'}, 'options': {},
        }),
        consulta('Consultar datos de la solicitud', [1680, -100],
                 '={{ { query: ' + json.dumps(query_detalle, ensure_ascii=False)
                 + ', variables: { solicitudId: $json.solicitud_id, proveedorId: $json.proveedor_id } } }}'),
        codigo('Respuesta de proveedor detectada', [1920, -100], '''return $input.all().map((item, index) => ({
  json: completarDeteccion(item.json, $('¿Solicitud identificada?').itemMatching(index).json),
  pairedItem: { item: index },
}));'''),
        nodo('Descargar adjuntos de la respuesta', 'gmail', 2.1, [2160, -100], {
            'resource': 'message', 'operation': 'get',
            'messageId': '={{ $json.gmail_message_id }}', 'simple': False,
            'options': {'downloadAttachments': True, 'dataPropertyAttachmentsPrefixName': 'adjunto_'},
        }),
        codigo_pdf('Preparar PDF del proveedor', [2400, -100], '''const items = $input.all();
const detecciones = items.map((item, index) => $('Respuesta de proveedor detectada').itemMatching(index).json);
return await prepararPdfs(items, detecciones,
  (index, clave) => this.helpers.getBinaryDataBuffer(index, clave));'''),
        condicion('¿Hay un PDF válido?', [2640, -100], 'estado_adjunto', 'pendiente'),
        nodo('Comprobar PDF en Nhost Storage', 'httpRequest', 4.2, [2880, -180], {
            'method': 'HEAD', 'url': '={{ ' + json.dumps(URL_STORAGE + '/') + ' + $json.storage_file_id }}',
            # Evita reutilizar un 404 guardado por la CDN antes de subir el PDF.
            'sendQuery': True, 'queryParameters': {'parameters': [
                {'name': 'costflow_check', 'value': "={{ $execution.id + '-' + $itemIndex + '-' + Date.now() }}"},
            ]},
            'authentication': 'genericCredentialType', 'genericAuthType': 'httpHeaderAuth',
            'options': {'timeout': 30000, 'response': {'response': {
                'fullResponse': True, 'neverError': True, 'responseFormat': 'text',
            }}},
        }),
        codigo_pdf('Comprobar si ya está guardado', [3120, -180], '''return $input.all().map((item, index) => ({
  ...comprobarExistencia(item.json, $('¿Hay un PDF válido?').itemMatching(index)),
  pairedItem: { item: index },
}));'''),
        condicion('¿Se debe subir el PDF?', [3360, -180], 'estado_adjunto', 'pendiente'),
        nodo('Guardar PDF en Nhost Storage', 'httpRequest', 4.2, [3600, -260], {
            'method': 'POST', 'url': URL_STORAGE,
            'authentication': 'genericCredentialType', 'genericAuthType': 'httpHeaderAuth',
            'sendBody': True, 'contentType': 'multipart-form-data',
            'bodyParameters': {'parameters': [
                {'parameterType': 'formData', 'name': 'bucket-id', 'value': 'cotizaciones'},
                {'parameterType': 'formData', 'name': 'metadata[]', 'value': '={{ JSON.stringify($json.metadata_storage) }}'},
                {'parameterType': 'formBinaryData', 'name': 'file[]', 'inputDataFieldName': 'pdf'},
            ]}, 'options': {'timeout': 120000},
        }),
        codigo_pdf('PDF guardado y vinculado', [3840, -260], '''return $input.all().map((item, index) => ({
  json: confirmarGuardado(item.json, $('¿Se debe subir el PDF?').itemMatching(index).json),
  pairedItem: { item: index },
}));'''),
        nodo('PDF ya guardado anteriormente', 'noOp', 1, [3600, 0], {}),
        nodo('Respuesta sin PDF o archivo rechazado', 'noOp', 1, [2880, 100], {}),
        nodo('Revisar conversación manualmente', 'noOp', 1, [1680, 160], {}),
        nodo('Cómo conectar este flujo', 'stickyNote', 1, [0, -320], {
            'content': '## Respuestas y PDF de proveedores\n1. Selecciona el MISMO Gmail del envío en los tres nodos Gmail.\n2. Selecciona Nhost Admin (Header Auth) en los cuatro nodos HTTP.\n3. Bucket: cotizaciones. Guarda TODOS los PDF adjuntos de respuestas identificadas.\n4. Prueba una respuesta con PDF; después publica/activa.\n\nLos archivos incluyen metadatos de solicitud, proveedor y correo. Evita volver a subir el mismo adjunto. No envía correos ni decide si una cotización es final.',
            'height': 280, 'width': 750,
        }),
    ]
    conexiones = {}
    def conectar(origen, destino, salida=0):
        ramas = conexiones.setdefault(origen, {'main': []})['main']
        while len(ramas) <= salida:
            ramas.append([])
        ramas[salida].append({'node': destino, 'type': 'main', 'index': 0})
    cadena = [n['name'] for n in nodos[:12]]
    for origen, destino in zip(cadena, cadena[1:]):
        conectar(origen, destino)
    conectar('¿Solicitud identificada?', 'Revisar conversación manualmente', 1)
    conectar('¿Hay un PDF válido?', 'Comprobar PDF en Nhost Storage')
    conectar('¿Hay un PDF válido?', 'Respuesta sin PDF o archivo rechazado', 1)
    conectar('Comprobar PDF en Nhost Storage', 'Comprobar si ya está guardado')
    conectar('Comprobar si ya está guardado', '¿Se debe subir el PDF?')
    conectar('¿Se debe subir el PDF?', 'Guardar PDF en Nhost Storage')
    conectar('¿Se debe subir el PDF?', 'PDF ya guardado anteriormente', 1)
    conectar('Guardar PDF en Nhost Storage', 'PDF guardado y vinculado')
    return {
        'id': 'costflowDetecta01',
        'name': 'CostFlow - Detectar respuestas de proveedores', 'nodes': nodos,
        'connections': conexiones, 'active': False, 'pinData': {},
        'settings': {'executionOrder': 'v1', 'timezone': 'America/Lima',
                     'saveDataSuccessExecution': 'all', 'saveDataErrorExecution': 'all'},
        'tags': [],
    }


if __name__ == '__main__':
    DESTINO.write_text(json.dumps(generar(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(DESTINO)
