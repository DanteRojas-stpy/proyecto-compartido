"""Genera los cinco flujos de E3 para n8n; nunca incluye valores de credenciales.

Todo ocurre dentro de n8n, sin el servicio `app/etapa3`: los nodos de código usan lector_core.js (equivalente a app/etapa3, comprobado
contra Python) y hablan directo con la Function `e3-operar` de Nhost, con Storage, con Nhost Auth y con Claude.
Los fragmentos de código de cada nodo están en nodos/*.js; este script los une con el núcleo y les inserta el método y el esquema de lectura.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI.parents[1]))  # para leer el método y el esquema desde app/etapa3

from app.etapa3 import contract  # noqa: E402

IDS = {str(i): f"costflowEtapa3_{i}" for i in range(1, 6)}
NHOST = "https://SUBDOMINIO.storage.REGION.nhost.run/v1/files"
NHOST_E3 = "https://SUBDOMINIO.functions.REGION.nhost.run/v1/e3-operar"
NHOST_AUTH = "https://SUBDOMINIO.auth.REGION.nhost.run/v1/user"
CLAUDE = "https://api.anthropic.com/v1/messages"
NUCLEO = (AQUI / "lector_core.js").read_text(encoding="utf-8")


def js(archivo: str, nucleo: bool = False, constantes: dict | None = None, crudos: dict | None = None) -> str:
    """Código de un nodo: (opcionalmente) el núcleo del lector más su fragmento, con las constantes de Python ya insertadas."""
    texto = (AQUI / "nodos" / archivo).read_text(encoding="utf-8")
    for nombre, valor in (constantes or {}).items():
        texto = texto.replace(f"__{nombre}__", json.dumps(valor, ensure_ascii=False))
    for nombre, valor in (crudos or {}).items():
        texto = texto.replace(f"__{nombre}__", valor)
    return NUCLEO + chr(10) + texto if nucleo else texto


LECTURA = {"SISTEMA": contract.SYSTEM, "ESQUEMA": contract.SCHEMA}


class Flow:
    def __init__(self, number, title):
        self.number = str(number)
        self.value = {"id": IDS[self.number], "name": f"CostFlow - E3.{number} {title}", "active": False,
                      "nodes": [], "connections": {}, "settings": {"executionOrder": "v1", "executionTimeout": 900,
                                                                  "saveDataErrorExecution": "none", "saveDataSuccessExecution": "none", "saveManualExecutions": False}}

    def node(self, name, kind, parameters, version=1, cred=None, position=None, on_error=None):
        node = {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, self.value["id"] + ":" + name)), "name": name, "type": "n8n-nodes-base." + kind,
                "typeVersion": version, "parameters": parameters, "position": position or [len(self.value["nodes"]) * 220, 0]}
        if kind == "webhook":
            node["webhookId"] = str(uuid.uuid5(uuid.NAMESPACE_URL, self.value["id"] + parameters["path"]))
        if cred:
            node["notes"] = "CREDENCIAL_E3:" + cred
        if on_error:
            node["onError"] = on_error
        self.value["nodes"].append(node)
        return name

    def link(self, source, target, output=0, entrada=0):
        salidas = self.value["connections"].setdefault(source, {"main": []})["main"]
        while len(salidas) <= output:
            salidas.append([])
        salidas[output].append({"node": target, "type": "main", "index": entrada})

    def code(self, name, codigo):
        return self.node(name, "code", {"jsCode": codigo}, 2)

    def subtrigger(self):
        return self.node("Desde otra etapa", "executeWorkflowTrigger", {"inputSource": "passthrough"}, 1.1)

    def schedule(self, name):
        return self.node(name, "scheduleTrigger", {"rule": {"interval": [{"field": "minutes", "minutesInterval": 1}]}}, 1.2)

    def webhook(self, name, path, protected=True):
        return self.node(name, "webhook", {"httpMethod": "POST", "path": path, "authentication": "headerAuth" if protected else "none",
                                           "responseMode": "responseNode", "options": {}}, 2, "internal" if protected else None)

    def nhost(self, name, operation, data="{}", seguir=False):
        # El primer }} termina la expresión de n8n: se deja un espacio antes de cada cierre de objeto anidado.
        return self.node(name, "httpRequest", {"method": "POST", "url": NHOST_E3, "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
                         "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify({operacion:'" + operation + "',datos:" + data + " }) }}",
                         "options": {"timeout": 120000, "response": {"response": {"neverError": True, "responseFormat": "json"}}}}, 4.2, "internal",
                         on_error="continueRegularOutput" if seguir else None)

    def storage(self, name, metodo, url_expresion, respuesta, cred="storage", cuerpo=None, timeout=120000):
        parametros = {"method": metodo, "url": url_expresion, "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
                      "options": {"timeout": timeout, "response": {"response": respuesta}}}
        if cuerpo:
            parametros.update(cuerpo)
        return self.node(name, "httpRequest", parametros, 4.2, cred)

    def respond(self, name="Responder"):
        return self.node(name, "respondToWebhook", {"respondWith": "json", "responseBody": "={{ JSON.stringify($json) }}",
                                                    "options": {"responseCode": "={{ $json.http_code || 200 }}"}}, 1.4)

    def execute(self, number, name):
        return self.node(name, "executeWorkflow", {"workflowId": {"__rl": True, "value": IDS[str(number)], "mode": "id"},
                         "workflowInputs": {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": [],
                                            "attemptToConvertTypes": False, "convertFieldsToString": True},
                         "options": {"waitForSubWorkflow": False}}, 1.3)

    def switch(self, name, field, values):
        return self.node(name, "switch", {"rules": {"values": [{"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                         "conditions": [{"leftValue": "={{ $json." + field + " }}", "rightValue": x, "operator": {"type": "string", "operation": "equals"}}],
                         "combinator": "and"}, "renameOutput": True, "outputKey": x} for x in values]}, "options": {"fallbackOutput": "extra"}}, 3.2)

    def si(self, name, expresion):
        return self.node(name, "if", {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
                         "conditions": [{"id": str(uuid.uuid5(uuid.NAMESPACE_URL, self.value["id"] + ":si:" + name)), "leftValue": expresion, "rightValue": True,
                                         "operator": {"type": "boolean", "operation": "equals"}}], "combinator": "and"}, "options": {}}, 2)

    def unir(self, name, modo="append"):
        parametros = {"mode": "append"} if modo == "append" else {"mode": "combine", "combineBy": "combineByPosition", "options": {}}
        return self.node(name, "merge", parametros, 3.2)


SIN_FALLO = "={{ $json.fallo === undefined }}"
FALLO = ("{version_id:$json.version_id,token:$json.token,fase:'FASE',recuperable:$json.fallo.recuperable,"
         "error:{tipo:$json.fallo.tipo,mensaje:$json.fallo.mensaje} }")


def acciones(flujo, ruta, reintento=False):
    """Decisión autenticada del especialista: se verifica su sesión en Nhost Auth y se registra con su identidad verificada."""
    entrada = flujo.webhook("Reintento desde el frontend" if reintento else "Decisión desde el frontend", ruta, False)
    preparar = flujo.code("Preparar decisión", js("accion_preparar.js", crudos={"CUERPO": "{ ...r.body, accion: 'reintentar' }" if reintento else "r.body"}))
    preparada = flujo.si("¿Decisión preparada?", "={{ $json.ok }}")
    sesion = flujo.storage("Verificar sesión en Nhost", "GET", NHOST_AUTH, {"fullResponse": True, "neverError": True, "responseFormat": "json"}, cred=None,
                           cuerpo={"authentication": "none", "sendHeaders": True,
                                   "headerParameters": {"parameters": [{"name": "Authorization", "value": '={{ $("Preparar decisión").first().json.authorization }}'}]}}, timeout=30000)
    flujo.value["nodes"][-1]["parameters"].pop("genericAuthType", None)
    evaluar = flujo.code("Evaluar sesión", js("accion_sesion.js"))
    autorizada = flujo.si("¿Sesión válida?", "={{ $json.ok }}")
    es_documento = flujo.si("¿Pide un documento?", "={{ $json.accion === 'ver_documento' }}")
    decision = flujo.nhost("Registrar decisión", "decision", "{usuario_id_verificado:$json.usuario_id,accion:$json.datos }", seguir=True)
    resultado = flujo.code("Resultado de la decisión", js("accion_decision.js"))
    permiso = flujo.nhost("Consultar acceso al documento", "documento_accesible", "{usuario_id_verificado:$json.usuario_id,documento_id:$json.datos.documento_id }", seguir=True)
    permitido = flujo.code("Documento permitido", js("accion_documento_permiso.js"))
    hay_permiso = flujo.si("¿Puede verlo?", "={{ $json.ok }}")
    descarga = flujo.storage("Recuperar documento", "GET", "={{ '" + NHOST + "/' + $json.storage_file_id }}", {"responseFormat": "file", "outputPropertyName": "data"})
    entregar = flujo.code("Entregar documento", js("accion_documento_entregar.js"))
    origen = "$('" + ("Reintento desde el frontend" if reintento else "Decisión desde el frontend") + "').first().json.headers.origin"
    respuesta = flujo.node("Responder decisión", "respondToWebhook", {"respondWith": "json", "responseBody": "={{ JSON.stringify($json) }}", "options": {
        "responseCode": "={{ $json.http_code || 503 }}", "responseHeaders": {"entries": [
            {"name": "Access-Control-Allow-Origin", "value": "={{ ['http://127.0.0.1:8001','http://localhost:8001'].includes(" + origen + ") ? " + origen + " : 'http://127.0.0.1:8001' }}"},
            {"name": "Vary", "value": "Origin"}, {"name": "Cache-Control", "value": "no-store"}]}}}, 1.4)
    flujo.link(entrada, preparar); flujo.link(preparar, preparada); flujo.link(preparada, sesion, 0); flujo.link(preparada, respuesta, 1)
    flujo.link(sesion, evaluar); flujo.link(evaluar, autorizada); flujo.link(autorizada, es_documento, 0); flujo.link(autorizada, respuesta, 1)
    flujo.link(es_documento, permiso, 0); flujo.link(es_documento, decision, 1)
    flujo.link(decision, resultado); flujo.link(resultado, respuesta)
    flujo.link(permiso, permitido); flujo.link(permitido, hay_permiso); flujo.link(hay_permiso, descarga, 0); flujo.link(hay_permiso, respuesta, 1)
    flujo.link(descarga, entregar); flujo.link(entregar, respuesta)


def generate():
    # ---- E3.1 Recepción -------------------------------------------------------------------------------------------------
    primero = Flow(1, "Recepción de correos confirmados")
    programa = primero.schedule("Consumir eventos de Nhost")
    eventos = primero.nhost("Tomar eventos pendientes", "eventos")
    uno = primero.code("Un correo por evento", "return ($json.respuesta.eventos??[]).map(json=>({json}));")
    disparo = primero.subtrigger()
    reservar = primero.nhost("Reservar versión por correo", "preparar_correo", "$json")
    recepcion = primero.code("Resultado de recepción", "return $input.all().map((i,index)=>({json:i.json.respuesta,pairedItem:{item:index}}));")
    nueva = primero.switch("¿Versión nueva?", "resultado", ["version_creada"])
    gmail = primero.node("Recuperar exactamente este correo", "gmail", {"resource": "message", "operation": "get", "messageId": "={{ $json.gmail_message_id }}", "simple": False,
                                                                         "options": {"downloadAttachments": True, "attachmentPrefix": "adjunto_"}}, 2.1, "gmail", on_error="continueRegularOutput")
    preparar = primero.code("Preparar documentos", js("recepcion_preparar.js", nucleo=True))
    hay_docs = primero.si("¿Hay documentos?", SIN_FALLO)
    cabecera = primero.storage("Comprobar archivo en Storage", "HEAD", "={{ '" + NHOST + "/' + $json.meta.storage_file_id + '?e3_revision=' + Date.now() + '-' + Math.random().toString(36).slice(2) }}",
                               {"fullResponse": True, "neverError": True, "responseFormat": "text"}, cuerpo={"sendHeaders": True, "headerParameters": {"parameters": [
                                   {"name": "Cache-Control", "value": "no-cache"}, {"name": "Pragma", "value": "no-cache"}]}}, timeout=30000)
    existencia = primero.code("Marcar existencia", js("recepcion_existencia.js"))
    junta = primero.unir("Merge de existencia", "posicion")
    que_hacer = primero.switch("¿Qué hacer con el archivo?", "accion", ["existe", "subir", "no_decidible"])
    existe = primero.code("Archivo ya guardado", "return $input.all().map((i,k)=>({json:{...i.json,confirmado:true,motivo:null},pairedItem:{item:k}}));")
    subir = primero.storage("Guardar original en Storage", "POST", NHOST, {"neverError": True, "responseFormat": "json"}, cuerpo={
        "sendBody": True, "contentType": "multipart-form-data", "bodyParameters": {"parameters": [
            {"name": "bucket-id", "value": "cotizaciones"},
            {"name": "metadata[]", "value": "={{ JSON.stringify({id:$json.meta.storage_file_id,name:$json.meta.nombre_original,metadata:{tipo:'documento_e3',sha256:$json.meta.sha256} }) }}"},
            {"parameterType": "formBinaryData", "name": "file[]", "inputDataFieldName": "data"}]}}, timeout=180000)
    confirmar = primero.code("Confirmar subida", js("recepcion_subida.js"))
    sin_decidir = primero.code("Storage no permitió comprobar", "return $input.all().map((i,k)=>({json:{...i.json,confirmado:false,motivo:'Storage no permitió comprobar el archivo.'},pairedItem:{item:k}}));")
    unir_a = primero.unir("Unir existentes y subidos")
    unir_b = primero.unir("Unir con no decidibles")
    reunir = primero.code("Reunir documentos", js("recepcion_reunir.js"))
    confirmados = primero.si("¿Documentos confirmados?", SIN_FALLO)
    registrar = primero.nhost("Registrar documentos", "registrar_documentos", "{version_id:$json.version_id,token:$json.token,documentos:$json.documentos }", seguir=True)
    normal = primero.code("Resultado del registro (normal)", """const r = $input.first().json;
