"""Llena la plantilla comparativa con las cotizaciones de cada proveedor (proceso 9).

La plantilla del usuario ya trae el presupuesto meta (metrado y costo unitario)
y las fórmulas de conversión, parcial y totales. Este módulo solo escribe las
celdas de entrada de cada proveedor: cantidad y precio en dólares. Las fórmulas
de soles y parciales se conservan.

Una cotización en soles no se escribe en la columna de dólares, porque cambiaría
la lógica de la plantilla. Se informa como pendiente para que el especialista la
revise.
"""

from dataclasses import dataclass, field

import openpyxl
from openpyxl.utils import column_index_from_string

HOJA_PLANTILLA = "PLANTILLA"
CELDA_TIPO_CAMBIO = "F5"
FILA_PARTIDA = 13
CELDA_METRADO = "D13"
CELDA_COSTO_UNITARIO = "E13"
CELDA_PARCIAL_META = "F13"

# Primera columna de cada bloque de proveedor en la hoja PLANTILLA.
# Cada bloque ocupa cuatro columnas: Cant., P.Unitario (US$), P.Unitario (S/), P.Parcial (S/).
BLOQUES_PROVEEDOR = {
    "PROVEEDOR 1": "H",
    "PROVEEDOR 2": "L",
    "PROVEEDOR 3 (TIPO 1)": "P",
    "PROVEEDOR 3 (TIPO 2)": "T",
    "PROVEEDOR 4": "X",
    "PROVEEDOR 5 (TIPO 1)": "AB",
    "PROVEEDOR 5 (TIPO 2)": "AF",
}


@dataclass
class Cotizacion:
    """Una fila de precio extraída de una cotización."""

    proveedor: str
    moneda: str
    precio_unitario: float | None
    cantidad: float | None
    descripcion: str = ""
    observaciones: str = ""


@dataclass
class Resultado:
    """Qué quedó escrito y qué quedó pendiente, por proveedor."""

    escritos: list[dict] = field(default_factory=list)
    pendientes: list[dict] = field(default_factory=list)


def _numero(valor) -> float | None:
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def leer_filas(ruta: str, hoja: str = "Datos cotizacion") -> list[Cotizacion]:
    """Lee las filas de precio de una cotización extraída (hoja 'Datos cotizacion')."""
    ws = openpyxl.load_workbook(ruta, data_only=True, read_only=True)[hoja]
    filas = list(ws.iter_rows(values_only=True))
    if not filas:
        return []
    encabezado = filas[0]
    indice = {str(nombre): i for i, nombre in enumerate(encabezado) if nombre is not None}

    def celda(fila, nombre):
        i = indice.get(nombre)
        return None if i is None else fila[i]

    resultado = []
    for fila in filas[1:]:
        proveedor = celda(fila, "Proveedor")
        if not proveedor:
            continue
        resultado.append(
            Cotizacion(
                proveedor=str(proveedor).strip(),
                moneda=str(celda(fila, "Moneda") or "").strip().upper(),
                precio_unitario=_numero(celda(fila, "Precio_unitario")),
                cantidad=_numero(celda(fila, "Cantidad")),
                descripcion=str(celda(fila, "Descripcion") or ""),
                observaciones=str(celda(fila, "Observaciones") or ""),
            )
        )
    return resultado


def generar_comparativo(plantilla: str, asignaciones: dict[str, Cotizacion], salida: str,
                        tipo_cambio: float | None = None) -> Resultado:
    """Escribe cada cotización en su bloque de proveedor y guarda una copia.

    asignaciones: nombre del bloque (por ejemplo 'PROVEEDOR 2') -> Cotizacion.
    tipo_cambio: se escribe en F5 solo si el especialista lo aprobó; si es None,
    la celda queda como está y el resultado lo indica.
    """
    for bloque in asignaciones:
        if bloque not in BLOQUES_PROVEEDOR:
            raise ValueError(f"Bloque de proveedor desconocido: {bloque}")

    libro = openpyxl.load_workbook(plantilla)
    hoja = libro[HOJA_PLANTILLA]
    resultado = Resultado()

    if tipo_cambio is not None:
        hoja[CELDA_TIPO_CAMBIO] = float(tipo_cambio)

    for bloque, cot in asignaciones.items():
        col_cant = column_index_from_string(BLOQUES_PROVEEDOR[bloque])
        col_usd = col_cant + 1
        registro = {"bloque": bloque, "proveedor": cot.proveedor,
                    "moneda": cot.moneda, "precio_original": cot.precio_unitario,
                    "cantidad": cot.cantidad}

        if cot.moneda != "USD":
            registro["motivo"] = "La cotización no está en dólares. Requiere revisión de moneda."
            resultado.pendientes.append(registro)
            continue
        if cot.precio_unitario is None:
            registro["motivo"] = "Sin precio unitario."
            resultado.pendientes.append(registro)
            continue

        hoja.cell(row=FILA_PARTIDA, column=col_usd).value = cot.precio_unitario
        if cot.cantidad is not None:
            hoja.cell(row=FILA_PARTIDA, column=col_cant).value = cot.cantidad
        else:
            registro["motivo"] = "Cantidad vacía: se escribió el precio sin cantidad."
            resultado.pendientes.append(registro)
            resultado.escritos.append(registro)
            continue
        resultado.escritos.append(registro)

    if tipo_cambio is None:
        resultado.pendientes.append({"motivo": "Tipo de cambio no aprobado: las columnas en soles quedan sin calcular."})

    libro.save(salida)
    return resultado


def calcular_referencia(plantilla: str, cotizaciones: dict[str, Cotizacion], tipo_cambio: float) -> list[dict]:
    """Calcula en Python la misma comparación que hace la plantilla, para revisar sin abrir Excel."""
    libro = openpyxl.load_workbook(plantilla, data_only=False)
    base_metrado = _numero(libro[HOJA_PLANTILLA][CELDA_METRADO].value)
    base_costo = _numero(libro[HOJA_PLANTILLA][CELDA_COSTO_UNITARIO].value)
    base_parcial = base_metrado * base_costo if base_metrado and base_costo else None

    filas = []
    for bloque, cot in cotizaciones.items():
        if cot.moneda != "USD" or cot.precio_unitario is None:
            filas.append({"bloque": bloque, "estado": "pendiente"})
            continue
        unitario_s = cot.precio_unitario * tipo_cambio
        parcial_s = unitario_s * (cot.cantidad or 0)
        filas.append({
            "bloque": bloque,
            "precio_unitario_s": round(unitario_s, 2),
            "parcial_s": round(parcial_s, 2),
            "desviacion_vs_base_pct": round((parcial_s - base_parcial) / base_parcial * 100, 2) if base_parcial else None,
            "estado": "comparable" if cot.cantidad else "cantidad_vacia",
        })
    return filas
