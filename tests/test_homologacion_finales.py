import json
from pathlib import Path
import runpy
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_guardas_de_finales_y_evidencia():
    subprocess.run(['node', '--test', 'tests/test_homologacion_finales.cjs'], cwd=ROOT, check=True)


def test_exportacion_homologacion_sin_mutaciones_y_con_lector_incluido():
    modulo = runpy.run_path(str(ROOT / 'scripts/generar_flujo_homologacion.py'))
    guardado = json.loads((ROOT / 'n8n/flujos/e4-homologar-cotizaciones-finales.json').read_text(encoding='utf-8'))
    assert guardado == modulo['generar']()
    workflows = [guardado]
    for w in workflows:
        nombres = {n['name'] for n in w['nodes']}
        for origen, salidas in w['connections'].items():
            assert origen in nombres
            for ramas in salidas.values():
                for rama in ramas:
                    assert all(c['node'] in nombres for c in rama)
        for n in w['nodes']:
            assert 'credentials' not in n
            if n['type'] == 'n8n-nodes-base.executeWorkflow':
                workflows.append(json.loads(n['parameters']['workflowJson']))
            if n['type'] == 'n8n-nodes-base.httpRequest':
                assert 'mutation ' not in n['parameters'].get('jsonBody', '')
            assert n['type'] not in ('n8n-nodes-base.gmail', 'n8n-nodes-base.gmailTrigger')