const c = $('Reunir documentos').first().json;
if (r.respuesta && typeof r.respuesta === 'object') return [{ json: r.respuesta }];
return [{ json: { version_id: c.version_id, token: c.token, fallo: { tipo: 'RuntimeError', mensaje: 'Nhost no registró los documentos: ' + JSON.stringify(r).slice(0, 300), recuperable: true } } }];""")
    sin_error = primero.si("¿Registro sin error?", SIN_FALLO)
    fallo = primero.nhost("Registrar fallo de recepción", "fallo", FALLO.replace("FASE", "recepcion"), seguir=True)
    fallo_norm = primero.code("Resultado del fallo (recepción)", "const r=$input.first().json;return [{json:(r.respuesta&&typeof r.respuesta==='object')?r.respuesta:{resultado:'error_procesamiento'}}];")
    salida = primero.switch("Resultado del registro", "resultado", ["documentos_registrados", "error_procesamiento"])
    leer = primero.execute(2, "Invocar E3.2")
    avisar = primero.execute(3, "Notificar error definitivo")
    primero.link(programa, eventos); primero.link(eventos, uno); primero.link(uno, reservar); primero.link(disparo, reservar); primero.link(reservar, recepcion)
    primero.link(recepcion, nueva); primero.link(nueva, gmail); primero.link(gmail, preparar); primero.link(preparar, hay_docs)
    primero.link(hay_docs, cabecera, 0); primero.link(hay_docs, junta, 0, 0); primero.link(hay_docs, fallo, 1)
    primero.link(cabecera, existencia); primero.link(existencia, junta, 0, 1); primero.link(junta, que_hacer)
    primero.link(que_hacer, existe, 0); primero.link(que_hacer, subir, 1); primero.link(que_hacer, sin_decidir, 2)
    primero.link(subir, confirmar); primero.link(existe, unir_a, 0, 0); primero.link(confirmar, unir_a, 0, 1)
    primero.link(unir_a, unir_b, 0, 0); primero.link(sin_decidir, unir_b, 0, 1); primero.link(unir_b, reunir)
    primero.link(reunir, confirmados); primero.link(confirmados, registrar, 0); primero.link(confirmados, fallo, 1)
    primero.link(registrar, normal); primero.link(normal, sin_error); primero.link(sin_error, salida, 0); primero.link(sin_error, fallo, 1)
    primero.link(fallo, fallo_norm); primero.link(fallo_norm, salida)
    primero.link(salida, leer, 0); primero.link(salida, avisar, 1)

    # ---- E3.2 Lectura -----------------------------------------------------------------------------------------------------
    segundo = Flow(2, "Lectura y validación")
    disparo = segundo.subtrigger()
    iniciar = segundo.nhost("Iniciar lectura", "iniciar_lectura", "{version_id:$json.version_id }")
    iniciada = segundo.si("¿Lectura iniciada?", "={{ $json.respuesta?.resultado === 'iniciada' }}")
    version = segundo.nhost("Obtener versión", "version", "{version_id:$json.respuesta.version_id }")
    config = segundo.nhost("Obtener configuración", "configuracion")
    documentos = segundo.code("Documentos por leer", js("lectura_documentos.js"))
    hay = segundo.si("¿Hay documentos por leer?", SIN_FALLO)
    lease = segundo.nhost("Renovar lease", "renovar_lease", "{version_id:$json.version_id,token:$json.token }", seguir=True)
    descargar = segundo.storage("Descargar documento", "GET", "={{ '" + NHOST + "/' + $('Documentos por leer').item.json.documento.storage_file_id + '?e3_revision=' + Date.now() + '-' + Math.random().toString(36).slice(2) }}",
                                {"responseFormat": "file", "outputPropertyName": "data"}, cuerpo={"sendHeaders": True, "headerParameters": {"parameters": [
                                    {"name": "Cache-Control", "value": "no-cache"}, {"name": "Pragma", "value": "no-cache"}]}})
    detectar = segundo.code("Detectar tipo", js("lectura_detectar.js", nucleo=True))
    clase = segundo.switch("Clase de documento", "tipo", ["pdf", "xlsx", "csv", "error"])
    extraer = segundo.node("Extraer texto del PDF", "extractFromFile", {"operation": "pdf", "binaryPropertyName": "data", "options": {"joinPages": False}}, 1.1, on_error="continueRegularOutput")
    leer_pdf = segundo.code("Leer PDF", js("lectura_pdf.js", nucleo=True))
    marcar = segundo.code("Marcar xlsx como zip", js("lectura_xlsx_marcar.js"))
    abrir = segundo.node("Descomprimir xlsx", "compression", {"operation": "decompress", "binaryPropertyName": "data", "outputPrefix": "p_"}, 1.1)
    leer_xlsx = segundo.code("Leer Excel", js("lectura_xlsx.js", nucleo=True))
    leer_csv = segundo.code("Leer CSV", js("lectura_csv.js", nucleo=True))
    no_leido = segundo.code("Documento no leído", js("lectura_error.js"))
    unir1 = segundo.unir("Unir PDF y Excel")
    unir2 = segundo.unir("Unir con CSV")
    unir3 = segundo.unir("Unir con no leídos")
    reunir = segundo.code("Reunir fuentes", js("lectura_reunir.js"))
    listas = segundo.si("¿Fuentes listas?", SIN_FALLO)
    guardado = segundo.code("Preparar guardado de fuentes", js("lectura_guardado.js"))
    guardar = segundo.nhost("Guardar fuentes", "guardar_fuentes", "$json", seguir=True)
    tandas = segundo.code("Armar tandas", js("lectura_tandas.js", nucleo=True, constantes=LECTURA))
    hay_tandas = segundo.si("¿Hay tandas?", SIN_FALLO)
    lease2 = segundo.nhost("Renovar lease (tanda)", "renovar_lease", "{version_id:$json.version_id,token:$json.token }", seguir=True)
    claude = segundo.node("Claude Messages", "httpRequest", {"method": "POST", "url": CLAUDE, "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
                          "sendHeaders": True, "headerParameters": {"parameters": [{"name": "anthropic-version", "value": "2023-06-01"}]}, "sendBody": True, "specifyBody": "json",
                          "jsonBody": "={{ JSON.stringify($('Armar tandas').item.json.cuerpo) }}",
                          "options": {"timeout": 170000, "response": {"response": {"neverError": True, "responseFormat": "json"}}}}, 4.2, "claude", on_error="continueRegularOutput")
    interpretar = segundo.code("Interpretar Claude", js("lectura_interpretar.js", nucleo=True, constantes=LECTURA))
    validar = segundo.code("Validar lectura", js("lectura_resultado.js", nucleo=True, constantes=LECTURA))
    valida = segundo.si("¿Lectura válida?", SIN_FALLO)
    resultado = segundo.nhost("Guardar resultado", "guardar_resultado", "{version_id:$json.version_id,token:$json.token,resultado:$json.resultado }", seguir=True)
    resultado_norm = segundo.code("Resultado guardado", """const r = $input.first().json;
