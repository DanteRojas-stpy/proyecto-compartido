"""Corrige el contrato detector -> E3.1 sin cambiar credenciales ni otros nodos."""

import argparse
import copy
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


VALIDACION = r'''const items = $input.all();
if (!items.length) throw new Error('E3.1 no recibió archivos del detector.');
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const invalidos = items.flatMap((item, index) => {
  const d = item.json ?? {};
  const faltan = ['solicitud_id', 'proveedor_id', 'storage_file_id']
    .filter(c => !uuid.test(String(d[c] ?? '').trim()));
  if (!String(d.nombre_original ?? d.nombre_archivo ?? '').trim()) faltan.push('nombre_original');
  if (!String(d.gmail_message_id ?? '').trim()) faltan.push('gmail_message_id');
  return faltan.length ? [`archivo ${index + 1}: ${faltan.join(', ')}`] : [];
});
if (invalidos.length) throw new Error(
  'E3.1 recibió datos vacíos o incompletos (' + invalidos.join('; ') + '). '
  + 'Ejecuta el flujo detector con la salida de los PDF guardados. '
  + 'Ejecutar este subflujo solo, sin datos de entrada, no recupera detecciones anteriores.'
);
return items;'''


def identificador(nombre):
    return str(uuid5(NAMESPACE_URL, 'costflow-entrada-e31/' + nombre))


def asegurar_detector(flujo):
    resultado = copy.deepcopy(flujo)
    llamadas = [n for n in resultado['nodes']
                if n['type'] == 'n8n-nodes-base.executeWorkflow'
                and (n['parameters'].get('workflowId') == 'costflowE3Recep01'
                     or (isinstance(n['parameters'].get('workflowId'), dict)
                         and n['parameters']['workflowId'].get('value') == 'costflowE3Recep01'))]
    if not llamadas and any(n['name'] == 'Normalizar recepción' for n in resultado['nodes']):
        # Variante integrada: E3.1 ya está dentro del detector. No se añade
        # otra llamada que duplicaría la recepción ni se elimina ningún nodo.
        nombre = 'Validar datos recibidos del detector'
        guardia = next((n for n in resultado['nodes'] if n['name'] == nombre), None)
        if guardia is None:
            normalizar = next(n for n in resultado['nodes'] if n['name'] == 'Normalizar recepción')
            guardia = {'id': identificador(nombre), 'name': nombre,
                       'type': 'n8n-nodes-base.code', 'typeVersion': 2,
                       'position': [normalizar['position'][0] - 240, normalizar['position'][1] - 180],
                       'parameters': {}}
            resultado['nodes'].append(guardia)
        guardia['parameters']['jsCode'] = VALIDACION
        for origen in ('PDF guardado y vinculado', 'PDF ya guardado anteriormente'):
            ramas = resultado['connections'][origen]['main']
            for rama in ramas:
                for conexion in rama:
                    if conexion['node'] == 'Normalizar recepción':
                        conexion['node'] = nombre
            if not any(c['node'] == nombre for rama in ramas for c in rama):
                raise ValueError('La salida de PDF no está conectada a la recepción: ' + origen)
        resultado['connections'][nombre] = {'main': [[{'node': 'Normalizar recepción', 'type': 'main', 'index': 0}]]}
        return resultado
    if len(llamadas) != 1:
        raise ValueError('Se esperaba una sola llamada existente del detector a E3.1.')
    p = llamadas[0]['parameters']
    p['source'] = 'database'
    p['mode'] = 'once'
    # El subflujo recibe todos los campos y todos los archivos del correo.
    p['workflowInputs'] = {'mappingMode': 'defineBelow', 'value': {},
                           'matchingColumns': [], 'schema': [],
                           'attemptToConvertTypes': False, 'convertFieldsToString': False}
    p.setdefault('options', {})['waitForSubWorkflow'] = True
    llamadas[0].pop('disabled', None)
    for origen in ('PDF guardado y vinculado', 'PDF ya guardado anteriormente'):
        if not any(n['name'] == origen for n in resultado['nodes']):
            raise ValueError('Falta el nodo ' + origen)
        ramas = resultado.setdefault('connections', {}).setdefault(origen, {'main': [[]]})['main']
        if not ramas:
            ramas.append([])
        if not any(c['node'] == llamadas[0]['name'] for c in ramas[0]):
            ramas[0].append({'node': llamadas[0]['name'], 'type': 'main', 'index': 0})
    return resultado


