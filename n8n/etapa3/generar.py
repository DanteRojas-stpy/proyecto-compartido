"""Genera cinco flujos portables; nunca incluye valores de credenciales."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

IDS = {str(i): f"costflowEtapa3_{i}" for i in range(1, 6)}
INTERNAL = "http://costflow-etapa3:8093"
NHOST = "https://SUBDOMINIO.storage.REGION.nhost.run/v1/files"
NHOST_E3 = "https://SUBDOMINIO.functions.REGION.nhost.run/v1/e3-operar"

# Traducción entre el formato interno del lector (el que habla el servicio de E3) y la API de mensajes de Claude.
CLAUDE_REQUEST = r"""// Traduce la petición del lector (formato interno del lector) al formato de la API de mensajes de Claude.
const { modelo, peticion } = $json;
const partes = (x) => (x?.parts ?? []).map((p) => p.text ?? '').join('\n');
const sistema = partes(peticion.systemInstruction);
const contenido = (peticion.contents ?? []).map((c) => partes(c)).join('\n');
const esquema = peticion.generationConfig?.responseJsonSchema ?? {};
if (!contenido.trim()) throw new Error('La petición no trae contenido para leer');
const instruccion = sistema
  + '\n\nResponde únicamente con un objeto JSON válido que cumpla exactamente este esquema JSON. '
  + 'Sin texto adicional, sin comentarios y sin bloques de código:\n' + JSON.stringify(esquema);
const cuerpo = {
  model: modelo,
  max_tokens: 16000,
  system: instruccion,
  messages: [{ role: 'user', content: contenido }],
};
// Extraer datos no necesita razonar a fondo: el esfuerzo bajo deja los tokens para el JSON (modelos 5.x).
if (/^claude-(opus|sonnet|haiku)-5/.test(modelo)) cuerpo.output_config = { effort: 'low' };
return [{ json: { modelo, cuerpo } }];"""

CLAUDE_RESPONSE = r"""// Devuelve la respuesta de Claude con la forma que espera el lector.
const r = $json;
const rechazo = (mensaje) => [{ json: { error: { message: mensaje } } }];
if (r.type === 'error' || r.error) return rechazo('Claude rechazó la petición: ' + (r.error?.message ?? 'error sin detalle'));
if (r.stop_reason === 'refusal') return rechazo('Claude rechazó la petición por seguridad.');
const texto = (r.content ?? []).filter((b) => b.type === 'text').map((b) => b.text).join('').trim();
let limpio = texto.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
const ini = limpio.indexOf('{');
const fin = limpio.lastIndexOf('}');
if (ini >= 0 && fin > ini) limpio = limpio.slice(ini, fin + 1);
const completo = r.stop_reason === 'end_turn' || r.stop_reason === 'stop_sequence';
if (!completo) return rechazo('Claude no devolvió una respuesta completa (' + (r.stop_reason ?? 'sin motivo') + '; salida: ' + (r.usage?.output_tokens ?? '?') + ' tokens).');
return [{ json: {
  candidates: [{ finishReason: 'STOP', content: { parts: [{ text: limpio }] } }],
  usageMetadata: { promptTokenCount: r.usage?.input_tokens, candidatesTokenCount: r.usage?.output_tokens },
  modelVersion: r.model,
} }];"""


class Flow:
    def __init__(self, number, title):
        self.number = str(number)
        self.value = {"id": IDS[self.number], "name": f"CostFlow - E3.{number} {title}", "active": False,
            "nodes": [], "connections": {}, "settings": {"executionOrder": "v1", "executionTimeout": 900,
                "saveDataErrorExecution": "none", "saveDataSuccessExecution": "none", "saveManualExecutions": False}}

    def node(self, name, kind, parameters, version=1, cred=None, position=None):
        node = {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, self.value["id"] + ":" + name)), "name": name,
                "type": "n8n-nodes-base." + kind, "typeVersion": version, "parameters": parameters,
                "position": position or [len(self.value["nodes"]) * 220, 0]}
        if kind == "webhook":
            node["webhookId"] = str(uuid.uuid5(uuid.NAMESPACE_URL, self.value["id"] + parameters["path"]))
        if cred:
            node["notes"] = "CREDENCIAL_E3:" + cred
        self.value["nodes"].append(node)
        return name

    def link(self, source, target, output=0):
        connections = self.value["connections"].setdefault(source, {"main": []})["main"]
        while len(connections) <= output:
            connections.append([])
        connections[output].append({"node": target, "type": "main", "index": 0})

    def code(self, name, code):
        return self.node(name, "code", {"jsCode": code}, 2)

    def subtrigger(self):
        return self.node("Desde otra etapa", "executeWorkflowTrigger", {"inputSource": "passthrough"}, 1.1)

    def schedule(self, name):
        return self.node(name, "scheduleTrigger", {"rule": {"interval": [{"field": "minutes", "minutesInterval": 1}]}}, 1.2)

    def webhook(self, name, path, protected=True):
        return self.node(name, "webhook", {"httpMethod": "POST", "path": path,
            "authentication": "headerAuth" if protected else "none", "responseMode": "responseNode", "options": {}},
            2, "internal" if protected else None)

    def worker(self, name, path, body="={{ $json }}", action=False):
        parameters = {"method": "POST", "url": INTERNAL + path, "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth", "sendBody": True, "specifyBody": "json", "jsonBody": body,
            "options": {"timeout": 720000}}
        if action:
            parameters.update({"sendHeaders": True, "headerParameters": {"parameters": [{"name": "Authorization", "value": '={{ $("Preparar decisión").first().json.authorization }}'}]}})
        return self.node(name, "httpRequest", parameters, 4.2, "internal")

    def nhost(self, name, operation, data="{}"):
        # El primer }} termina la expresión de n8n: separar el cierre del objeto.
        return self.node(name, "httpRequest", {"method": "POST", "url": NHOST_E3,
            "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
            "sendBody": True, "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({operacion:'" + operation + "',datos:" + data + " }) }}",
            "options": {"timeout": 120000, "response": {"response": {"responseFormat": "json"}}}},
            4.2, "internal")

    def nhost_dynamic(self, name):
        return self.node(name, "httpRequest", {"method": "POST", "url": NHOST_E3,
            "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
            "sendBody": True, "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({operacion:$json.body.operacion,datos:$json.body.datos||{} }) }}",
            "options": {"timeout": 120000, "response": {"response": {"responseFormat": "json"}}}},
            4.2, "internal")

    def respond(self, name="Responder"):
        return self.node(name, "respondToWebhook", {"respondWith": "json", "responseBody": "={{ JSON.stringify($json) }}",
            "options": {"responseCode": "={{ $json.http_code || 200 }}"}}, 1.4)

    def execute(self, number, name):
        return self.node(name, "executeWorkflow", {"workflowId": {"__rl": True, "value": IDS[str(number)], "mode": "id"},
            "workflowInputs": {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": [],
                               "attemptToConvertTypes": False, "convertFieldsToString": True},
            "options": {"waitForSubWorkflow": False}}, 1.3)

    def switch(self, name, field, values):
        return self.node(name, "switch", {"rules": {"values": [{"conditions": {"options": {
            "caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2}, "conditions": [
            {"leftValue": "={{ $json." + field + " }}", "rightValue": x, "operator": {"type": "string", "operation": "equals"}}],
            "combinator": "and"}, "renameOutput": True, "outputKey": x} for x in values]}, "options": {"fallbackOutput": "extra"}}, 3.2)


def action_nodes(flow, path, retry=False):
    hook = flow.webhook("Decisión desde el frontend" if not retry else "Reintento desde el frontend", path, False)
    prep = flow.code("Preparar decisión", """const r=$json;const origen=String(r.headers?.origin??'');
