"""Genera el cuadro comparativo en la plantilla Excel del usuario (proceso 9).

Entrada: datos homologados (ver app/modelo.py) y la plantilla en plantillas/.
Salida: un .xlsx nuevo, con las fórmulas y el formato de la plantilla conservados.

Implementación para la plantilla compartida de ascensores: app/comparativo/plantilla.py.
Requiere homologaciones validadas y el motor de cálculo configurado.
"""


def generar_comparativo(datos_homologados, plantilla, salida, **opciones):
    from .plantilla import generar
    return generar(datos_homologados, plantilla, salida, **opciones)
