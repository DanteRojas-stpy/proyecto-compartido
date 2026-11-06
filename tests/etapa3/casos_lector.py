"""Casos de referencia de E3 con Python (app/etapa3) para comparar con n8n/etapa3/lector_core.js.

Se construyen al importar el módulo; `CASOS` es un diccionario listo para serializar a JSON.
"""
import base64
import copy
import io
import json
import re
import uuid
from decimal import Decimal
from zipfile import ZipFile

import openpyxl  # noqa: E402
from jsonschema import ValidationError  # noqa: E402

from app.etapa3 import contract, documents, rag  # noqa: E402
from test_contrato import sample  # noqa: E402
from test_importes_reales import armar  # noqa: E402

CASOS = casos = {"numeros": [], "deteccion": [], "combine": [], "extraccion": [], "describe": [], "fragmentos": [], "tandas": []}

# ---- number / detección --------------------------------------------------------------------------------------------
ORIGINALES = [("Valor total de venta (sin I.G.V): 73,600.00 USD", None), ("I.G.V. 18%: 13,248.00 USD", None), ("TOTAL:\n86,848.00 USD", None), ("+1 x", None),
              ("Cantidad 2", None), ("I.G.V $\n13,604.40", None), ("Costo total US$ 73.875,10", None), ("I.G.V. 18% US$ 13.297,52", None), ("US$ 36.937,55", None),
              ("36,800", "us"), ("36.937", "eu"), ("1,250,000", "us"), ("36,800", None), ("36.937", None), ("36,800", "eu"), ("2 x 3", None), ("I.G.V.", None),
              ("1,25,000", "us"), ("-12.50", None), ("0,5", None), ("1.234.567,89", None), ("12", None), ("S/ 1,200.00", "us"), ("1.500", "eu"), ("1.500", None)]
for texto, conv in ORIGINALES:
    n = contract.number(texto, conv)
    casos["numeros"].append({"texto": texto, "convencion": conv, "esperado": None if n is None else float(n)})
TEXTOS = [["precio 36,800.00 USD y 1,200.50"], ["precio 36.937,55 y 1.200,50"], ["36,800.00 y 36.937,55"], ["sin decimales 100"],
          ["Todos los importes en dólares americanos"], ["Importes en US$ 100 y soles"], ["valor S/ 250"], ["USD pen"], ["Precio en Nuevos Soles"], ["nada"], ["total $ 50"]]
for textos in TEXTOS:
    casos["deteccion"].append({"textos": textos, "convencion": contract.detect_convention(textos), "moneda": contract.detect_currency(textos)})


# ---- combine ---------------------------------------------------------------------------------------------------------
def correr(nombre, data, source, context, modelo="modelo-prueba"):
    entrada = {"respuestas": [data], "documentos": [source], "version": context}
    try:
        r = contract.combine([copy.deepcopy(data)], [copy.deepcopy(source)], context, modelo)
        entrada["esperado"] = {"resultado": r}
    except ValidationError as e:
        entrada["esperado"] = {"error": e.message, "esquema": True}
    except ValueError as e:
        entrada["esperado"] = {"error": str(e)}
    casos["combine"].append({"nombre": nombre, **entrada})


def con(nombre, cambiar):
    data, source, context = sample()
    cambiar(data, source, context)
    correr(nombre, data, source, context)


correr("base", *sample())
con("cita_inventada", lambda d, s, c: d["evidencias"][0].update(texto_fuente="dato que no existe"))
con("item_otra_version", lambda d, s, c: d["items"][0].update(documento_id=str(uuid.uuid4())))
con("parcial_incoherente", lambda d, s, c: d["items"][0].update(parcial=999, originales={**d["items"][0]["originales"], "parcial": "999"}))
con("total_incoherente", lambda d, s, c: d["comerciales"][0]["valores"].update(total=999))


def sin_moneda_explicita(d, s, c):
    d["comerciales"][0]["originales"]["moneda"] = "dolar"


con("moneda_ambigua", sin_moneda_explicita)


def campo_faltante(d, s, c):
    d["items"][0].update(cantidad=None, originales={**d["items"][0]["originales"], "cantidad": None})


con("cantidad_faltante", campo_faltante)


def numero_distinto(d, s, c):
    d["items"][0].update(precio_unitario=101)


con("numero_no_coincide", numero_distinto)


def con_acentos(d, s, c):
    d["observaciones"] = [{"documento_id": d["documentos"][0]["documento_id"], "tipo": "garantía", "descripcion": "Garantía de 2 años — verificar", "severidad": "media",
                           "requiere_aclaracion": True, "evidencia_ids": ["e1"]}]


