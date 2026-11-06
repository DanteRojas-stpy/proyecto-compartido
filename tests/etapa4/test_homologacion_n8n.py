"""E4 dentro de n8n: el JavaScript de los nodos equivale a app/homologacion (que queda como referencia y se usa en las pruebas)."""
import copy
import importlib.util
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.homologacion import contrato, entrada
from app.homologacion.construir import HomologacionInvalida, build
from datos_ficticios import ALFA, BETA, GAMMA, paquete, respuesta_modelo

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="Estas pruebas ejecutan el código de los nodos y requieren Node.js.")
AHORA = datetime(2026, 11, 5, 21, 0, 0, tzinfo=timezone.utc)
MODELO = "claude-sonnet-5-5"


def modificar(cambiar):
    datos = paquete(False)
    cambiar(datos)
    return datos


def sin_moneda(d):
    for f in d["finales"]:
        if f["proveedor_id"] == GAMMA:
            for c in f["resultado"]["datos_comerciales_documentos"]:
                c["valores"]["moneda"] = None


def en_soles(d):
    for f in d["finales"]:
        if f["proveedor_id"] == BETA:
            f["resultado"]["datos_comerciales"]["moneda"] = "PEN"
            for c in f["resultado"]["datos_comerciales_documentos"]:
                c["valores"]["moneda"] = "PEN"


def subtotal_mas(delta):
    def cambiar(d):
        for f in d["finales"]:
            if f["proveedor_id"] == ALFA:
                f["resultado"]["datos_comerciales_documentos"][0]["valores"]["subtotal"] = round(73600 + delta, 2)
    return cambiar


def salida_con(cambiar):
    def aplicar(salida, preparado):
        cambiar(salida, preparado)
    return aplicar


def item_ajeno(s, p):
    s["partidas"][0]["ofertas"][0]["item_ids"] = [p["postores"][1]["items"][0]["item_id"]]


def evidencia_falsa(s, p):
    s["partidas"][0]["ofertas"][0]["evidencia_ids"] = ["00000000-0000-0000-0000-000000000000"]


def equivalente_sin_evidencia(s, p):
    for o in s["partidas"][0]["ofertas"]:
        o["evidencia_ids"] = []


def item_en_dos(s, p):
    s["partidas"][1]["ofertas"][-1]["item_ids"] = s["partidas"][0]["ofertas"][-1]["item_ids"]


def metrado_cambiado(s, p):
    s["partidas"][0]["metrado"] = 99


def olvidar_un_item(s, p):
    s["partidas"][0]["ofertas"][0]["item_ids"] = s["partidas"][0]["ofertas"][0]["item_ids"][:1]


def dudosa(s, p):
    for o in s["partidas"][0]["ofertas"]:
        o["equivalencia"] = "pendiente"
        o["evidencia_ids"] = []


def forma_invalida(s, p):
    s["partidas"][0]["ofertas"][0]["estado"] = "inventado"


def campo_extra(s, p):
    s["importe"] = 5


def caso(datos, con_itemizado=False, cambiar_salida=None):
    preparado = entrada.prepare(datos)
    salida = respuesta_modelo(preparado, con_itemizado)
    if cambiar_salida:
        cambiar_salida(salida, preparado)
    resultado = {"paquete": datos, "salida": salida, "preparado": preparado, "cuerpo_claude": contrato.request(preparado, MODELO)}
    try:
        resultado["esperado"] = {"homologacion": build(preparado, salida, MODELO, AHORA)}
    except HomologacionInvalida as error:
        resultado["esperado"] = {"errores": error.errores}
    return resultado


def todos_los_casos():
    return {
        "provisional": caso(paquete(False)), "itemizado": caso(paquete(True), True),
        "sin_moneda": caso(modificar(sin_moneda)), "otra_moneda": caso(modificar(en_soles)),
        "subtotal_dentro_de_tolerancia": caso(modificar(subtotal_mas(0.01))), "subtotal_fuera_de_tolerancia": caso(modificar(subtotal_mas(0.03))),
        "item_ajeno": caso(paquete(False), False, item_ajeno), "evidencia_falsa": caso(paquete(False), False, evidencia_falsa),
        "equivalente_sin_evidencia": caso(paquete(False), False, equivalente_sin_evidencia),
        "item_en_dos_partidas": caso(paquete(True), True, item_en_dos), "metrado_cambiado": caso(paquete(True), True, metrado_cambiado),
        "item_sin_relacionar": caso(paquete(False), False, olvidar_un_item), "equivalencia_dudosa": caso(paquete(False), False, dudosa),
        "forma_invalida": caso(paquete(False), False, forma_invalida), "campo_extra": caso(paquete(False), False, campo_extra),
    }


