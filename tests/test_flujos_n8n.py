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
        ["node", ruta], capture_output=True, text=True, check=False
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
    assert salida[0]["json"]["aplicar"] is False
    assert salida[0]["json"]["notificar"] is True
    assert salida[0]["json"]["cambios"]["confianza_clasificacion"] == 0


def test_exportaciones_solo_referencian_credenciales_reemplazables():
    for archivo, flujo in cargar_flujos().items():
        for nodo in flujo["nodes"]:
            for credencial in nodo.get("credentials", {}).values():
                assert credencial["id"].startswith("REEMPLAZAR_"), archivo
