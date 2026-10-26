"""Genera el JSON importable de n8n con las reglas de app/correo/deteccion.js."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


ROOT = Path(__file__).resolve().parents[1]
DESTINO = ROOT / 'n8n/flujos/detectar-respuestas-proveedores.json'
REGLAS = (ROOT / 'app/correo/deteccion.js').read_text(encoding='utf-8').split('module.exports =')[0]
URL_NHOST = 'https://zgorsmkvfyytsouacrpa.graphql.sa-east-1.nhost.run/v1'


def nodo(nombre, tipo, version, posicion, parametros, **extra):
    return dict(name=nombre, type='n8n-nodes-base.' + tipo, typeVersion=version,
                id=str(uuid5(NAMESPACE_URL, 'costflow-recepcion/' + nombre)),
                position=posicion, parameters=parametros, **extra)


def codigo(nombre, posicion, cuerpo):
    return nodo(nombre, 'code', 2, posicion, {'jsCode': REGLAS + '\n' + cuerpo})


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
        nodo('Revisar conversación manualmente', 'noOp', 1, [1680, 160], {}),
        nodo('Cómo conectar este flujo', 'stickyNote', 1, [0, -320], {
            'content': '## Detector de respuestas de proveedores\n1. Selecciona el MISMO Gmail del envío en los dos nodos Gmail.\n2. Selecciona Nhost Admin (Header Auth) en los dos nodos HTTP.\n3. Prueba con una respuesta al correo original.\n4. Publica/activa cuando termines la conexión.\n\nSolo lee y muestra resultados. No envía correos, no modifica Nhost y no decide si una cotización es final. Lee nuevos mensajes, incluso si ya los abriste.',
            'height': 280, 'width': 750,
        }),
    ]
    conexiones = {}
    def conectar(origen, destino, salida=0):
        ramas = conexiones.setdefault(origen, {'main': []})['main']
        while len(ramas) <= salida:
            ramas.append([])
        ramas[salida].append({'node': destino, 'type': 'main', 'index': 0})
    cadena = [n['name'] for n in nodos[:9]]
    for origen, destino in zip(cadena, cadena[1:]):
        conectar(origen, destino)
    conectar('¿Solicitud identificada?', 'Revisar conversación manualmente', 1)
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
