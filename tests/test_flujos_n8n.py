import json
import subprocess
from pathlib import Path


FLUJOS = Path(__file__).parents[1] / "n8n" / "flujos"


def cargar_flujos():
    return {ruta.name: json.loads(ruta.read_text(encoding="utf-8")) for ruta in FLUJOS.glob("*.json")}


def ejecutar_javascript(codigo, preambulo, tmp_path):
    ruta = tmp_path / "ejecutar-nodo.js"
    ruta.write_text(
        f"{preambulo}\n(async () => {{\n{codigo}\n}})()"
        ".then((salida) => console.log(JSON.stringify(salida)))"
        ".catch((error) => { console.error(error.message); process.exit(1); });\n",
        encoding="utf-8",
    )
    resultado = subprocess.run(
        ["node", ruta], capture_output=True, text=True, encoding="utf-8", check=False
    )
    assert resultado.returncode == 0, resultado.stderr
    return json.loads(resultado.stdout)


def test_conexiones_apuntan_a_nodos_existentes():
    for archivo, flujo in cargar_flujos().items():
        nombres = [nodo["name"] for nodo in flujo["nodes"]]
        identificadores = [nodo["id"] for nodo in flujo["nodes"]]
        assert len(nombres) == len(set(nombres)), archivo
        assert len(identificadores) == len(set(identificadores)), archivo
        for origen, salidas in flujo.get("connections", {}).items():
            assert origen in nombres, f"{archivo}: {origen}"
            for grupos in salidas.values():
                for grupo in grupos:
                    for conexion in grupo:
                        assert conexion["node"] in nombres, f"{archivo}: {conexion['node']}"


def test_codigo_de_nodos_es_javascript_valido(tmp_path):
    for archivo, flujo in cargar_flujos().items():
        for nodo in flujo["nodes"]:
            codigo = nodo.get("parameters", {}).get("jsCode")
            if not codigo:
                continue
            ruta = tmp_path / f"{Path(archivo).stem}-{nodo['id']}.js"
            ruta.write_text(f"async function nodo() {{\n{codigo}\n}}\n", encoding="utf-8")
            resultado = subprocess.run(
                ["node", "--check", ruta], capture_output=True, text=True, check=False
            )
            assert resultado.returncode == 0, resultado.stderr


def test_expresiones_de_cuerpos_http_son_javascript_valido(tmp_path):
    for archivo, flujo in cargar_flujos().items():
        for nodo in flujo["nodes"]:
            cuerpo = nodo.get("parameters", {}).get("jsonBody")
            if not cuerpo or not cuerpo.startswith("={{"):
                continue
            expresion = cuerpo[3:-2]
            ruta = tmp_path / f"expresion-{Path(archivo).stem}-{nodo['id']}.js"
            ruta.write_text(f"const cuerpo = ({expresion});\n", encoding="utf-8")
            resultado = subprocess.run(
                ["node", "--check", ruta], capture_output=True, text=True, check=False
            )
            assert resultado.returncode == 0, resultado.stderr


def test_seguimiento_separa_orquestacion_e_interpretacion():
    flujos = cargar_flujos()
    diario = flujos["seguimiento-diario-proveedores.json"]
    respuestas = flujos["analizar-respuestas-proveedores.json"]

    tipos_diarios = {nodo["type"] for nodo in diario["nodes"]}
    tipos_respuestas = {nodo["type"] for nodo in respuestas["nodes"]}

    assert "n8n-nodes-base.scheduleTrigger" in tipos_diarios
    assert "n8n-nodes-base.gmail" not in tipos_diarios
    assert "n8n-nodes-base.gmailTrigger" in tipos_respuestas
    assert "@n8n/n8n-nodes-langchain.chainLlm" in tipos_respuestas
    assert "@n8n/n8n-nodes-langchain.lmChatGoogleGemini" in tipos_respuestas
    assert "@n8n/n8n-nodes-langchain.agent" not in tipos_respuestas


