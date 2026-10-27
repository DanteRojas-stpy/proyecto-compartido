"""Evita publicar un flujo que no incluya las reglas actuales de identificación."""

import json
from pathlib import Path
import runpy


def test_flujo_exportado_coincide_con_sus_reglas():
    root = Path(__file__).resolve().parents[1]
    generador = runpy.run_path(str(root / 'scripts/generar_flujo_recepcion.py'))
    flujo = json.loads((root / 'n8n/flujos/detectar-respuestas-proveedores.json').read_text(encoding='utf-8'))
    assert flujo == generador['generar']()
    nombres = {nodo['name'] for nodo in flujo['nodes']}
    for origen, salidas in flujo['connections'].items():
        assert origen in nombres
        for rama in salidas['main']:
            assert all(destino['node'] in nombres for destino in rama)
