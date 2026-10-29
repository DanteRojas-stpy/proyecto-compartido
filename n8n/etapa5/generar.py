"""Genera el flujo de E5 (cuadro comparativo) para n8n; nunca incluye valores de credenciales.

Reutiliza la clase Flow del generador de E4. Las credenciales se asignan por nombre al preparar n8n.
"""
from __future__ import annotations

import importlib.util
import json
import uuid
from pathlib import Path

_e4 = importlib.util.spec_from_file_location("generar_e4", Path(__file__).parent.parent / "etapa4" / "generar.py")
e4 = importlib.util.module_from_spec(_e4)
_e4.loader.exec_module(e4)

IDS = {"1": "costflowE5_1"}
STORAGE = "https://SUBDOMINIO.storage.REGION.nhost.run/v1/files"
SERVICIO = "http://costflow-cuadro:8095"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

COMPROBAR_ENTRADA = """// Sigue solo si Nhost entregó la entrada de este cuadro; si el intento venció, termina sin hacer nada.
const tomada = $('Tomar cuadro pendiente').first().json.respuesta;
const entrada = $json.respuesta;
if (entrada?.resultado !== 'entrada') return [];
const base = { cuadro_id: tomada.cuadro_id, token: tomada.token, entrada };
if (!entrada.plantilla?.storage_file_id) {
  return [{ json: { ...base, ok: false, recuperable: false, error: 'La solicitud no tiene cargada la plantilla del cuadro comparativo.' } }];
}
return [{ json: { ...base, ok: true, storage_file_id: entrada.plantilla.storage_file_id } }];"""

ARMAR_PETICION = """// Une la plantilla descargada con la homologación y el tipo de cambio para el servicio de E5.
const ctx = $('Comprobar entrada').first().json;
const buffer = await this.helpers.getBinaryDataBuffer(0, 'data');
const e = ctx.entrada;
return [{ json: { cuadro_id: ctx.cuadro_id, token: ctx.token, codigo: e.solicitud?.codigo ?? 'solicitud', revision: e.revision,
  peticion: { homologacion: e.homologacion, tipo_cambio: e.tipo_cambio ?? null, plantilla_b64: buffer.toString('base64') } } }];"""

EVALUAR_CUADRO = """// El servicio devuelve el xlsx y su validación; un cuadro imposible de armar no se reintenta.
const ctx = $('Armar petición').first().json;
const base = { cuadro_id: ctx.cuadro_id, token: ctx.token };
if (!$json.ok || !$json.archivo_b64) {
  return [{ json: { ...base, ok: false, recuperable: $json.recuperable !== false,
    error: String($json.error ?? $json.detail ?? 'El servicio de E5 no devolvió el cuadro.').slice(0, 600) } }];
}
const nombre = `cuadro-${ctx.codigo}-rev${ctx.revision}.xlsx`;
const binario = await this.helpers.prepareBinaryData(Buffer.from($json.archivo_b64, 'base64'), nombre,
  '%s');
return [{ json: { ...base, ok: true, estado: $json.estado, validacion: $json.validacion, nombre_archivo: nombre,
  metadata: JSON.stringify({ name: nombre, metadata: { tipo: 'cuadro_comparativo', cuadro_id: ctx.cuadro_id } }) }, binary: { data: binario } }];""" % XLSX

EVALUAR_SUBIDA = """// Storage responde con el archivo creado; sin identificador, el intento falla y se reintenta.
const ctx = $('Evaluar cuadro').first().json;
const base = { cuadro_id: ctx.cuadro_id, token: ctx.token };
const id = $json.processedFiles?.[0]?.id;
if (!id) return [{ json: { ...base, ok: false, recuperable: true, error: 'Storage no guardó el cuadro: ' + JSON.stringify($json).slice(0, 300) } }];
return [{ json: { ...base, ok: true, estado: ctx.estado, validacion: ctx.validacion, nombre_archivo: ctx.nombre_archivo, storage_file_id: id } }];"""