def test_el_javascript_da_lo_mismo_que_python(tmp_path):
    casos = todos_los_casos()
    base = json.dumps(casos["provisional"]["salida"], ensure_ascii=False)
    textos = {"limpio": base, "con_bloque": "```json\n" + base + "\n```", "con_texto": "Aquí va el resultado:\n" + base + "\nListo.",
              "vacio": "sin json", "cortado": base[:50]}
    lecturas = {}
    for nombre, texto in textos.items():
        try:
            lecturas[nombre] = {"ok": contrato.parse_text(texto)}
        except Exception as error:  # noqa: BLE001
            lecturas[nombre] = {"error": str(error)}
    archivo = tmp_path / "casos_e4.json"
    archivo.write_text(json.dumps({"casos": casos, "textos": textos, "lecturas": lecturas, "esquema": contrato.SALIDA, "ahora": AHORA.isoformat()},
                                  ensure_ascii=False, default=str), encoding="utf-8")
    r = subprocess.run([NODE, "--test", str(ROOT / "tests/etapa4/homologacion_paridad.test.js")], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "CASOS": str(archivo)}, timeout=180)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-1500:]


def generador():
    spec = importlib.util.spec_from_file_location("generador_e4", ROOT / "n8n/etapa4/generar.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def correr_nodo(codigo, entrada_json):
    """Ejecuta el código de un nodo con `$input.first().json` como entrada."""
    # El código y la entrada van por la entrada estándar: el código del nodo supera el límite de largo de la línea de comandos de Windows.
    guion = ("const { codigo, json } = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));"
             "const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;"
             "const f = new AsyncFunction('$input', codigo);"
             "f.call({}, { first: () => ({ json }) }).then((r) => process.stdout.write(JSON.stringify(r)));")
    r = subprocess.run([NODE, "-e", guion], input=json.dumps({"codigo": codigo, "json": entrada_json}), capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)[0]["json"]


def test_el_nodo_prepara_la_peticion_con_el_metodo_y_las_versiones_finales():
    g = generador()
    datos = paquete(True)
    salida = correr_nodo(g.PREPARAR_PETICION, {"paquete": datos})
    ref = entrada.prepare(datos)
    assert salida["huella"] == ref["huella"] and salida["version_ids"] == ref["version_ids"] and salida["base"] == "itemizado"
    cuerpo = salida["cuerpo_claude"]
    assert cuerpo["model"] == MODELO and cuerpo["max_tokens"] == 16000 and cuerpo["output_config"] == {"effort": "medium"}
    assert cuerpo["system"] == contrato.system_prompt()
    assert json.loads(cuerpo["messages"][0]["content"])["solicitud"]["moneda_comparacion"] == ref["solicitud"]["moneda_comparacion"]
    assert "temperature" not in cuerpo and "tool_choice" not in cuerpo
    assert correr_nodo(g.PREPARAR_PETICION, {"paquete": {}})["error"]


def test_el_nodo_construye_y_rechaza_como_el_servicio():
    g = generador()
    datos = paquete(False)
    preparado = entrada.prepare(datos)
    texto = json.dumps(respuesta_modelo(preparado))
    ok = correr_nodo(g.CONSTRUIR_VALIDAR, {"paquete": datos, "texto": texto, "modelo": MODELO})
    ref = build(preparado, contrato.parse_text(texto), MODELO, AHORA)
    assert ok["resultado"] == "construida" and ok["estado_revision"] == ref["estado_revision"] == "requiere_revision"
    assert ok["huella"] == preparado["huella"] and ok["version_ids"] == preparado["version_ids"]
    assert ok["homologacion"]["partidas"] == ref["partidas"] and ok["homologacion"]["pendientes"] == ref["pendientes"]
    malo = copy.deepcopy(respuesta_modelo(preparado))
    malo["partidas"][0]["ofertas"][0]["evidencia_ids"] = ["00000000-0000-0000-0000-000000000000"]
    r = correr_nodo(g.CONSTRUIR_VALIDAR, {"paquete": datos, "texto": json.dumps(malo), "modelo": MODELO})
    assert r["resultado"] == "respuesta_invalida" and "no existe en la entrada" in r["errores"][0]
    r = correr_nodo(g.CONSTRUIR_VALIDAR, {"paquete": datos, "texto": "no es json", "modelo": MODELO})
    assert r["resultado"] == "respuesta_invalida" and "JSON" in r["errores"][0]


def test_el_flujo_ya_no_llama_a_ningun_servicio():
    flujo = generador().generate()[0]
    assert not [n["name"] for n in flujo["nodes"] if "costflow-" in str(n["parameters"].get("url", ""))]
    nombres = {n["name"]: n["type"] for n in flujo["nodes"]}
    assert nombres["Preparar petición para Claude"].endswith(".code") and nombres["Construir y validar"].endswith(".code")