con("observacion_con_acentos", con_acentos)


def ocr_ignorado(d, s, c):
    d["observaciones"] = [{"documento_id": None, "tipo": "uso_ocr", "descripcion": "x", "severidad": "baja", "requiere_aclaracion": False, "evidencia_ids": []}]


con("ocr_correcto_no_es_incidencia", ocr_ignorado)


def con_especificacion(d, s, c):
    doc = d["documentos"][0]["documento_id"]
    s["fragmentos"][0]["texto"] += " capacidad 630 kg velocidad 1.75 m/s"
    d["evidencias"][0]["texto_fuente"] = s["fragmentos"][0]["texto"]
    d["especificaciones_tecnicas"] = [
        {"documento_id": doc, "referencia_item": "A", "campo": "Capacidad", "valor_original": "630 kg", "valor_numerico": 630, "unidad_original": "kg", "unidad_normalizada": None, "evidencia_ids": ["e1"]},
        {"documento_id": doc, "referencia_item": "A", "campo": "Capacidad", "valor_original": "630 kg", "valor_numerico": 630, "unidad_original": "kg", "unidad_normalizada": None, "evidencia_ids": ["e1"]},
        {"documento_id": doc, "referencia_item": None, "campo": "Velocidad", "valor_original": "1.75 m/s", "valor_numerico": 1.75, "unidad_original": "m/s", "unidad_normalizada": None, "evidencia_ids": ["e1"]}]


con("especificaciones_y_duplicados", con_especificacion)


def contradiccion(d, s, c):
    con_especificacion(d, s, c)
    doc = d["documentos"][0]["documento_id"]
    s["fragmentos"][0]["texto"] += " capacidad 800 kg"
    d["evidencias"][0]["texto_fuente"] = s["fragmentos"][0]["texto"]
    d["especificaciones_tecnicas"].append({"documento_id": doc, "referencia_item": "A", "campo": "Capacidad", "valor_original": "800 kg", "valor_numerico": 800,
                                           "unidad_original": "kg", "unidad_normalizada": None, "evidencia_ids": ["e1"]})


con("contradiccion_tecnica", contradiccion)


def sin_clasificar(d, s, c):
    d["documentos"] = []


con("documento_sin_clasificar", sin_clasificar)


def esquema_roto(d, s, c):
    d["observaciones"] = "no es lista"


con("forma_invalida", esquema_roto)

# Importes de fichas reales (test_importes_reales).
casos_reales = [
    ("Valor total de venta (sin I.G.V): 73,600.00 USD\nI.G.V. 18%: 13,248.00 USD\nTOTAL:\n86,848.00 USD",
     {"moneda": "USD", "subtotal": 73600, "impuestos": 13248, "total": 86848},
     {"moneda": "USD", "subtotal": "73,600.00 USD", "impuestos": "13,248.00 USD", "total": "86,848.00 USD"}),
    ("Costo total US$ 73.875,10\nI.G.V. 18% US$ 13.297,52\nPrecio Total US$ 87.172,62",
     {"moneda": "USD", "subtotal": 73875.10, "impuestos": 13297.52, "total": 87172.62},
     {"moneda": "US$", "subtotal": "US$ 73.875,10", "impuestos": "US$ 13.297,52", "total": "US$ 87.172,62"}),
    ("Importe $ 36,800 dólares americanos", {"moneda": "USD", "subtotal": 36800}, {"moneda": "$", "subtotal": "36,800"}),
    ("Importe 36,800 sin moneda", {"moneda": "USD", "subtotal": 36800}, {"moneda": "USD", "subtotal": "36,800"}),
]
for i, (texto, valores, originales) in enumerate(casos_reales):
    data, source, context = armar(texto, valores, originales)
    correr(f"real_{i}", data, source, context)

# ---- documentos: describe, fragmentos, tandas ---------------------------------------------------------------------------
version = str(uuid.UUID(int=123))
for nombre, datos in (("a.pdf", b"%PDF-1.4 contenido de prueba"), ("ñandú árbol.xlsx", b"PK\x03\x04..."), ("x/y\\z.csv", "col1;col2\n1;2\n".encode())):
    meta = documents.describe(datos, nombre, "application/octet-stream", version)
    casos["describe"].append({"b64": base64.b64encode(datos).decode(), "nombre": nombre, "version": version, "esperado": meta})
