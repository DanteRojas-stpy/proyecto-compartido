"""Completa una exportación E3.0 conservando sus nodos y credenciales.

Lee el cuerpo de los correos identificados y guarda sus PDF en cotizaciones.
No llama a IA ni envía mensajes. La salida conserva el contrato de E3.1.
"""

import argparse
import copy
import json
from pathlib import Path

from generar_flujo_recepcion import generar, nodo


LECTURA = r'''return $input.all().map((item, index) => {
  const deteccion = $('Respuesta de proveedor detectada').itemMatching(index).json;
  if (item.json.id !== deteccion.gmail_message_id || item.json.threadId !== deteccion.gmail_thread_id)
    throw new Error('El contenido descargado no corresponde al correo identificado.');
  const texto = String(item.json.text ?? item.json.textPlain ?? '');
  const html = String(item.json.html ?? item.json.textHtml ?? '');
  return { ...item, json: { ...item.json, lectura_correo: {
    ...deteccion, cuerpo_texto: texto, cuerpo_html: html,
    resumen_gmail: String(item.json.snippet ?? ''),
    estado_lectura_correo: texto || html ? 'leido' : 'sin_cuerpo',
  } }, pairedItem: { item: index } };
});'''


def completar(flujo):
    resultado = copy.deepcopy(flujo)
    nombres = {n['name'] for n in resultado['nodes']}
    if 'Respuesta de proveedor detectada' not in nombres:
        raise ValueError('El flujo no contiene la salida de detección E3.0.')
    gmail = next(n for n in resultado['nodes'] if n['type'] == 'n8n-nodes-base.gmail')
    nhost = next(n for n in resultado['nodes'] if n['name'] == 'Buscar envíos al proveedor')
    plantilla = generar()
    adicionales = plantilla['nodes'][9:19]
    for n in adicionales:
        if n['name'] not in nombres:
            if n['type'] == 'n8n-nodes-base.gmail':
                n['credentials'] = copy.deepcopy(gmail.get('credentials', {}))
            elif n['type'] == 'n8n-nodes-base.httpRequest':
                n['credentials'] = copy.deepcopy(nhost.get('credentials', {}))
            resultado['nodes'].append(n)
    for origen, ramas in plantilla['connections'].items():
        if origen in {n['name'] for n in adicionales}:
            resultado['connections'].setdefault(origen, copy.deepcopy(ramas))
    def conectar(origen, destino):
        resultado['connections'][origen] = {'main': [[{'node': destino, 'type': 'main', 'index': 0}]]}
    conectar('Respuesta de proveedor detectada', 'Descargar adjuntos de la respuesta')
    if 'Leer contenido del correo' not in nombres:
        resultado['nodes'].append(nodo('Leer contenido del correo', 'code', 2, [2310, -420], {'jsCode': LECTURA}))
    conectar('Descargar adjuntos de la respuesta', 'Leer contenido del correo')
    conectar('Leer contenido del correo', 'Preparar PDF del proveedor')
    preparar = next(n for n in resultado['nodes'] if n['name'] == 'Preparar PDF del proveedor')
    preparar['parameters']['jsCode'] = preparar['parameters']['jsCode'].replace(
        "$('Respuesta de proveedor detectada').itemMatching(index).json",
        'item.json.lectura_correo')
    comprobar = next(n for n in resultado['nodes'] if n['name'] == 'Comprobar PDF en Nhost Storage')
    comprobar['parameters']['sendQuery'] = True
    comprobar['parameters']['queryParameters'] = {'parameters': [
        {'name': 'costflow_check', 'value': "={{ $execution.id + '-' + $itemIndex + '-' + Date.now() }}"},
    ]}
    buscar = next(n for n in resultado['nodes'] if n['name'] == 'Buscar correos existentes en Gmail')
    buscar['parameters']['returnAll'] = True
    # Se revisa también lo ya leído: abrir un correo no debe excluirlo.
    buscar['parameters'].setdefault('filters', {})['readStatus'] = 'both'
    buscar['parameters']['filters']['q'] = '-in:sent -in:drafts -in:spam -in:trash'
    for n in resultado['nodes']:
        if n['name'] == 'Cómo conectar este flujo':
            n['parameters']['content'] = (
                '## E3.0: correos y PDF de proveedores\n'
                'Ejecutar «Revisar correos existentes». Incluye correos leídos y no leídos.\n'
                'Verifica remitente y conversación contra los envíos de Nhost.\n'
                '«Leer contenido del correo» muestra un elemento por correo, con su cuerpo.\n'
                'Guarda todos los PDF válidos en cotizaciones y reutiliza los ya guardados.\n'
                'Las dos salidas de PDF conservan los datos requeridos por E3.1.\n'
                'Esta etapa no solicita lectura IA ni envía correos.'
            )
    resultado['pinData'] = {}
    return resultado


def generar_e30():
    """Plantilla compartible sin cuentas, credenciales ni correos reales."""
    flujo = generar()
    flujo['id'] = 'costflowE30Detecta01'
    flujo['name'] = 'CostFlow - E3.0 Detectar respuestas de proveedores'
    flujo['nodes'][0] = nodo('Revisar correos existentes', 'manualTrigger', 1, [0, 0], {})
    flujo['nodes'].append(nodo('Buscar correos existentes en Gmail', 'gmail', 2.1, [0, 200], {
        'resource': 'message', 'operation': 'getAll', 'simple': True,
        'returnAll': True, 'filters': {'includeSpamTrash': False, 'readStatus': 'both'},
        'options': {},
    }))
    flujo['connections'].pop('Leer respuestas en Gmail')
    flujo['connections']['Revisar correos existentes'] = {'main': [[{
        'node': 'Buscar correos existentes en Gmail', 'type': 'main', 'index': 0}]]}
    flujo['connections']['Buscar correos existentes en Gmail'] = {'main': [[{
        'node': 'Normalizar correo', 'type': 'main', 'index': 0}]]}
    return completar(flujo)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('entrada', type=Path)
    parser.add_argument('salida', type=Path)
    args = parser.parse_args()
    dato = json.loads(args.entrada.read_text(encoding='utf-8-sig'))
    salida = [completar(dato[0])] if isinstance(dato, list) else completar(dato)
    args.salida.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
