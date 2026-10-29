"""E5: llenado de la plantilla con una homologación ficticia. La plantilla real es privada; aquí se usa una mínima con las mismas celdas."""
import base64
import copy
import io
import re
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etapa4"))

from app.cuadro import server  # noqa: E402
from app.cuadro.llenar import CuadroNoGenerable, generar, plan  # noqa: E402
from app.homologacion import entrada  # noqa: E402
from app.homologacion.construir import build  # noqa: E402
from datos_ficticios import ALFA, GAMMA, paquete, respuesta_modelo  # noqa: E402


def plantilla_minima() -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "PLANTILLA"
    hoja["B3"] = '="COMPARATIVO - "&$I$3'
    for ref in ("I3", "F5", "B13", "C13", "D13", "E13"):
        hoja[ref] = 0
    hoja["F13"] = "=E13*D13"
    for n, cant, usd, pen, total in [("H", "H", "I", "J", "K"), ("L", "L", "M", "N", "O"), ("P", "P", "Q", "R", "S"), ("T", "T", "U", "V", "W"),
                                     ("X", "X", "Y", "Z", "AA"), ("AB", "AB", "AC", "AD", "AE"), ("AF", "AF", "AG", "AH", "AI")]:
        hoja[f"{n}6"] = "PROVEEDOR"
        hoja[f"{cant}13"], hoja[f"{usd}13"] = 0, 0
        hoja[f"{pen}13"] = f"={usd}13*$F$5"
        hoja[f"{total}13"] = f"={pen}13*{cant}13"
        for fila in (30, 33, 36):
            hoja[f"{n}{fila}"] = "-"
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def homologacion(una_partida=True, cambiar=None):
    datos = paquete(True)
    if cambiar:
        cambiar(datos)
    preparado = entrada.prepare(datos)
    salida = respuesta_modelo(preparado, True)
    if una_partida:
        salida["partidas"] = salida["partidas"][:1]
        preparado["base"]["partidas"] = preparado["base"]["partidas"][:1]
    return build(preparado, salida, "claude-sonnet-5-5")


def hoja_xml(archivo: bytes) -> str:
    return ZipFile(io.BytesIO(archivo)).read("xl/worksheets/sheet1.xml").decode()


def celda(xml: str, ref: str) -> str:
    return re.search(r'<c r="%s"[^>]*?(?:/>|>.*?</c>)' % ref, xml, re.S).group(0)


def test_llena_partida_proveedores_y_condiciones_con_numeros_de_e3():
    h = homologacion()
    archivo, validacion = generar(plantilla_minima(), h, {"valor": 3.75, "fecha": "2026-10-29", "fuente": "SBS"})
    xml = hoja_xml(archivo)
    assert "Ascensor de pasajeros 630 kg, 8 personas" in celda(xml, "I3") and "<v>2</v>" in celda(xml, "D13")
    nombres = sorted(p["nombre"] for p in h["postores"])
    assert [nombres[i] in celda(xml, c + "6") for i, c in enumerate(("H", "L", "P"))] == [True] * 3
    assert "<v>3.75</v>" in celda(xml, "F5")
    # Alfa (2 ítems de 36 800 agrupados): cantidad 2, unitario 36 800; Beta: 2 x 36 937,55; Gamma: 2 x 37 790.
    assert ("<v>2</v>" in celda(xml, "H13")) and "<v>36800</v>" in celda(xml, "I13")
    assert "<v>36937.55</v>" in celda(xml, "M13") and "<v>37790</v>" in celda(xml, "Q13")
    assert "8.5 meses" in celda(xml, "L30") and "Cuotas" in celda(xml, "P33")
    assert "Vigencia de la oferta: 15 días" in celda(xml, "H36") and "-" in celda(xml, "T30")  # sin proveedor: la plantilla queda como estaba
    assert validacion["tipo_cambio"]["fuente"] == "SBS" and all(c["cuadra"] for c in validacion["comprobaciones"])


def test_las_formulas_se_conservan_y_el_libro_recalcula_al_abrir():
    archivo, _ = generar(plantilla_minima(), homologacion(), {"valor": 3.75})
    z = ZipFile(io.BytesIO(archivo))
    xml = z.read("xl/worksheets/sheet1.xml").decode()
    assert "<f>I13*$F$5</f>" in celda(xml, "J13") and "<v>" not in celda(xml, "J13")
    assert 'fullCalcOnLoad="1"' in z.read("xl/workbook.xml").decode()
    assert "calcChain" not in " ".join(z.namelist())


def test_sin_tipo_de_cambio_con_ofertas_en_dolares_queda_borrador_y_avisa():
    _, validacion = generar(plantilla_minima(), homologacion(), None)
    assert validacion["validado"] is False
    assert any("tipo de cambio" in a for a in validacion["avisos"])


