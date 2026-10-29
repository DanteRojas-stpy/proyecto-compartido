"""E5: llena una copia de la plantilla comparativa con la homologación de E4.

Determinista: no usa modelo. Escribe sobre el XML de la hoja para conservar formatos, comentarios y
formatos condicionales de la plantilla. Todos los números vienen de homologacion.json (que a su vez los copió de E3).
"""
from __future__ import annotations

import io
import re
from decimal import Decimal, InvalidOperation
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

HOJA = "xl/worksheets/sheet1.xml"
# (primera columna del bloque = nombre y texto, cantidad, P.U. US$, P.U. S/, parcial)
BLOQUES = [("H", "H", "I", "J", "K"), ("L", "L", "M", "N", "O"), ("P", "P", "Q", "R", "S"), ("T", "T", "U", "V", "W"),
           ("X", "X", "Y", "Z", "AA"), ("AB", "AB", "AC", "AD", "AE"), ("AF", "AF", "AG", "AH", "AI")]
FILA_PLAZO, FILA_PAGO, FILA_CONSIDERACIONES = 30, 33, 36
TOLERANCIA = Decimal("0.01")


class CuadroNoGenerable(ValueError):
    """La homologación no se puede volcar en esta plantilla (no es reintentable)."""


def dec(valor) -> Decimal | None:
    if valor is None or isinstance(valor, bool):
        return None
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        return None


def numero(valor: Decimal):
    return int(valor) if valor == valor.to_integral_value() else float(valor)


