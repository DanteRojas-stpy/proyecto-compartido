"""Los cinco flujos de E3 corren solo con nodos de n8n: estructura, referencias entre nodos y código de cada nodo."""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CARPETA = ROOT / "n8n" / "etapa3"
PERMITIDAS = {
    "https://SUBDOMINIO.functions.REGION.nhost.run/v1/e3-operar",
    "https://SUBDOMINIO.storage.REGION.nhost.run/v1/files",
    "https://SUBDOMINIO.auth.REGION.nhost.run/v1/user",
    "https://api.anthropic.com/v1/messages",
}


@pytest.fixture(scope="module")
def flujos():
    spec = importlib.util.spec_from_file_location("generador_e3", CARPETA / "generar.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.generate()


def nodos_de(flujo):
    return {n["name"]: n for n in flujo["nodes"]}


def test_los_json_del_repositorio_son_los_que_genera_el_generador(flujos):
    for flujo in flujos:
        guardado = json.loads((CARPETA / f"e3-{flujo['id'][-1]}.json").read_text(encoding="utf-8"))
        assert guardado == flujo, f"Regenera e3-{flujo['id'][-1]}.json con n8n/etapa3/generar.py"


def test_ningun_nodo_llama_a_un_servicio_propio(flujos):
    for flujo in flujos:
        texto = json.dumps(flujo)
        assert "costflow-etapa3" not in texto and "8093" not in texto and "host.docker.internal" not in texto
        for nodo in flujo["nodes"]:
            url = nodo["parameters"].get("url")
            if url and not url.startswith("="):
                assert url in PERMITIDAS, f"{flujo['name']} · {nodo['name']} llama a {url}"
            assert "credentials" not in nodo


def test_conexiones_y_entradas_de_merge_son_validas(flujos):
    for flujo in flujos:
        nodos = nodos_de(flujo)
        entradas: dict[str, set[int]] = {}
        for origen, salidas in flujo["connections"].items():
            assert origen in nodos
            for rama in salidas["main"]:
                for destino in rama:
                    assert destino["node"] in nodos
                    entradas.setdefault(destino["node"], set()).add(destino["index"])
        for nombre, nodo in nodos.items():
            if nodo["type"].endswith(".merge"):
                assert entradas.get(nombre) == {0, 1}, f"{flujo['name']} · {nombre} necesita dos entradas"


def test_cada_nodo_es_alcanzable_desde_un_disparador(flujos):
    for flujo in flujos:
        nodos = nodos_de(flujo)
        pendientes = [n for n, x in nodos.items() if any(t in x["type"] for t in ("Trigger", "webhook"))]
        vistos = set(pendientes)
        while pendientes:
            for rama in flujo["connections"].get(pendientes.pop(), {"main": []})["main"]:
                for destino in rama:
                    if destino["node"] not in vistos:
                        vistos.add(destino["node"])
                        pendientes.append(destino["node"])
        assert vistos == set(nodos), f"{flujo['name']}: sin conexión {sorted(set(nodos) - vistos)}"


def test_el_codigo_cita_solo_nodos_que_existen(flujos):
    for flujo in flujos:
        nombres = set(nodos_de(flujo))
        for nodo in flujo["nodes"]:
            texto = nodo["parameters"].get("jsCode", "") + json.dumps(nodo["parameters"], ensure_ascii=False)
            for citado in re.findall(r"\$\('([^']+)'\)", texto):
                assert citado in nombres, f"{flujo['name']} · {nodo['name']} cita «{citado}», que no existe"


def test_las_peticiones_a_nhost_separan_las_llaves_de_la_expresion(flujos):
    for flujo in flujos:
        for nodo in flujo["nodes"]:
            cuerpo = nodo["parameters"].get("jsonBody", "")
            if "operacion:" in cuerpo:
                assert cuerpo.endswith(" }) }}") and "}}}" not in cuerpo, f"{nodo['name']}: el primer }} cerraría la expresión"


def test_no_quedan_marcadores_sin_resolver_en_el_codigo(flujos):
    for flujo in flujos:
        for nodo in flujo["nodes"]:
            assert not re.search(r"__[A-Z]+__", nodo["parameters"].get("jsCode", "")), f"{nodo['name']} conserva un marcador"


def test_la_credencial_de_cada_nodo_queda_marcada(flujos):
    for flujo in flujos:
        for nodo in flujo["nodes"]:
            if nodo["type"].endswith("httpRequest") and nodo["parameters"].get("authentication") == "genericCredentialType":
                assert nodo["notes"].startswith("CREDENCIAL_E3:")


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js no está instalado")
def test_el_codigo_de_todos_los_nodos_es_javascript_valido(flujos, tmp_path):
    for flujo in flujos:
        for nodo in flujo["nodes"]:
            codigo = nodo["parameters"].get("jsCode")
            if not codigo:
                continue
            archivo = tmp_path / "nodo.js"
            archivo.write_text("(async function(){\n" + codigo + "\n})", encoding="utf-8")
            resultado = subprocess.run(["node", "--check", str(archivo)], capture_output=True, text=True)
            assert resultado.returncode == 0, f"{flujo['name']} · {nodo['name']}: {resultado.stderr[:300]}"


def test_el_flujo_de_recepcion_usa_gmail_solo_para_leer(flujos):
    gmail = [n for f in flujos for n in f["nodes"] if n["type"].endswith(".gmail")]
    assert len(gmail) == 1
    assert gmail[0]["parameters"]["operation"] == "get" and gmail[0]["parameters"]["options"]["downloadAttachments"]


def test_los_subflujos_se_invocan_sin_esperar_la_respuesta(flujos):
    for flujo in flujos:
        for nodo in flujo["nodes"]:
            if nodo["type"].endswith("executeWorkflow"):
                assert nodo["parameters"]["options"]["waitForSubWorkflow"] is False
