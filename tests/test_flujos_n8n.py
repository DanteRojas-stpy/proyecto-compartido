import json
import subprocess
from pathlib import Path


FLUJOS = Path(__file__).parents[1] / "n8n" / "flujos"


def cargar_flujos():
    return {ruta.name: json.loads(ruta.read_text(encoding="utf-8")) for ruta in FLUJOS.glob("*.json")}


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
    assert "@n8n/n8n-nodes-langchain.agent" in tipos_respuestas


def test_exportaciones_solo_referencian_credenciales_reemplazables():
    for archivo, flujo in cargar_flujos().items():
        for nodo in flujo["nodes"]:
            for credencial in nodo.get("credentials", {}).values():
                assert credencial["id"].startswith("REEMPLAZAR_"), archivo
