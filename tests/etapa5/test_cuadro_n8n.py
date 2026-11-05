"""E5 dentro de n8n: el JavaScript de los nodos equivale a app/cuadro/llenar.py (que queda como referencia)."""
import base64
import copy
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import openpyxl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etapa4"))

from app.cuadro import llenar as L  # noqa: E402
from test_cuadro import homologacion, hoja_xml, plantilla_minima  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="Estas pruebas ejecutan el código de los nodos y requieren Node.js.")
TC = {"valor": 3.75, "fecha": "2026-11-05", "fuente": "SBS"}


def variantes():
    una, dos = homologacion(), homologacion(una_partida=False)
    sin_moneda = copy.deepcopy(una)
    next(p for p in sin_moneda["postores"] if p["nombre"] == "Beta SA")["moneda"] = None
    sin_parcial = copy.deepcopy(una)
    for oferta in sin_parcial["partidas"][0]["ofertas"]:
        for i in oferta["items"]:
            i["original"]["parcial"] = None
    sin_cantidad = copy.deepcopy(una)
    for oferta in sin_cantidad["partidas"][0]["ofertas"]:
        for i in oferta["items"]:
            i["original"]["cantidad"] = None
    todo_pen = copy.deepcopy(una)
    for p in todo_pen["postores"]:
        p["moneda"] = "PEN"
    return {"una_partida_tc": (una, TC), "una_partida_sin_tc": (una, None), "dos_partidas_tc": (dos, TC), "dos_partidas_sin_tc": (dos, None),
            "sin_moneda": (sin_moneda, TC), "sin_parcial": (sin_parcial, TC), "sin_cantidad": (sin_cantidad, TC), "todo_pen": (todo_pen, None),
            "tc_invalido": (una, {"valor": -1}), "sin_partidas": ({**una, "partidas": []}, TC)}


def test_el_javascript_da_lo_mismo_que_python(tmp_path):
    plantilla = plantilla_minima()
    zip_entrada = ZipFile(io.BytesIO(plantilla))
    casos = {}
    for nombre, (h, tc) in variantes().items():
        caso = {"homologacion": h, "tipo_cambio": tc}
        try:
            r = L.plan(h, tc)
            z = ZipFile(io.BytesIO(L.llenar(plantilla, r["celdas"])))
            caso["minima"] = {
                "hoja_entrada": hoja_xml(plantilla), "plan": r,
                "salida": {n: z.read(n).decode("utf-8") for n in ("xl/worksheets/sheet1.xml", "xl/workbook.xml", "[Content_Types].xml",
                                                                   "xl/_rels/workbook.xml.rels") if n in z.namelist()},
                "workbook_entrada": zip_entrada.read("xl/workbook.xml").decode("utf-8"),
                "tipos_entrada": zip_entrada.read("[Content_Types].xml").decode("utf-8"),
                "rels_entrada": zip_entrada.read("xl/_rels/workbook.xml.rels").decode("utf-8")}
        except L.CuadroNoGenerable as error:
            caso["minima"] = {"error": str(error)}
        casos[nombre] = caso
    archivo = tmp_path / "casos.json"
    archivo.write_text(json.dumps(casos, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([NODE, "--test", str(ROOT / "tests/etapa5/cuadro_paridad.test.js")], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "CASOS": str(archivo)}, timeout=120)
    assert r.returncode == 0, r.stdout[-2500:] + r.stderr[-1500:]


def codigo_llenar():
    spec = importlib.util.spec_from_file_location("generador_e5", ROOT / "n8n/etapa5/generar.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.LLENAR_PLANTILLA


def correr_nodo_llenar(plantilla: bytes, homologacion_json, tipo_cambio):
    """Ejecuta el nodo «Llenar plantilla» con n8n simulado: los archivos llegan sin carpeta, como los entrega el nodo Descomprimir."""
    z = ZipFile(io.BytesIO(plantilla))
    archivos = [{"nombre": i.filename.split("/")[-1], "b64": base64.b64encode(z.read(i.filename)).decode()}
                for i in z.infolist() if not i.filename.endswith("/")]
    peticion = {"codigo": codigo_llenar(), "original_b64": base64.b64encode(plantilla).decode(), "archivos": archivos,
                "ctx": {"cuadro_id": "c1", "token": "t1", "entrada": {"solicitud": {"codigo": "MA-001"}, "revision": 3,
                                                                      "homologacion": homologacion_json, "tipo_cambio": tipo_cambio}}}
    r = subprocess.run([NODE, str(ROOT / "tests/etapa5/glue_harness.js")], input=json.dumps(peticion), capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def empaquetar(resultado) -> bytes:
    """Lo que hace el nodo «Comprimir»: un zip con cada binario en la ruta de su fileName."""
    salida = io.BytesIO()
    with ZipFile(salida, "w", ZIP_DEFLATED) as destino:
        for binario in resultado["binary"].values():
            destino.writestr(binario["fileName"], base64.b64decode(binario["b64"]))
    return salida.getvalue()


def test_el_nodo_devuelve_cada_archivo_en_su_carpeta_y_el_libro_abre_igual_que_con_python():
    plantilla = plantilla_minima()
    r = correr_nodo_llenar(plantilla, homologacion(una_partida=False), TC)
    assert r["json"]["ok"] is True and r["json"]["validacion"]["bloques"] == 4
    nombres = {b["fileName"] for b in r["binary"].values()}
    assert {"xl/worksheets/sheet1.xml", "xl/workbook.xml", "[Content_Types].xml", "xl/_rels/workbook.xml.rels"} <= nombres
    assert r["json"]["propiedades"] == ",".join(r["binary"])
    referencia, _ = L.generar(plantilla, homologacion(una_partida=False), TC)
    zip_js = empaquetar(r)
    hoja_js = openpyxl.load_workbook(io.BytesIO(zip_js))["PLANTILLA"]
    hoja_py = openpyxl.load_workbook(io.BytesIO(referencia))["PLANTILLA"]
    for ref in ("I3", "F5", "H6", "P6", "T6", "H13", "I13", "M13", "Q13", "U13", "L30", "P33", "T36"):
        assert hoja_js[ref].value == hoja_py[ref].value, ref
    z_js, z_py = ZipFile(io.BytesIO(zip_js)), ZipFile(io.BytesIO(referencia))
    assert sorted(z_js.namelist()) == sorted(z_py.namelist())
    assert all(z_js.read(n) == z_py.read(n) for n in z_py.namelist())


def test_una_plantilla_ajena_o_una_homologacion_imposible_no_se_reintenta():
    otra = openpyxl.Workbook()
    otra.active["A1"] = 1
    buffer = io.BytesIO()
    otra.save(buffer)
    r = correr_nodo_llenar(buffer.getvalue(), homologacion(), TC)
    assert r["json"]["ok"] is False and r["json"]["recuperable"] is False and r["binary"] == {}
    r = correr_nodo_llenar(plantilla_minima(), {**homologacion(), "partidas": []}, TC)
    assert r["json"]["ok"] is False and r["json"]["recuperable"] is False and "no tiene partidas" in r["json"]["error"]
