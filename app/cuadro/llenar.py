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
    """Decide qué va en cada celda y las comprobaciones. No toca el archivo."""
    partidas = homologacion["partidas"]
    if len(partidas) != 1:
        raise CuadroNoGenerable(f"La plantilla tiene una sola fila de partida y la homologación tiene {len(partidas)}. "
                                "Hace falta una plantilla con más filas.")
    partida = partidas[0]
    postores = {p["proveedor_id"]: p for p in homologacion["postores"]}
    if not postores:
        raise CuadroNoGenerable("No hay ofertas finales para comparar.")
    if len(postores) > len(BLOQUES):
        raise CuadroNoGenerable(f"La plantilla admite {len(BLOQUES)} proveedores y hay {len(postores)}.")
    tc = None
    if tipo_cambio:
        tc = dec(tipo_cambio.get("valor"))
        if tc is None or tc <= 0:
            raise CuadroNoGenerable("El tipo de cambio no es un número positivo.")
    avisos, comprobaciones = [], []
    celdas: dict[str, object] = {}
    metrado = dec(partida["metrado"])
    celdas["I3"] = partida["descripcion"]
    celdas["B13"], celdas["C13"] = partida["descripcion"], partida["unidad"]
    celdas["D13"], celdas["E13"] = (numero(metrado) if metrado is not None else None), None  # el presupuesto meta no viene de E3
    celdas["F5"] = numero(tc) if tc else 0
    ofertas = {o["proveedor_id"]: o for o in partida["ofertas"]}
    usa_dolares = False
    for indice, (proveedor_id, postor) in enumerate(sorted(postores.items(), key=lambda kv: kv[1]["nombre"])):
        n, cant, usd, pen, _total = BLOQUES[indice]
        celdas[f"{n}6"] = postor["nombre"]
        oferta = ofertas.get(proveedor_id)
        items = oferta["items"] if oferta and oferta["estado"] in ("cotizado", "global", "incluido_con_evidencia") else []
        if not items:
            avisos.append(f"{postor['nombre']}: no cotiza la partida (estado {oferta['estado'] if oferta else 'sin oferta'}).")
            celdas[f"{cant}13"], celdas[f"{usd}13"], celdas[f"{pen}13"] = 0, 0, 0
        else:
            parciales = [dec(i["original"]["parcial"]) for i in items]
            if any(p is None for p in parciales):
                raise CuadroNoGenerable(f"{postor['nombre']}: un ítem no tiene parcial; no se inventa el importe.")
            suma = sum(parciales)
            cantidad = dec(items[0]["original"]["cantidad"]) if len(items) == 1 else None
            if cantidad is None:
                cantidad = metrado if metrado else Decimal(1)
            unitario = suma / cantidad
            moneda = postor["moneda"]
            if moneda not in ("PEN", "USD"):
                raise CuadroNoGenerable(f"{postor['nombre']}: moneda {moneda or 'desconocida'}; la plantilla solo maneja PEN y USD.")
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
            comprobaciones.append({"proveedor": postor["nombre"], "cantidad_por_unitario": float(cantidad * unitario), "suma_parciales": float(suma),
                                   "cuadra": abs(cantidad * unitario - suma) <= TOLERANCIA})
        condiciones = postor["condiciones"]
        if condiciones["plazo_entrega"]:
            celdas[f"{n}{FILA_PLAZO}"] = str(condiciones["plazo_entrega"])
        if condiciones["condiciones_pago"]:
            celdas[f"{n}{FILA_PAGO}"] = str(condiciones["condiciones_pago"])
        if condiciones["vigencia_oferta"]:
            celdas[f"{n}{FILA_CONSIDERACIONES}"] = f"Vigencia de la oferta: {condiciones['vigencia_oferta']}"
    if usa_dolares and not tc:
        comprobaciones.append({"proveedor": None, "tipo_cambio_presente": False, "cuadra": False})
    # Un pendiente que solo pide autorizar el tipo de cambio queda resuelto si el especialista lo indicó al generar.
    bloqueantes = [p for p in homologacion["pendientes"] if p["bloquea_comparacion"] and not (tc and "tipo de cambio" in p["decision_requerida"])]
    if bloqueantes:
        avisos.append(f"La homologación tiene {len(bloqueantes)} pendientes que bloquean la comparación.")
    validado = all(c["cuadra"] for c in comprobaciones) and not avisos and not bloqueantes
    return {"celdas": celdas, "avisos": avisos, "comprobaciones": comprobaciones, "validado": validado,
            "pendientes_bloqueantes": len(bloqueantes), "tipo_cambio": tipo_cambio, "moneda_comparacion": homologacion["moneda_comparacion"]}


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