def plan(homologacion: dict, tipo_cambio: dict | None) -> dict:
    """Decide qué va en cada celda y las comprobaciones. No toca el archivo.

    La plantilla tiene una fila de partida (todos los equipos) y hasta 7 bloques de proveedor. Un proveedor que cotiza
    varios tipos (partidas de E4) ocupa un bloque por tipo: «PROVEEDOR (TIPO 1)», «PROVEEDOR (TIPO 2)».
    """
    partidas = homologacion["partidas"]
    if not partidas:
        raise CuadroNoGenerable("La homologación no tiene partidas que comparar.")
    postores = homologacion["postores"]
    if not postores:
        raise CuadroNoGenerable("No hay ofertas finales para comparar.")
    tc = None
    if tipo_cambio:
        tc = dec(tipo_cambio.get("valor"))
        if tc is None or tc <= 0:
            raise CuadroNoGenerable("El tipo de cambio no es un número positivo.")
    por_tipos = len(partidas) > 1
    avisos, informativos, comprobaciones = [], [], []
    celdas: dict[str, object] = {}
    metrado = dec(partidas[0]["metrado"]) if not por_tipos else None
    if por_tipos:
        celdas["I3"] = homologacion["especialidad"]["nombre"]  # el título dice COMPARATIVO - <especialidad>; B13 conserva el texto de la plantilla
    else:
        celdas["I3"] = partidas[0]["descripcion"]
        celdas["B13"], celdas["C13"] = partidas[0]["descripcion"], partidas[0]["unidad"]
        celdas["D13"] = numero(metrado) if metrado is not None else None
    celdas["E13"] = None  # el presupuesto meta no viene de E3
    if por_tipos:
        celdas["D13"] = None
    celdas["F5"] = numero(tc) if tc else 0

    bloques = []  # (postor, tipo, partida, items)
    for postor in sorted(postores, key=lambda p: p["nombre"]):
        cotizadas = []
        for numero_tipo, partida in enumerate(partidas, start=1):
            oferta = next((o for o in partida["ofertas"] if o["proveedor_id"] == postor["proveedor_id"]), None)
            if oferta and oferta["estado"] in ("cotizado", "global", "incluido_con_evidencia") and oferta["items"]:
                cotizadas.append((numero_tipo, partida, oferta["items"]))
        if not cotizadas:
            informativos.append(f"{postor['nombre']}: no cotiza ninguna partida; no ocupa un bloque.")
        for numero_tipo, partida, items in cotizadas:
            bloques.append((postor, numero_tipo if len(cotizadas) > 1 else None, numero_tipo, partida, items))
    if not bloques:
        raise CuadroNoGenerable("Ningún proveedor cotizó las partidas.")
    if len(bloques) > len(BLOQUES):
        raise CuadroNoGenerable(f"La plantilla tiene {len(BLOQUES)} bloques de proveedor y se necesitan {len(bloques)} "
                                "(un bloque por proveedor y tipo).")

    usa_dolares = False
    for (postor, etiqueta_tipo, numero_tipo, partida, items), (n, cant, usd, pen, _total) in zip(bloques, BLOQUES):
        celdas[f"{n}6"] = postor["nombre"] + (f" (TIPO {etiqueta_tipo})" if etiqueta_tipo else "")
        moneda = postor["moneda"]
        parciales = [dec(i["original"]["parcial"]) for i in items]
        cantidades = [dec(i["original"]["cantidad"]) for i in items]
        cantidad = sum(cantidades) if all(c is not None for c in cantidades) and sum(cantidades) > 0 else None
        if cantidad is None:
            cantidad = dec(partida["metrado"]) or Decimal(1)
            avisos.append(f"{postor['nombre']}: E3 no trae la cantidad; se usó {numero(cantidad)} (el metrado de la partida o 1).")
        unitario_item = dec(items[0]["original"]["precio_unitario"]) if len(items) == 1 else None
        if moneda not in ("PEN", "USD"):
            avisos.append(f"{postor['nombre']}: moneda {moneda or 'no identificada'}; la plantilla solo maneja PEN y USD, el bloque queda sin precios.")
            comprobaciones.append({"proveedor": postor["nombre"], "tipo": numero_tipo, "cuadra": False})
            celdas[f"{cant}13"], celdas[f"{usd}13"], celdas[f"{pen}13"] = numero(cantidad), 0, 0
            if por_tipos:
                celdas[f"{n}{FILA_CONSIDERACIONES}"] = f"Tipo {numero_tipo}: {partida['descripcion']}"
            continue
        if all(p is not None for p in parciales):
            suma = sum(parciales)
            unitario = suma / cantidad
        elif unitario_item is not None:
            unitario = unitario_item
            suma = unitario * cantidad
            avisos.append(f"{postor['nombre']}: el ítem no trae parcial; se usó precio unitario por cantidad.")
        else:
            avisos.append(f"{postor['nombre']}: faltan importes en la lectura de E3; el bloque queda sin precios (no se inventan).")
            comprobaciones.append({"proveedor": postor["nombre"], "tipo": numero_tipo, "cuadra": False})
            celdas[f"{cant}13"], celdas[f"{usd}13"], celdas[f"{pen}13"] = numero(cantidad), 0, 0
            texto = [f"Tipo {numero_tipo}: {partida['descripcion']}"] if por_tipos else []
            if texto:
                celdas[f"{n}{FILA_CONSIDERACIONES}"] = chr(10).join(texto)
            continue
        celdas[f"{cant}13"] = numero(cantidad)
        if moneda == "USD":
            usa_dolares = True
            celdas[f"{usd}13"] = numero(unitario)
            if not tc:
                avisos.append(f"{postor['nombre']} cotiza en US$ y falta el tipo de cambio: las columnas en S/ quedan sin valor.")
        else:
            celdas[f"{usd}13"], celdas[f"{pen}13"] = 0, numero(unitario)
        if len(items) > 1:
            avisos.append(f"{postor['nombre']}: {len(items)} ítems agrupados en la partida; el precio unitario es la suma de parciales entre la cantidad.")
        comprobaciones.append({"proveedor": postor["nombre"], "tipo": numero_tipo, "cantidad_por_unitario": float(cantidad * unitario),
                               "suma_parciales": float(suma), "cuadra": abs(cantidad * unitario - suma) <= TOLERANCIA})
        condiciones = postor["condiciones"]
        if condiciones["plazo_entrega"]:
            celdas[f"{n}{FILA_PLAZO}"] = str(condiciones["plazo_entrega"])
        if condiciones["condiciones_pago"]:
            celdas[f"{n}{FILA_PAGO}"] = str(condiciones["condiciones_pago"])
        texto = []
        if por_tipos:
            texto.append(f"Tipo {numero_tipo}: {partida['descripcion']}")
        if condiciones["vigencia_oferta"]:
            texto.append(f"Vigencia de la oferta: {condiciones['vigencia_oferta']}")
        if texto:
            celdas[f"{n}{FILA_CONSIDERACIONES}"] = "\n".join(texto)
    if usa_dolares and not tc:
        comprobaciones.append({"proveedor": None, "tipo_cambio_presente": False, "cuadra": False})
    # Un pendiente que solo pide autorizar el tipo de cambio queda resuelto si el especialista lo indicó al generar.
    bloqueantes = [p for p in homologacion["pendientes"] if p["bloquea_comparacion"] and not (tc and "tipo de cambio" in p["decision_requerida"])]
    if bloqueantes:
        avisos.append(f"La homologación tiene {len(bloqueantes)} pendientes que bloquean la comparación.")
    validado = all(c["cuadra"] for c in comprobaciones) and not avisos and not bloqueantes
    return {"celdas": celdas, "avisos": avisos, "informativos": informativos, "bloques": len(bloques), "comprobaciones": comprobaciones,
            "validado": validado, "pendientes_bloqueantes": len(bloqueantes), "tipo_cambio": tipo_cambio,
            "moneda_comparacion": homologacion["moneda_comparacion"]}