const origenes=['http://127.0.0.1:8001','http://localhost:8001'];
if(origen&&!origenes.includes(origen))return [{json:{ok:false,http_code:403,mensaje:'Origen de frontend no autorizado.'}}];
if(!/^Bearer\\s+\\S+$/i.test(String(r.headers?.authorization??'')))return [{json:{ok:false,http_code:401,mensaje:'Inicia sesión en Nhost.'}}];
if(!r.body||typeof r.body!=='object'||Array.isArray(r.body))return [{json:{ok:false,http_code:400,mensaje:'Envía una decisión en JSON.'}}];
return [{json:{ok:true,body:BODY,authorization:r.headers.authorization}}];""".replace("BODY", "{...r.body,accion:'reintentar'}" if retry else "r.body"))
    branch = flow.switch("¿Decisión preparada?", "ok", ["true"])
    # Comparación booleana explícita: no depende de coerción de texto.
    branch_node = flow.value["nodes"][-1]
    cond = branch_node["parameters"]["rules"]["values"][0]["conditions"]["conditions"][0]
    cond.update({"rightValue": True, "operator": {"type": "boolean", "operation": "true", "singleValue": True}})
    call = flow.worker("Verificar sesión y registrar decisión", "/action", "={{ $json.body }}", action=True)
    response = flow.node("Responder decisión", "respondToWebhook", {"respondWith": "json",
        "responseBody": "={{ JSON.stringify($json) }}", "options": {"responseCode": "={{ $json.http_code || 503 }}",
            "responseHeaders": {"entries": [{"name": "Access-Control-Allow-Origin", "value": "={{ ['http://127.0.0.1:8001','http://localhost:8001'].includes($('" + ("Reintento desde el frontend" if retry else "Decisión desde el frontend") + "').first().json.headers.origin) ? $('" + ("Reintento desde el frontend" if retry else "Decisión desde el frontend") + "').first().json.headers.origin : 'http://127.0.0.1:8001' }}"},
                {"name": "Vary", "value": "Origin"}, {"name": "Cache-Control", "value": "no-store"}]}}}, 1.4)
    flow.link(hook, prep); flow.link(prep, branch); flow.link(branch, call, 0); flow.link(branch, response, 1); flow.link(call, response)


def generate():
    first = Flow(1, "Recepción de correos confirmados")
    schedule = first.schedule("Consumir eventos de Nhost")
    events = first.nhost("Tomar eventos pendientes", "eventos")
    flatten = first.code("Un correo por evento", "return ($json.respuesta.eventos??[]).map(json=>({json}));")
    trigger = first.subtrigger()
    reserve = first.nhost("Reservar versión por correo", "preparar_correo", "$json")
    unpack = first.code("Resultado de recepción", "return $input.all().map((i,index)=>({json:i.json.respuesta,pairedItem:{item:index}}));")
    branch = first.switch("¿Versión nueva?", "resultado", ["version_creada"])
    gmail = first.node("Recuperar exactamente este correo", "gmail", {"resource": "message", "operation": "get",
        "messageId": "={{ $json.gmail_message_id }}", "simple": False, "options": {"downloadAttachments": True, "attachmentPrefix": "adjunto_"}}, 2.1, "gmail")
    first.value["nodes"][-1]["onError"] = "continueRegularOutput"
    attachments = first.code("Preparar todos los adjuntos", """const result=[];
