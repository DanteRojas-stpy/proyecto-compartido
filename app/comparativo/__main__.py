"""Línea de comandos del generador del comparativo.

Ejemplo:
    python -m app.comparativo --plantilla plantilla.xlsx --salida comparativo.xlsx \
        --cotizacion "PROVEEDOR 2=cotizacion.xlsx" --tipo-cambio 3.6
"""

import argparse
import json
import sys

from .generar_comparativo import calcular_referencia, generar_comparativo, leer_filas


def _asignar(entradas: list[str]) -> dict:
    asignaciones = {}
    for entrada in entradas:
        bloque, _, resto = entrada.partition("=")
        ruta, _, indice = resto.partition("#")
        filas = leer_filas(ruta)
        asignaciones[bloque.strip()] = filas[int(indice or 0)]
    return asignaciones


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Llena la plantilla comparativa con las cotizaciones.")
    parser.add_argument("--plantilla", required=True)
    parser.add_argument("--salida", required=True)
    parser.add_argument("--cotizacion", action="append", default=[],
                        help="BLOQUE=ruta.xlsx[#indice de fila]. Puede repetirse.")
    parser.add_argument("--tipo-cambio", type=float, default=None)
    args = parser.parse_args(argv)

    asignaciones = _asignar(args.cotizacion)
    resultado = generar_comparativo(args.plantilla, asignaciones, args.salida, args.tipo_cambio)
    salida = {"escritos": resultado.escritos, "pendientes": resultado.pendientes}
    if args.tipo_cambio is not None:
        salida["referencia"] = calcular_referencia(args.plantilla, asignaciones, args.tipo_cambio)
    print(json.dumps(salida, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