def test_seguimiento_usa_endpoint_directo_y_calendario_por_proveedor():
    flujos = cargar_flujos()
    for archivo, flujo in flujos.items():
        for nodo in flujo["nodes"]:
            url = nodo.get("parameters", {}).get("url", "")
            if "nhost.run" in url and "graphql" in url:
                assert ".hasura." in url, archivo
                assert url.endswith("/v1/graphql"), archivo

    diario = flujos["seguimiento-diario-proveedores.json"]
    preparar = next(
        nodo for nodo in diario["nodes"]
        if nodo["name"] == "Preparar resumen y exclusiones"
    )
    codigo = preparar["parameters"]["jsCode"]
    assert "diasProveedor" in codigo
    assert "primerEnvio" not in codigo


def test_clasificacion_rechaza_confianza_invalida_y_exige_version_coherente():
    respuestas = cargar_flujos()["analizar-respuestas-proveedores.json"]
    validar = next(
        nodo for nodo in respuestas["nodes"]
        if nodo["name"] == "Validar clasificación"
    )
    codigo = validar["parameters"]["jsCode"]
    assert "Number.isFinite(confianzaRecibida)" in codigo
    assert "versionFinalCoherente" in codigo


def test_analisis_procesa_cada_correo_y_recupera_los_omitidos(tmp_path):
    respuestas = cargar_flujos()["analizar-respuestas-proveedores.json"]
    nodos = {nodo["name"]: nodo for nodo in respuestas["nodes"]}

    assert nodos["Normalizar correo"]["parameters"]["mode"] == "runOnceForEachItem"
    assert nodos["Preparar contexto"]["parameters"]["mode"] == "runOnceForEachItem"
    assert nodos["Validar clasificación"]["parameters"]["mode"] == "runOnceForEachItem"

    revision = nodos["Revisión horaria de correos"]
    assert revision["parameters"]["rule"]["interval"][0]["expression"] == "0 * * * *"
    recuperacion = nodos["Recuperar correos recientes"]["parameters"]
    assert recuperacion["operation"] == "getAll"
    assert recuperacion["limit"] == 500
    assert recuperacion["filters"]["q"] == "newer_than:30d subject:Cotización -from:me"
    assert recuperacion["filters"]["readStatus"] == "both"

    consulta = nodos["Consultar contexto en Nhost"]["parameters"]["jsonBody"]
    assert "correo_existente" in consulta
    assert "gmail_message_id: { _eq: $messageId }" in consulta
    assert "_costflow_version" in nodos["Preparar contexto"]["parameters"]["jsCode"]

    registro = nodos["Registrar respuesta y notificación"]["parameters"]["jsonBody"]
    assert "ultimo_correo_at: { _lte: $recibidoAt }" in registro
    assert "update_solicitud_proveedores(" in registro

    filtro = nodos["Filtrar correos pendientes"]["parameters"]["jsCode"]
    preambulo = "const $input = { all: () => [{json: {id: 1}}, {json: {id: 2}}, {json: {omitir: true}}] };"
    salida = ejecutar_javascript(filtro, preambulo, tmp_path)
    assert [item["json"]["id"] for item in salida] == [1, 2]


def test_clasificacion_distingue_ficha_tecnica_sin_cotizacion():
    respuestas = cargar_flujos()["analizar-respuestas-proveedores.json"]
    nodos = {nodo["name"]: nodo for nodo in respuestas["nodes"]}
    preparar = nodos["Preparar contexto"]["parameters"]["jsCode"]
    validar = nodos["Validar clasificación"]["parameters"]["jsCode"]
    sistema = nodos["Clasificar respuesta"]["parameters"]["messages"]["messageValues"][0]["message"]

    assert "ficha_tecnica_sin_cotizacion" in preparar
    assert "ficha_tecnica_sin_cotizacion" in validar
    assert "ficha_tecnica_sin_cotizacion" in sistema


