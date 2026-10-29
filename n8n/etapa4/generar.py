"""Genera el flujo de E4 para n8n; nunca incluye valores de credenciales."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

IDS = {"1": "costflowE4_1"}
FUNCION = "https://SUBDOMINIO.functions.REGION.nhost.run/v1/e4-operar"
SERVICIO = "http://costflow-homologacion:8094"
CLAUDE = "https://api.anthropic.com/v1/messages"

# Cada paso conserva el contexto (ejecucion, token y paquete) para poder registrar el fallo desde cualquier punto.
COMPROBAR_ENTRADA = """// Sigue solo si Nhost entregó la entrada de esta homologación; si el intento venció, termina sin hacer nada.
const tomada = $('Tomar homologación pendiente').first().json.respuesta;
const entrada = $json.respuesta;
if (entrada?.resultado !== 'entrada') return [];
return [{ json: { ejecucion_id: tomada.ejecucion_id, token: tomada.token, paquete: entrada.paquete } }];"""

VERIFICAR_PETICION = """// El servicio de homologación debe devolver la petición lista para Claude.
const ctx = $('Comprobar entrada').first().json;
const base = { ejecucion_id: ctx.ejecucion_id, token: ctx.token, paquete: ctx.paquete };
if (!$json.cuerpo_claude) {
  return [{ json: { ...base, ok: false, error: 'El servicio de homologación no preparó la petición: ' + String($json.detail ?? $json.error ?? 'sin detalle').slice(0, 300) } }];
}
return [{ json: { ...base, ok: true, cuerpo_claude: $json.cuerpo_claude, modelo: $json.modelo } }];"""

INTERPRETAR_CLAUDE = """// Convierte la respuesta de la API de Claude en texto utilizable o en un fallo con su motivo.
const ctx = $('Verificar petición').first().json;
const base = { ejecucion_id: ctx.ejecucion_id, token: ctx.token, paquete: ctx.paquete };
const r = $json;
const fallo = (mensaje) => [{ json: { ...base, ok: false, error: mensaje } }];
if (r.type === 'error' || r.error) return fallo('Claude rechazó la petición: ' + (r.error?.message ?? 'error sin detalle'));
if (r.stop_reason === 'refusal') return fallo('Claude rechazó la petición por seguridad.');
if (r.stop_reason !== 'end_turn') return fallo('Claude no terminó la respuesta (' + (r.stop_reason ?? 'sin motivo') + '; salida: ' + (r.usage?.output_tokens ?? '?') + ' tokens).');
const texto = (r.content ?? []).filter((b) => b.type === 'text').map((b) => b.text).join('');
return [{ json: { ...base, ok: true, texto, modelo: r.model ?? ctx.modelo,
  tokens_entrada: r.usage?.input_tokens ?? null, tokens_salida: r.usage?.output_tokens ?? null } }];"""

EVALUAR_RESULTADO = """// El servicio valida la respuesta contra la entrada; si no cuadra, es un fallo reintentable.
const ctx = $('Interpretar respuesta de Claude').first().json;
const base = { ejecucion_id: ctx.ejecucion_id, token: ctx.token, paquete: ctx.paquete };
if ($json.resultado !== 'construida') {
  const errores = Array.isArray($json.errores) ? $json.errores.join('; ') : String($json.detail ?? $json.error ?? 'sin detalle');
  return [{ json: { ...base, ok: false, error: 'La respuesta de Claude no pasó la validación: ' + errores.slice(0, 600) } }];
}
return [{ json: { ...base, ok: true, estado_revision: $json.estado_revision, resultado: $json.homologacion,
  version_ids: $json.version_ids, huella: $json.huella, modelo: ctx.modelo, tokens_entrada: ctx.tokens_entrada, tokens_salida: ctx.tokens_salida } }];"""


class Flow:
    def __init__(self, number, title):
        self.number = str(number)
        self.value = {"id": IDS[self.number], "name": f"CostFlow - E4.{number} {title}", "active": False,
                      "nodes": [], "connections": {}, "settings": {"executionOrder": "v1", "executionTimeout": 900,
                      "saveDataErrorExecution": "none", "saveDataSuccessExecution": "none", "saveManualExecutions": False}}

    def node(self, name, kind, parameters, version=1, cred=None, position=None):
        node = {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, self.value["id"] + ":" + name)), "name": name,
                "type": "n8n-nodes-base." + kind, "typeVersion": version, "parameters": parameters,
                "position": position or [len(self.value["nodes"]) * 220, 0]}
        if cred:
            node["notes"] = "CREDENCIAL_E4:" + cred
        self.value["nodes"].append(node)
        return name

    def link(self, source, target, output=0):
        salidas = self.value["connections"].setdefault(source, {"main": []})["main"]
        while len(salidas) <= output:
            salidas.append([])
        salidas[output].append({"node": target, "type": "main", "index": 0})

    def code(self, name, codigo):
        return self.node(name, "code", {"jsCode": codigo}, 2)

    def si(self, name, expresion):
        return self.node(name, "if", {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
            "conditions": [{"id": str(uuid.uuid5(uuid.NAMESPACE_URL, self.value["id"] + ":si:" + name)), "leftValue": expresion, "rightValue": True,
                            "operator": {"type": "boolean", "operation": "equals"}}], "combinator": "and"}, "options": {}}, 2)

    def funcion(self, name, operacion, datos):
        # El primer }} termina la expresión de n8n: se separan los cierres del objeto.
        return self.node(name, "httpRequest", {"method": "POST", "url": FUNCION, "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth", "sendBody": True, "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({operacion:'" + operacion + "',datos:" + datos + " }) }}",
            "options": {"timeout": 120000, "response": {"response": {"responseFormat": "json"}}}}, 4.2, "internal")

    def servicio(self, name, ruta, cuerpo, timeout=60000):
        return self.node(name, "httpRequest", {"method": "POST", "url": SERVICIO + ruta, "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth", "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify(" + cuerpo + ") }}",
            "options": {"timeout": timeout, "response": {"response": {"neverError": True, "responseFormat": "json"}}}}, 4.2, "internal")


def generate():
    flujo = Flow(1, "Homologación de cotizaciones finales")
    cola = flujo.node("Revisar la cola cada minuto", "scheduleTrigger", {"rule": {"interval": [{"field": "minutes", "minutesInterval": 1}]}}, 1.2)
    tomar = flujo.funcion("Tomar homologación pendiente", "tomar_e4", "{}")
    hay = flujo.node("¿Hay algo que homologar?", "if", {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
        "conditions": [{"id": str(uuid.uuid5(uuid.NAMESPACE_URL, "costflowE4_1:hay")), "leftValue": "={{ $json.respuesta.resultado }}", "rightValue": "tomada",
                        "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"}, "options": {}}, 2)
    entrada = flujo.funcion("Consultar entrada en Nhost", "entrada_e4",
                            "{ejecucion_id:$json.respuesta.ejecucion_id,token:$json.respuesta.token}")
    comprobar = flujo.code("Comprobar entrada", COMPROBAR_ENTRADA)
    preparar = flujo.servicio("Preparar petición para Claude", "/e4/preparar", "{paquete:$json.paquete}")
    verificar = flujo.code("Verificar petición", VERIFICAR_PETICION)
    peticion_ok = flujo.si("¿Petición lista?", "={{ $json.ok }}")
    claude = flujo.node("Claude Messages", "httpRequest", {"method": "POST", "url": CLAUDE, "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth", "sendHeaders": True, "headerParameters": {"parameters": [{"name": "anthropic-version", "value": "2023-06-01"}]},
        "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify($json.cuerpo_claude) }}",
        "options": {"timeout": 280000, "response": {"response": {"neverError": True, "responseFormat": "json"}}}}, 4.2, "claude")
    interpretar = flujo.code("Interpretar respuesta de Claude", INTERPRETAR_CLAUDE)
    respuesta_ok = flujo.si("¿Claude respondió bien?", "={{ $json.ok }}")
    construir = flujo.servicio("Construir y validar", "/e4/construir", "{paquete:$json.paquete,texto:$json.texto,modelo:$json.modelo}", 120000)
    evaluar = flujo.code("Evaluar resultado", EVALUAR_RESULTADO)
    resultado_ok = flujo.si("¿Pasó la validación?", "={{ $json.ok }}")
    guardar = flujo.funcion("Guardar homologación", "guardar_e4",
        "{ejecucion_id:$json.ejecucion_id,token:$json.token,estado_revision:$json.estado_revision,resultado:$json.resultado,"
        "version_ids:$json.version_ids,huella:$json.huella,modelo:$json.modelo,tokens_entrada:$json.tokens_entrada,tokens_salida:$json.tokens_salida}")
    fallo = flujo.funcion("Registrar fallo", "fallo_e4",
                          "{ejecucion_id:$json.ejecucion_id,token:$json.token,error:$json.error,recuperable:true}")
    flujo.link(cola, tomar); flujo.link(tomar, hay); flujo.link(hay, entrada, 0); flujo.link(entrada, comprobar); flujo.link(comprobar, preparar)
    flujo.link(preparar, verificar); flujo.link(verificar, peticion_ok); flujo.link(peticion_ok, claude, 0); flujo.link(peticion_ok, fallo, 1)
    flujo.link(claude, interpretar); flujo.link(interpretar, respuesta_ok); flujo.link(respuesta_ok, construir, 0); flujo.link(respuesta_ok, fallo, 1)
    flujo.link(construir, evaluar); flujo.link(evaluar, resultado_ok); flujo.link(resultado_ok, guardar, 0); flujo.link(resultado_ok, fallo, 1)
    return [flujo.value]


if __name__ == "__main__":
    raiz = Path(__file__).parent
    for flujo in generate():
        (raiz / f"e4-{flujo['id'][-1]}.json").write_text(json.dumps(flujo, ensure_ascii=False, indent=2), encoding="utf-8")