const c = $('Validar lectura').first().json;
if (r.respuesta && typeof r.respuesta === 'object') return [{ json: r.respuesta }];
return [{ json: { version_id: c.version_id, token: c.token, fallo: { tipo: 'RuntimeError', mensaje: 'Nhost no guardó el resultado: ' + JSON.stringify(r).slice(0, 300), recuperable: true } } }];""")
    guardado_ok = segundo.si("¿Resultado sin error?", SIN_FALLO)
    fallo = segundo.nhost("Registrar fallo de lectura", "fallo", FALLO.replace("FASE", "lectura"), seguir=True)
    fallo_norm = segundo.code("Resultado del fallo (lectura)", "const r=$input.first().json;return [{json:(r.respuesta&&typeof r.respuesta==='object')?r.respuesta:{resultado:'error_procesamiento'}}];")
    salida = segundo.switch("Resultado de la lectura", "resultado", ["procesamiento_completado", "error_procesamiento"])
    avisar = segundo.execute(3, "Invocar E3.3")
    segundo.link(disparo, iniciar); segundo.link(iniciar, iniciada); segundo.link(iniciada, version, 0); segundo.link(version, config); segundo.link(config, documentos)
    segundo.link(documentos, hay); segundo.link(hay, lease, 0); segundo.link(hay, fallo, 1); segundo.link(lease, descargar); segundo.link(descargar, detectar); segundo.link(detectar, clase)
    segundo.link(clase, extraer, 0); segundo.link(clase, marcar, 1); segundo.link(clase, leer_csv, 2); segundo.link(clase, no_leido, 3)
    segundo.link(extraer, leer_pdf); segundo.link(marcar, abrir); segundo.link(abrir, leer_xlsx)
    segundo.link(leer_pdf, unir1, 0, 0); segundo.link(leer_xlsx, unir1, 0, 1); segundo.link(unir1, unir2, 0, 0); segundo.link(leer_csv, unir2, 0, 1)
    segundo.link(unir2, unir3, 0, 0); segundo.link(no_leido, unir3, 0, 1); segundo.link(unir3, reunir)
    segundo.link(reunir, listas); segundo.link(listas, guardado, 0); segundo.link(listas, fallo, 1); segundo.link(guardado, guardar); segundo.link(guardar, tandas)
    segundo.link(tandas, hay_tandas); segundo.link(hay_tandas, lease2, 0); segundo.link(hay_tandas, fallo, 1); segundo.link(lease2, claude); segundo.link(claude, interpretar)
    segundo.link(interpretar, validar); segundo.link(validar, valida); segundo.link(valida, resultado, 0); segundo.link(valida, fallo, 1)
    segundo.link(resultado, resultado_norm); segundo.link(resultado_norm, guardado_ok); segundo.link(guardado_ok, salida, 0); segundo.link(guardado_ok, fallo, 1)
    segundo.link(fallo, fallo_norm); segundo.link(fallo_norm, salida); segundo.link(salida, avisar, 0); segundo.link(salida, avisar, 1)

    # ---- E3.3 Notificaciones --------------------------------------------------------------------------------------------
    tercero = Flow(3, "Notificaciones solo en frontend")
    disparo = tercero.subtrigger()
    aviso = tercero.nhost("Registrar notificación única en Nhost", "notificar", "{version_id:$json.version_id }")
    tercero.link(disparo, aviso)

    # ---- E3.4 Decisiones --------------------------------------------------------------------------------------------------
    cuarto = Flow(4, "Decisiones autenticadas del especialista")
    acciones(cuarto, "costflow-e3-especialista")

    # ---- E3.5 Recuperación ------------------------------------------------------------------------------------------------
    quinto = Flow(5, "Recuperación y servicios internos")
    programa = quinto.schedule("Revisar errores y ejecuciones estancadas")
    disparo = quinto.subtrigger()
    recuperar = quinto.nhost("Consultar recuperación segura", "recuperar")
    repartir = quinto.code("Distribuir recuperación", "const r=$json.respuesta??{};return [...(r.reintentos??[]).map(x=>({json:{...x,destino:x.fase}})),...(r.definitivos??[]).map(x=>({json:{...x,destino:'notificar'}}))];")
    punto = quinto.switch("Punto seguro", "destino", ["recepcion", "lectura", "notificar"])
    r1 = quinto.execute(1, "Reintentar E3.1")
    r2 = quinto.execute(2, "Reintentar E3.2")
    r3 = quinto.execute(3, "Notificar agotamiento")
    quinto.link(programa, recuperar); quinto.link(disparo, recuperar); quinto.link(recuperar, repartir); quinto.link(repartir, punto)
    quinto.link(punto, r1, 0); quinto.link(punto, r2, 1); quinto.link(punto, r3, 2)
    acciones(quinto, "costflow-e3-reintentar", reintento=True)

    return [f.value for f in [primero, segundo, tercero, cuarto, quinto]]


if __name__ == "__main__":
    for flujo in generate():
        numero = flujo["id"][-1]
        (AQUI / f"e3-{numero}.json").write_text(json.dumps(flujo, ensure_ascii=False, indent=2), encoding="utf-8")