def test_seguimiento_omite_proveedor_sin_envio_y_respeta_su_fecha(tmp_path):
    diario = cargar_flujos()["seguimiento-diario-proveedores.json"]
    preparar = next(
        nodo for nodo in diario["nodes"]
        if nodo["name"] == "Preparar resumen y exclusiones"
    )
    datos = {
        "solicitudes_cotizacion": [{
            "id": "s1", "codigo": "SC-001", "nombre": "Prueba",
            "creado_por": "u1", "fecha_limite": "2026-10-30",
            "frecuencia_aviso_dias": 2, "partida_critica": False,
        }],
        "solicitud_proveedores": [
            {
                "solicitud_id": "s1", "proveedor_id": "p1",
                "estado_respuesta": "no_envio_cotizacion", "considerado": True,
                "numero_coordinaciones": 0,
                "proveedor_asociado": {"nombre": "Con envío", "correo": "uno@example.com"},
            },
            {
                "solicitud_id": "s1", "proveedor_id": "p2",
                "estado_respuesta": "no_envio_cotizacion", "considerado": True,
                "numero_coordinaciones": 0,
                "proveedor_asociado": {"nombre": "Sin envío", "correo": "dos@example.com"},
            },
        ],
        "envios_solicitud": [{
            "solicitud_id": "s1", "proveedor_id": "p1",
            "enviado_at": "2026-10-24T15:00:00Z",
        }],
        "notificaciones": [],
    }
    preambulo = (
        f"const $json = {{data: {json.dumps(datos)}}};\n"
        "const $now = { setZone: () => ({ toISODate: () => '2026-10-26' }) };"
    )
    salida = ejecutar_javascript(preparar["parameters"]["jsCode"], preambulo, tmp_path)
    proveedores = salida[0]["json"]["notificacion"]["datos"]["proveedores"]
    assert [item["proveedor"] for item in proveedores] == ["Con envío"]


def test_confianza_invalida_solicita_revision_sin_aplicar(tmp_path):
    respuestas = cargar_flujos()["analizar-respuestas-proveedores.json"]
    validar = next(
        nodo for nodo in respuestas["nodes"]
        if nodo["name"] == "Validar clasificación"
    )
    contexto = {
        "messageId": "m1", "threadId": "t1", "remitente": "p@example.com",
        "destinatarios": ["c@example.com"], "asunto": "Respuesta", "cuerpo": "Recibido",
        "recibidoAt": "2026-10-26T10:00:00-05:00", "adjuntos": [],
        "candidatos": [{
            "solicitud_id": "s1", "proveedor_id": "p1", "considerado": True,
            "proveedor_asociado": {"nombre": "Proveedor"},
            "solicitud_cotizacion": {
                "codigo": "SC-001", "estado": "inicio",
                "fecha_limite": "2026-10-30", "creado_por": "u1",
            },
        }],
    }
    modelo = {
        "solicitudId": "s1", "proveedorId": "p1",
        "estado": "no_envio_cotizacion", "detalle": "confirmo_recepcion",
        "esVersionFinal": False, "aclaraciones": [], "evidencia": ["Acuse"],
        "confianza": "valor-invalido", "razon": "Solo confirmó recepción",
    }
    preambulo = (
        f"const contextoPrueba = {json.dumps(contexto)};\n"
        f"const $json = {{text: JSON.stringify({json.dumps(modelo)})}};\n"
        "const $ = () => ({ item: { json: contextoPrueba } });"
    )
    salida = ejecutar_javascript(validar["parameters"]["jsCode"], preambulo, tmp_path)
    assert salida["json"]["aplicar"] is False
    assert salida["json"]["notificar"] is True
    assert salida["json"]["cambios"]["confianza_clasificacion"] == 0