def generate():
    flujo = e4.Flow(1, "Cuadro comparativo")
    flujo.value["id"] = IDS["1"]
    flujo.value["name"] = "CostFlow - E5.1 Cuadro comparativo"
    flujo.number = "1"
    # Las funciones de E4 apuntan a e4-operar; E5 comparte esa Function (operaciones *_e5).
    cola = flujo.node("Revisar la cola cada minuto", "scheduleTrigger", {"rule": {"interval": [{"field": "minutes", "minutesInterval": 1}]}}, 1.2)
    tomar = flujo.funcion("Tomar cuadro pendiente", "tomar_e5", "{}")
    hay = flujo.node("¿Hay algún cuadro por generar?", "if", {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
        "conditions": [{"id": str(uuid.uuid5(uuid.NAMESPACE_URL, "costflowE5_1:hay")), "leftValue": "={{ $json.respuesta.resultado }}", "rightValue": "tomada",
                        "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"}, "options": {}}, 2)
    entrada = flujo.funcion("Consultar entrada en Nhost", "entrada_e5", "{cuadro_id:$json.respuesta.cuadro_id,token:$json.respuesta.token}")
    comprobar = flujo.code("Comprobar entrada", COMPROBAR_ENTRADA)
    con_plantilla = flujo.si("¿Hay plantilla?", "={{ $json.ok }}")
    descargar = flujo.node("Descargar plantilla", "httpRequest", {"method": "GET", "url": "={{ '" + STORAGE + "/' + $json.storage_file_id }}",
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "options": {"timeout": 120000, "response": {"response": {"responseFormat": "file", "outputPropertyName": "data"}}}}, 4.2, "storage")
    armar = flujo.code("Armar petición", ARMAR_PETICION)
    e4.SERVICIO = SERVICIO  # Flow.servicio lee esta constante al construir el nodo
    generar = flujo.servicio("Generar cuadro", "/e5/generar", "$json.peticion", 120000)
    evaluar = flujo.code("Evaluar cuadro", EVALUAR_CUADRO)
    cuadro_ok = flujo.si("¿Cuadro armado?", "={{ $json.ok }}")
    subir = flujo.node("Guardar cuadro en Storage", "httpRequest", {"method": "POST", "url": STORAGE, "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth", "sendBody": True, "contentType": "multipart-form-data", "bodyParameters": {"parameters": [
            {"name": "bucket-id", "value": "cotizaciones"}, {"name": "metadata[]", "value": "={{ $json.metadata }}"},
            {"parameterType": "formBinaryData", "name": "file[]", "inputDataFieldName": "data"}]},
        "options": {"timeout": 180000, "response": {"response": {"neverError": True, "responseFormat": "json"}}}}, 4.2, "storage")
    evaluar_subida = flujo.code("Evaluar subida", EVALUAR_SUBIDA)
    subida_ok = flujo.si("¿Se guardó el archivo?", "={{ $json.ok }}")
    guardar = flujo.funcion("Guardar cuadro", "guardar_e5",
        "{cuadro_id:$json.cuadro_id,token:$json.token,estado:$json.estado,nombre_archivo:$json.nombre_archivo,"
        "storage_file_id:$json.storage_file_id,validacion:$json.validacion}")
    fallo = flujo.funcion("Registrar fallo", "fallo_e5", "{cuadro_id:$json.cuadro_id,token:$json.token,error:$json.error,recuperable:$json.recuperable}")
    flujo.link(cola, tomar); flujo.link(tomar, hay); flujo.link(hay, entrada, 0); flujo.link(entrada, comprobar); flujo.link(comprobar, con_plantilla)
    flujo.link(con_plantilla, descargar, 0); flujo.link(con_plantilla, fallo, 1); flujo.link(descargar, armar); flujo.link(armar, generar)
    flujo.link(generar, evaluar); flujo.link(evaluar, cuadro_ok); flujo.link(cuadro_ok, subir, 0); flujo.link(cuadro_ok, fallo, 1)
    flujo.link(subir, evaluar_subida); flujo.link(evaluar_subida, subida_ok); flujo.link(subida_ok, guardar, 0); flujo.link(subida_ok, fallo, 1)
    return [flujo.value]


if __name__ == "__main__":
    raiz = Path(__file__).parent
    for flujo in generate():
        (raiz / f"e5-{flujo['id'][-1]}.json").write_text(json.dumps(flujo, ensure_ascii=False, indent=2), encoding="utf-8")