for(let index=0;index<$input.all().length;index++){
const item=$input.all()[index];const contexto=$('Resultado de recepción').itemMatching(index).json;
const archivos=[];for(const[key,b]of Object.entries(item.binary??{})){const bytes=await this.helpers.getBinaryDataBuffer(index,key);
archivos.push({nombre_original:b.fileName??key,mime_type:b.mimeType??'application/octet-stream',contenido_base64:bytes.toString('base64')});}
result.push({json:{contexto,archivos,error:item.json.error??null},pairedItem:{item:index}});}return result;""")
    receive = first.worker("Guardar archivos y vincular versión", "/receive")
    outcome = first.switch("Resultado del registro", "resultado", ["documentos_registrados", "error_procesamiento"])
    read = first.execute(2, "Invocar E3.2")
    notify_error = first.execute(3, "Notificar error definitivo")
    first.link(schedule, events); first.link(events, flatten); first.link(flatten, reserve); first.link(trigger, reserve)
    first.link(reserve, unpack); first.link(unpack, branch); first.link(branch, gmail); first.link(gmail, attachments)
    first.link(attachments, receive); first.link(receive, outcome); first.link(outcome, read, 0); first.link(outcome, notify_error, 1)

    second = Flow(2, "Lectura OCR RAG y validación")
    trigger = second.subtrigger()
    read = second.worker("Leer y verificar versión completa", "/read")
    branch = second.switch("Resultado de la lectura", "resultado", ["procesamiento_completado", "error_procesamiento"])
    notify = second.execute(3, "Invocar E3.3")
    second.link(trigger, read); second.link(read, branch); second.link(branch, notify, 0); second.link(branch, notify, 1)
    reader_hook = second.webhook("Lector interno", "e3-interno-lector")
    validate = second.code("Preparar petición estructurada", "if(!/^claude-[a-zA-Z0-9.-]+$/.test($json.body.modelo??''))throw new Error('El modelo debe ser de Claude (claude-...)');return [{json:$json.body}];")
    x = len(second.value["nodes"]) * 220
    to_claude = second.code("Convertir a Claude", CLAUDE_REQUEST)
    second.value["nodes"][-1]["position"] = [x, 0]
    claude = second.node("Claude Messages", "httpRequest", {"method": "POST", "url": "https://api.anthropic.com/v1/messages",
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "sendHeaders": True, "headerParameters": {"parameters": [{"name": "anthropic-version", "value": "2023-06-01"}]},
        "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify($json.cuerpo) }}",
        "options": {"timeout": 170000, "response": {"response": {"neverError": True, "responseFormat": "json"}}}},
        4.2, "claude", [x + 220, 0])
    from_claude = second.code("Claude a formato del lector", CLAUDE_RESPONSE)
    second.value["nodes"][-1]["position"] = [x + 440, 0]
    answer = second.respond("Devolver respuesta del lector")
    second.value["nodes"][-1]["position"] = [x + 660, 0]
    second.link(reader_hook, validate); second.link(validate, to_claude)
    second.link(to_claude, claude); second.link(claude, from_claude); second.link(from_claude, answer)

    third = Flow(3, "Notificaciones solo en frontend")
    trigger = third.subtrigger(); notify = third.worker("Registrar notificación única en Nhost", "/notify")
    third.link(trigger, notify)

    fourth = Flow(4, "Decisiones autenticadas del especialista")
    action_nodes(fourth, "costflow-e3-especialista")

    fifth = Flow(5, "Recuperación y servicios internos")
    schedule = fifth.schedule("Revisar errores y ejecuciones estancadas")
    sub = fifth.subtrigger()
    recover = fifth.worker("Consultar recuperación segura", "/recover", "={{ {} }}")
    flatten = fifth.code("Distribuir recuperación", "return [...($json.reintentos??[]).map(x=>({json:{...x,destino:x.fase}})),...($json.definitivos??[]).map(x=>({json:{...x,destino:'notificar'}}))];")
    route = fifth.switch("Punto seguro", "destino", ["recepcion", "lectura", "notificar"])
    receive = fifth.execute(1, "Reintentar E3.1"); read = fifth.execute(2, "Reintentar E3.2"); notify = fifth.execute(3, "Notificar agotamiento")
    fifth.link(schedule, recover); fifth.link(sub, recover); fifth.link(recover, flatten); fifth.link(flatten, route)
    fifth.link(route, receive, 0); fifth.link(route, read, 1); fifth.link(route, notify, 2)
    action_nodes(fifth, "costflow-e3-reintentar", True)
    hook = fifth.webhook("Servicios internos protegidos", "e3-interno-datos")
    router = fifth.switch("Servicio requerido", "body.operacion", ["storage_head", "storage_get", "storage_upload"])
    respond = fifth.respond("Responder servicio interno")
    api = fifth.nhost_dynamic("Operación transaccional Nhost")
    uncached_url = "={{ '" + NHOST + "/'+$json.body.datos.storage_file_id+'?e3_revision='+Date.now()+'-'+Math.random().toString(36).slice(2) }}"
    no_cache = {"sendHeaders": True, "headerParameters": {"parameters": [
        {"name": "Cache-Control", "value": "no-cache"}, {"name": "Pragma", "value": "no-cache"}]}}
    head = fifth.node("Comprobar archivo por huella", "httpRequest", {"method": "HEAD", "url": uncached_url, **no_cache,
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth", "options": {
            "timeout": 30000, "response": {"response": {"fullResponse": True, "neverError": True, "responseFormat": "text"}}}}, 4.2, "storage")
    get = fifth.node("Recuperar original desde Storage", "httpRequest", {"method": "GET", "url": uncached_url, **no_cache,
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth", "options": {
            "timeout": 120000, "response": {"response": {"responseFormat": "file", "outputPropertyName": "data"}}}}, 4.2, "storage")
    binary = fifth.code("Devolver contenido al lector", "const b=await this.helpers.getBinaryDataBuffer(0,'data');return [{json:{contenido_base64:b.toString('base64')}}];")
    prep_upload = fifth.code("Preparar archivo original", "const item=$input.first();const key=Object.keys(item.binary??{})[0];if(!key)throw new Error('No llegó el archivo original');return [{json:{metadata:item.json.body.metadata},binary:{data:item.binary[key]}}];")
    upload = fifth.node("Guardar original en cotizaciones", "httpRequest", {"method": "POST", "url": NHOST,
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth", "sendBody": True,
        "contentType": "multipart-form-data", "bodyParameters": {"parameters": [
            {"name": "bucket-id", "value": "cotizaciones"}, {"name": "metadata[]", "value": "={{ $json.metadata }}"},
            {"parameterType": "formBinaryData", "name": "file[]", "inputDataFieldName": "data"}]}, "options": {"timeout": 180000,
            "response": {"response": {"neverError": True, "responseFormat": "json"}}}}, 4.2, "storage")
    fifth.link(hook, router); fifth.link(router, head, 0); fifth.link(router, get, 1); fifth.link(router, prep_upload, 2); fifth.link(router, api, 3)
    fifth.link(head, respond); fifth.link(get, binary); fifth.link(binary, respond); fifth.link(prep_upload, upload); fifth.link(upload, respond); fifth.link(api, respond)

    return [f.value for f in [first, second, third, fourth, fifth]]


if __name__ == "__main__":
    root = Path(__file__).parent
    for workflow in generate():
        number = workflow["id"][-1]
        (root / f"e3-{number}.json").write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
