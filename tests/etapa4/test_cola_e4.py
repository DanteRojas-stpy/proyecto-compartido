"""Cola, resultados y permisos de E4/E5 contra un PostgreSQL aislado (misma base que usan las demás etapas)."""
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import instalar, migraciones

ROOT = Path(__file__).resolve().parents[2]


def test_e4_e5_operaciones_permisos_y_cola(postgres):
    sql = postgres
    instalar(sql)
    # La migración se puede repetir sin cambiar nada.
    sql((ROOT / 'db/etapa4/017_homologacion_cuadro.sql').read_text(encoding='utf-8'))
    salida = sql((ROOT / 'tests/etapa4/integracion_e4.sql').read_text(encoding='utf-8'))
    lineas = salida.splitlines()
    assert len(lineas) == 11, salida
    assert all(linea.endswith('|true') for linea in lineas), salida


def test_la_migracion_esta_en_el_orden_documentado():
    numeros = [int(p.name.split('_', 1)[0]) for p in migraciones()]
    assert numeros == list(range(1, len(numeros) + 1))
    guia = (ROOT / 'db/ORDEN_MIGRACIONES.md').read_text(encoding='utf-8')
    assert '[017_homologacion_cuadro.sql](etapa4/017_homologacion_cuadro.sql)' in guia


def test_function_e4_operar_con_node():
    node = shutil.which('node')
    if not node:
        pytest.skip('Las pruebas ejecutables de la Function requieren Node.js 22.6 o posterior.')
    version = subprocess.check_output([node, '--version'], text=True).strip().lstrip('v')
    mayor, menor, *_ = map(int, version.split('.'))
    if (mayor, menor) < (22, 6):
        pytest.skip('El Node.js instalado no admite TypeScript; usa Node.js 24 para la Function.')
    r = subprocess.run([node, '--experimental-strip-types', '--test', str(ROOT / 'tests/etapa4/e4_function.test.mjs')],
                       capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr


def test_permisos_de_hasura_solo_lectura_sin_datos_internos():
    import importlib.util
    spec = importlib.util.spec_from_file_location('configurar_etapa4', ROOT / 'scripts/configurar_etapa4_nhost.py')
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    base = {'resource_version': 7, 'metadata': {'version': 3, 'sources': [{'name': 'default', 'kind': 'postgres', 'tables': [
        {'table': {'schema': 'public', 'name': 'solicitudes_cotizacion'}},
        {'table': {'schema': 'public', 'name': 'e3_resultados'},
         'select_permissions': [{'role': 'user', 'permission': {'columns': ['version_id'], 'filter': {}}}]}]}]}}
    cambio = modulo.replacement(base)
    tablas = {t['table']['name']: t for t in cambio['args']['metadata']['sources'][0]['tables']}
    assert {'e4_estado_solicitud', 'e4_homologaciones', 'e5_cuadros'} <= set(tablas)
    assert tablas['e3_resultados']['select_permissions'][0]['permission']['columns'] == ['version_id']
    for nombre in ('e4_estado_solicitud', 'e4_homologaciones', 'e5_cuadros'):
        permisos = tablas[nombre]['select_permissions']
        assert [p['role'] for p in permisos] == ['user']
        assert not {'token', 'lease_hasta', 'intentos', 'error', 'solicitado_por'} & set(permisos[0]['permission']['columns'])
        assert 'insert_permissions' not in tablas[nombre] and 'update_permissions' not in tablas[nombre]