TEXTO_LARGO = ("Ítem 00100 Ascensor de pasajeros 630 kg x 2 unidades. Valor de venta 36,800.00 USD. " * 12)
for texto, loc in ((TEXTO_LARGO, {"pagina": 3, "origen": "pdf_texto"}), ("corto", {"hoja": "H", "fila": 2}), ("a" * 400, {"pagina": 1}), ("a" * 341, {"pagina": 1}), ("  ", {"pagina": 1})):
    casos["fragmentos"].append({"texto": texto, "ubicacion": loc, "documento": "doc-1", "serie": 4, "esperado": documents._fragment(texto, loc, "doc-1", 4)})
docs_tandas = [{"fragmentos": [{"id": f"f{i}", "documento_id": "d", "texto": "x" * n, "ubicacion": {}} for i, n in enumerate([100, 300, 250, 400, 50, 399, 10])], "consultas_rag": []}]
for maximo in (500, 1000, 24000):
    casos["tandas"].append({"documentos": docs_tandas, "maximo": maximo, "esperado": rag.context_batches(copy.deepcopy(docs_tandas), maximum=maximo)})


# ---- extracción de Excel y CSV -----------------------------------------------------------------------------------------
def zip_a_entradas(datos: bytes) -> dict:
    z = ZipFile(io.BytesIO(datos))
    return {n: base64.b64encode(z.read(n)).decode() for n in z.namelist() if not n.endswith("/")}


def libro_de_prueba() -> bytes:
    from datetime import datetime
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cotización"
    ws["A1"], ws["B1"], ws["C1"], ws["D1"] = "Descripción", "Cant.", "P. Unit. US$", "Parcial"
    ws["A2"], ws["B2"], ws["C2"] = "Ascensor 630 kg & más <especial>", 2, 36937.55
    ws["D2"] = "=B2*C2"
    ws["A3"], ws["B3"], ws["C3"] = "Instalación", 1, 1200
    ws["D3"] = "=B3*C3"
    ws["A5"], ws["B5"] = "Fecha", datetime(2026, 11, 5, 10, 30)
    ws["A6"], ws["B6"] = "IGV", 0.18
    ws["B6"].number_format = "0%"
    ws["C6"], ws["D6"] = True, "texto con  espacios"
    ws["B5"].number_format = "yyyy-mm-dd hh:mm"
    oculta = wb.create_sheet("Oculta")
    oculta["A1"], oculta["B1"] = "secreto", 99
    oculta.sheet_state = "hidden"
    wb.create_sheet("Vacía")
    buffer = io.BytesIO()
    wb.save(buffer)
    # openpyxl no calcula: se agrega el resultado guardado de D2 y se deja D3 sin resultado.
    original = ZipFile(io.BytesIO(buffer.getvalue()))
    salida = io.BytesIO()
    with ZipFile(salida, "w") as destino:
        for info in original.infolist():
            contenido = original.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                xml = contenido.decode("utf-8")
                xml = re.sub(r'(<c r="D2"[^>]*><f>B2\*C2</f>)<v\s*/>', r"\g<1><v>73875.1</v>", xml)
                xml = re.sub(r'(<c r="D2"[^>]*><f>B2\*C2</f>)<v></v>', r"\g<1><v>73875.1</v>", xml)
                contenido = xml.encode("utf-8")
            destino.writestr(info, contenido)
    return salida.getvalue()


def extraer(nombre, datos, mime):
    meta = documents.describe(datos, nombre, mime, version)
    try:
        r = documents.extract(datos, meta)
        esperado = {"resultado": r}
    except documents.DocumentError as e:
        esperado = {"error": str(e)}
    return {"nombre": nombre, "b64": base64.b64encode(datos).decode(), "mime": mime, "meta": meta, "esperado": esperado,
            "entradas": zip_a_entradas(datos) if nombre.endswith(".xlsx") else None}


libro = libro_de_prueba()
casos["extraccion"].append(extraer("cotizacion.xlsx", libro, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
casos["extraccion"].append(extraer("coma.csv", "Descripción,Cant,Precio\nAscensor,2,\"36,937.55\"\n\nSin cierre,\"con\nsalto\",3\n".encode("utf-8"), "text/csv"))
casos["extraccion"].append(extraer("punto_y_coma.csv", "Item;Cant;Precio\nA;2;36.937,55\nB;1;1.200,00\n".encode("utf-8-sig"), "text/csv"))
casos["extraccion"].append(extraer("latin.csv", "Ítem;Año\nÁrbol;2026\n".encode("cp1252"), "text/csv"))
casos["extraccion"].append(extraer("vacio.csv", b"\n\n", "text/csv"))
casos["esquema"] = contract.SCHEMA
casos["version"] = version