def test_ficha_tecnica_cuenta_como_respuesta_sin_sumar_cotizacion(tmp_path):
    respuestas = cargar_flujos()["analizar-respuestas-proveedores.json"]
    validar = next(
        nodo for nodo in respuestas["nodes"]
        if nodo["name"] == "Validar clasificación"
    )
    contexto = {
        "messageId": "m-ficha", "threadId": "t1", "remitente": "p@example.com",
        "destinatarios": ["c@example.com"], "asunto": "Ficha técnica",
        "cuerpo": "Adjunto ficha técnica para revisión",
        "recibidoAt": "2026-10-25T10:00:00-05:00", "adjuntos": [{"nombre": "ficha.pdf"}],
        "versionAnalisis": 2,
        "candidatos": [{
            "solicitud_id": "s1", "proveedor_id": "p1", "considerado": True,
            "ultimo_correo_at": None,
            "proveedor_asociado": {"nombre": "Proveedor"},
            "solicitud_cotizacion": {
                "codigo": "MA-001", "estado": "inicio",
                "fecha_limite": "2026-11-29", "creado_por": "u1",
            },
        }],
    }
    modelo = {
        "solicitudId": "s1", "proveedorId": "p1",
        "estado": "no_envio_cotizacion", "detalle": "ficha_tecnica_sin_cotizacion",
        "esVersionFinal": False, "aclaraciones": [], "evidencia": ["Adjunta ficha técnica"],
        "confianza": 0.96, "razon": "Envió una ficha técnica sin precios.",
    }
    preambulo = (
        f"const contextoPrueba = {json.dumps(contexto)};\n"
        f"const $json = {{text: JSON.stringify({json.dumps(modelo)})}};\n"
        "const $ = () => ({ item: { json: contextoPrueba } });"
    )
    salida = ejecutar_javascript(validar["parameters"]["jsCode"], preambulo, tmp_path)["json"]

    assert salida["aplicar"] is True
    assert salida["cambios"]["estado"] == "respondio"
    assert salida["cambios"]["estado_respuesta"] == "no_envio_cotizacion"
    assert salida["cambios"]["detalle_respuesta"] == "ficha_tecnica_sin_cotizacion"
    assert "ficha técnica, sin cotización" in salida["notificacion"]["titulo"]
    assert salida["correo"]["analisis_agente"]["_costflow_version"] == 2


def test_correo_antiguo_no_sobrescribe_el_ultimo_estado(tmp_path):
    respuestas = cargar_flujos()["analizar-respuestas-proveedores.json"]
    validar = next(
        nodo for nodo in respuestas["nodes"]
        if nodo["name"] == "Validar clasificación"
    )
    contexto = {
        "messageId": "m-antiguo", "threadId": "t1", "remitente": "p@example.com",
        "destinatarios": ["c@example.com"], "asunto": "Respuesta", "cuerpo": "Recibido",
        "recibidoAt": "2026-10-24T10:00:00-05:00", "adjuntos": [], "versionAnalisis": 2,
        "candidatos": [{
            "solicitud_id": "s1", "proveedor_id": "p1", "considerado": True,
            "ultimo_correo_at": "2026-10-26T10:00:00-05:00",
            "proveedor_asociado": {"nombre": "Proveedor"},
            "solicitud_cotizacion": {
                "codigo": "MA-001", "estado": "inicio",
                "fecha_limite": "2026-11-29", "creado_por": "u1",
            },
        }],
    }
    modelo = {
        "solicitudId": "s1", "proveedorId": "p1",
        "estado": "no_envio_cotizacion", "detalle": "confirmo_recepcion",
        "esVersionFinal": False, "aclaraciones": [], "evidencia": ["Confirmación"],
        "confianza": 0.95, "razon": "Confirmó recepción.",
    }
    preambulo = (
        f"const contextoPrueba = {json.dumps(contexto)};\n"
        f"const $json = {{text: JSON.stringify({json.dumps(modelo)})}};\n"
        "const $ = () => ({ item: { json: contextoPrueba } });"
    )
    salida = ejecutar_javascript(validar["parameters"]["jsCode"], preambulo, tmp_path)["json"]

    assert salida["aplicar"] is False
    assert salida["notificar"] is True


def test_exportaciones_solo_referencian_credenciales_reemplazables():
    for archivo, flujo in cargar_flujos().items():
        for nodo in flujo["nodes"]:
            for credencial in nodo.get("credentials", {}).values():
                assert credencial["id"].startswith("REEMPLAZAR_"), archivo