def _celda(xml: str, ref: str, valor) -> str:
    patron = re.compile(r'<c r="%s"((?:\s[^>]*?)?)(/>|>.*?</c>)' % ref, re.S)
    m = patron.search(xml)
    if not m:
        raise CuadroNoGenerable(f"La plantilla no tiene la celda {ref}; no es la plantilla esperada.")
    estilo = re.search(r'\ss="(\d+)"', m.group(1))
    s = f' s="{estilo.group(1)}"' if estilo else ""
    if valor is None:
        nuevo = f'<c r="{ref}"{s}/>'
    elif isinstance(valor, str):
        nuevo = f'<c r="{ref}"{s} t="inlineStr"><is><t xml:space="preserve">{escape(valor)}</t></is></c>'
    else:
        nuevo = f'<c r="{ref}"{s}><v>{valor}</v></c>'
    return xml[:m.start()] + nuevo + xml[m.end():]


def llenar(plantilla: bytes, cambios: dict[str, object]) -> bytes:
    """Devuelve el xlsx con las celdas escritas, sin valores calculados viejos y con recálculo al abrir."""
    entrada = ZipFile(io.BytesIO(plantilla))
    if HOJA not in entrada.namelist():
        raise CuadroNoGenerable("El archivo no parece la plantilla del cuadro comparativo.")
    salida = io.BytesIO()
    with ZipFile(salida, "w", ZIP_DEFLATED) as destino:
        for info in entrada.infolist():
            datos = entrada.read(info.filename)
            if info.filename == "xl/calcChain.xml":
                continue
            texto = None
            if info.filename == HOJA:
                texto = datos.decode("utf-8")
                for ref, valor in cambios.items():
                    texto = _celda(texto, ref, valor)
                texto = re.sub(r"(<f>[^<]*</f>)<v>[^<]*</v>", r"\1", texto)  # valores calculados viejos
                texto = re.sub(r'(<c r="[A-Z]+\d+"[^>]*?) t="str"(>\s*<f>)', r"\1\2", texto)
            elif info.filename == "xl/workbook.xml":
                texto = re.sub(r"<calcPr[^>]*/>", '<calcPr calcId="191028" fullCalcOnLoad="1"/>', datos.decode("utf-8"))
            elif info.filename == "[Content_Types].xml":
                texto = re.sub(r'<Override[^>]*calcChain[^>]*/>', "", datos.decode("utf-8"))
            elif info.filename == "xl/_rels/workbook.xml.rels":
                texto = re.sub(r'<Relationship [^>]*calcChain[^>]*/>', "", datos.decode("utf-8"))
            destino.writestr(info, texto.encode("utf-8") if texto is not None else datos)
    return salida.getvalue()


def generar(plantilla: bytes, homologacion: dict, tipo_cambio: dict | None) -> tuple[bytes, dict]:
    resultado = plan(homologacion, tipo_cambio)
    archivo = llenar(plantilla, resultado["celdas"])
    validacion = {k: v for k, v in resultado.items() if k != "celdas"}
    validacion["celdas_escritas"] = len(resultado["celdas"])
    return archivo, validacion