def asegurar_recepcion(flujo):
    resultado = copy.deepcopy(flujo)
    disparador = next(n for n in resultado['nodes'] if n['name'] == 'Desde detección de respuestas')
    disparador['parameters']['inputSource'] = 'passthrough'
    nombre = 'Validar datos recibidos del detector'
    guardia = next((n for n in resultado['nodes'] if n['name'] == nombre), None)
    if guardia is None:
        guardia = {'id': identificador(nombre), 'name': nombre,
                   'type': 'n8n-nodes-base.code', 'typeVersion': 2,
                   'position': [240, -180], 'parameters': {}}
        resultado['nodes'].append(guardia)
    guardia['parameters']['jsCode'] = VALIDACION
    conexiones = resultado['connections']
    conexiones[disparador['name']] = {'main': [[{'node': nombre, 'type': 'main', 'index': 0}]]}
    conexiones[nombre] = {'main': [[{'node': 'Normalizar recepción', 'type': 'main', 'index': 0}]]}

    # La recepción ya quedó guardada antes de intentar la lectura con IA.
    # Un E3.2 sin publicar/configurar queda pendiente y conserva su versión.
    llamadas = [n for n in resultado['nodes'] if n['type'] == 'n8n-nodes-base.executeWorkflow'
                and (n['parameters'].get('workflowId') == 'costflowE3Lectu01'
                     or (isinstance(n['parameters'].get('workflowId'), dict)
                         and n['parameters']['workflowId'].get('value') == 'costflowE3Lectu01'))]
    for llamada in llamadas:
        previa = next((origen for origen, ramas in conexiones.items()
                       if any(c['node'] == llamada['name'] for rama in ramas['main'] for c in rama)), None)
        if not previa:
            raise ValueError('La llamada a E3.2 no tiene nodo de entrada.')
        llamada['onError'] = 'continueRegularOutput'
        estado_nombre = 'Estado de lectura: ' + llamada['name']
        estado = next((n for n in resultado['nodes'] if n['name'] == estado_nombre), None)
        if estado is None:
            estado = {'id': identificador(estado_nombre), 'name': estado_nombre,
                      'type': 'n8n-nodes-base.code', 'typeVersion': 2,
                      'position': [llamada['position'][0] + 240, llamada['position'][1]],
                      'parameters': {}}
            resultado['nodes'].append(estado)
        estado['parameters']['jsCode'] = '''return $input.all().map((item, index) => {
  const origen = $(''' + json.dumps(previa, ensure_ascii=False) + ''').itemMatching(index).json;
  const error = item.json.error;
  return { json: { ...origen, estado_recepcion: 'registrado',
    estado_lectura: error ? 'pendiente' : 'enviada_a_e32',
    motivo_lectura: error ? String(error.message ?? error).slice(0, 500) : null,
  }, pairedItem: { item: index } };
});'''
        if llamada['name'] not in conexiones or not any(
                c['node'] == estado_nombre for rama in conexiones[llamada['name']]['main'] for c in rama):
            conexiones[estado_nombre] = copy.deepcopy(conexiones.get(llamada['name'], {'main': [[]]}))
        conexiones[llamada['name']] = {'main': [[{'node': estado_nombre, 'type': 'main', 'index': 0}]]}
    return resultado


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tipo', choices=['detector', 'recepcion'])
    parser.add_argument('entrada', type=Path)
    parser.add_argument('salida', type=Path)
    args = parser.parse_args()
    contenido = json.loads(args.entrada.read_text(encoding='utf-8-sig'))
    arreglo = isinstance(contenido, list)
    flujo = contenido[0] if arreglo else contenido
    actualizado = (asegurar_detector if args.tipo == 'detector' else asegurar_recepcion)(flujo)
    args.salida.write_text(json.dumps([actualizado] if arreglo else actualizado,
                                     ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Preparado:', actualizado['name'])


if __name__ == '__main__':
    main()
