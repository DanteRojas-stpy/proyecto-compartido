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
    for nombre in ('017_homologacion_cuadro.sql', '018_tipo_cambio_cuadro.sql'):
        sql((ROOT / 'db/etapa4' / nombre).read_text(encoding='utf-8'))
    salida = sql((ROOT / 'tests/etapa4/integracion_e4.sql').read_text(encoding='utf-8'))
    lineas = salida.splitlines()
    assert len(lineas) == 12, salida
    assert all(linea.endswith('|true') for linea in lineas), salida


def test_la_migracion_esta_en_el_orden_documentado():
    numeros = [int(p.name.split('_', 1)[0]) for p in migraciones()]
    assert numeros == list(range(1, len(numeros) + 1))
    guia = (ROOT / 'db/ORDEN_MIGRACIONES.md').read_text(encoding='utf-8')
    assert '[017_homologacion_cuadro.sql](etapa4/017_homologacion_cuadro.sql)' in guia
    assert '[018_tipo_cambio_cuadro.sql](etapa4/018_tipo_cambio_cuadro.sql)' in guia


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


def test_pantalla_de_e4_con_el_resultado_real_del_constructor():
    """La lógica del front se prueba con Node y con lo que de verdad produce el constructor de E4."""
    import json
    import sys
    sys.path.insert(0, str(ROOT / 'tests/etapa4'))
    from app.homologacion import entrada
    from app.homologacion.construir import build
    from datos_ficticios import paquete, respuesta_modelo
    preparado = entrada.prepare(paquete())
    homologacion = build(preparado, respuesta_modelo(preparado), 'claude-sonnet-5-5')
    node = shutil.which('node')
    if not node:
        pytest.skip('La prueba de la pantalla requiere Node.js.')
    version = subprocess.check_output([node, '--version'], text=True).strip().lstrip('v')
    mayor, menor, *_ = map(int, version.split('.'))
    if (mayor, menor) < (22, 7):
        pytest.skip('Se necesita Node.js 22.7 o posterior para leer módulos ES sin package.json.')
    r = subprocess.run([node, '--test', str(ROOT / 'tests/etapa4/front_e4.test.mjs')], capture_output=True, text=True, encoding='utf-8',
                       timeout=60, env={**__import__('os').environ, 'HOMOLOGACION_JSON': json.dumps(homologacion)})
    assert r.returncode == 0, r.stdout + r.stderr


def test_el_front_conecta_el_boton_con_la_function_y_no_usa_html_sin_escapar():
    app = (ROOT / 'frontend/js/app.js').read_text(encoding='utf-8')
    assert 'from "./e4.js"' in app
    assert '"e4-operar", "solicitar_e4"' in app
    assert 'e4_estado_solicitud(' in app and 'e4_homologaciones(' in app
    bloque = app[app.index('// ---- E4: homologación'):app.index('async function cargarDetalleProyecto()')]
    assert 'innerHTML' not in bloque, 'los textos de proveedores y pendientes se muestran con textContent'
    assert 'estadosE4.get(solicitud.id)' in app
    modulo = (ROOT / 'frontend/js/e4.js').read_text(encoding='utf-8')
    assert 'document.' not in modulo and 'window.' not in modulo, 'e4.js no toca el DOM'