def test_con_todo_resuelto_el_cuadro_queda_validado():
    h = homologacion()
    h["pendientes"] = [p for p in h["pendientes"] if not p["bloquea_comparacion"]]
    h["estado_revision"] = "listo_para_cuadro"
    resultado = plan(h, {"valor": 3.75})
    assert resultado["pendientes_bloqueantes"] == 0
    sin_avisos = [a for a in resultado["avisos"] if "ítems agrupados" not in a]
    assert sin_avisos == []


def test_un_proveedor_con_dos_tipos_ocupa_dos_bloques():
    h = homologacion(una_partida=False)
    archivo, validacion = generar(plantilla_minima(), h, {"valor": 3.75})
    xml = hoja_xml(archivo)
    # Alfa y Beta cotizan solo el tipo 1; Gamma cotiza los dos y ocupa dos bloques.
    assert validacion["bloques"] == 4
    assert "Gamma Lift (TIPO 1)" in celda(xml, "P6") and "Gamma Lift (TIPO 2)" in celda(xml, "T6")
    assert "Alfa SAC</t>" in celda(xml, "H6") and "TIPO" not in celda(xml, "H6")
    assert "Tipo 2: Ascensor de pasajeros 750 kg" in celda(xml, "T36")
    assert "<v>36849.07</v>" in celda(xml, "U13") and "<v>37790</v>" in celda(xml, "Q13")
    assert "ELEVADORES" in celda(xml, "I3") or "Ascensores" in celda(xml, "I3")


def test_mas_bloques_que_los_de_la_plantilla_se_rechaza():
    h = homologacion(una_partida=False)
    extra = copy.deepcopy(h["postores"][0])
    for i in range(5):
        otro = copy.deepcopy(extra)
        otro["proveedor_id"] = f"extra-{i}"
        otro["nombre"] = f"Extra {i}"
        h["postores"].append(otro)
        for partida in h["partidas"]:
            partida["ofertas"].append({**copy.deepcopy(partida["ofertas"][0]), "proveedor_id": f"extra-{i}"})
    with pytest.raises(CuadroNoGenerable, match="bloques"):
        generar(plantilla_minima(), h, {"valor": 3.75})


def test_moneda_desconocida_o_sin_importes_deja_el_bloque_vacio_y_en_borrador():
    h = homologacion()
    beta = next(p for p in h["postores"] if p["nombre"] == "Beta SA")
    beta["moneda"] = None
    archivo, validacion = generar(plantilla_minima(), h, {"valor": 3.75})
    assert validacion["validado"] is False and any("Beta SA: moneda" in a for a in validacion["avisos"])
    alfa = next(o for o in h["partidas"][0]["ofertas"] if o["proveedor_id"] == ALFA)
    for i in alfa["items"]:
        i["original"]["parcial"] = None
    resultado = plan(h, {"valor": 3.75})
    assert any("faltan importes" in a for a in resultado["avisos"])


def test_tipo_de_cambio_invalido_o_plantilla_ajena_se_rechazan():
    with pytest.raises(CuadroNoGenerable, match="tipo de cambio"):
        generar(plantilla_minima(), homologacion(), {"valor": -1})
    otra = Workbook()
    otra.active["A1"] = 1
    salida = io.BytesIO()
    otra.save(salida)
    with pytest.raises(CuadroNoGenerable):
        generar(salida.getvalue(), homologacion(), {"valor": 3.75})


@pytest.fixture
def cliente(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("E3_INTERNAL_KEY", "clave")
    return TestClient(server.app)


def test_servicio_exige_clave_y_devuelve_xlsx_en_base64(cliente):
    cuerpo = {"homologacion": homologacion(), "tipo_cambio": {"valor": 3.75}, "plantilla_b64": base64.b64encode(plantilla_minima()).decode()}
    assert cliente.post("/e5/generar", json=cuerpo).status_code == 401
    r = cliente.post("/e5/generar", json=cuerpo, headers={"X-Costflow-Internal-Key": "clave"})
    assert r.status_code == 200 and r.json()["estado"] in ("borrador", "validado")
    assert ZipFile(io.BytesIO(base64.b64decode(r.json()["archivo_b64"]))).testzip() is None


def test_servicio_responde_error_no_recuperable(cliente):
    cabecera = {"X-Costflow-Internal-Key": "clave"}
    r = cliente.post("/e5/generar", json={"homologacion": {**homologacion(), "partidas": []}, "plantilla_b64": base64.b64encode(plantilla_minima()).decode()}, headers=cabecera)
    assert r.status_code == 422 and r.json()["recuperable"] is False
    r = cliente.post("/e5/generar", json={"homologacion": homologacion(), "plantilla_b64": "no-es-base64"}, headers=cabecera)
    assert r.status_code == 422
