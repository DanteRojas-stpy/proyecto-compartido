"""Prueba una instalación vacía, aislada del Nhost del equipo.

Para ejecutar la prueba PostgreSQL: definir COSTFLOW_TEST_POSTGRES_IMAGE=postgres:18.
El contenedor no publica puertos, no tiene red y solo guarda datos ficticios.
"""
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def migrations():
    return sorted([*ROOT.glob('db/migraciones/*.sql'), *ROOT.glob('db/etapa3/*.sql'), *ROOT.glob('db/etapa4/*.sql')],
                  key=lambda p: int(p.name.split('_', 1)[0]))


def test_orden_documentado_completo_y_sin_numeros_repetidos():
    files = migrations()
    numbers = [int(p.name.split('_', 1)[0]) for p in files]
    assert numbers == list(range(1, len(files) + 1))
    guide = ROOT / 'db/ORDEN_MIGRACIONES.md'
    links = re.findall(r'\]\(([^)]+\.sql)\)', guide.read_text(encoding='utf-8'))
    assert [(guide.parent / link).resolve() for link in links] == files


@pytest.fixture
def postgres():
    image = os.environ.get('COSTFLOW_TEST_POSTGRES_IMAGE')
    if not image:
        pytest.skip('Definir COSTFLOW_TEST_POSTGRES_IMAGE para probar PostgreSQL aislado.')
    if not shutil.which('docker'):
        pytest.fail('Se solicitó la prueba PostgreSQL, pero Docker no está disponible.')
    name = 'costflow-e3-migraciones-' + uuid.uuid4().hex[:12]
    subprocess.run(['docker', 'run', '--rm', '-d', '--name', name, '--network', 'none',
                    '--tmpfs', '/var/lib/postgresql:rw',
                    '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', image],
                   check=True, capture_output=True, timeout=120)
    try:
        for _ in range(90):
            ready = subprocess.run(['docker', 'exec', name, 'pg_isready', '-q', '-U', 'postgres'],
                                   capture_output=True, timeout=5)
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            pytest.fail('PostgreSQL de prueba no inició a tiempo.')

        def sql(text):
            result = subprocess.run(['docker', 'exec', '-i', name, 'psql', '-X', '-qAt',
                                     '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', 'postgres'],
                                    input=text, capture_output=True, text=True,
                                    encoding='utf-8', timeout=60)
            assert result.returncode == 0, result.stderr
            return result.stdout.strip()
        yield sql
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=20)


def test_instalacion_vacia_y_base_repetible_sin_cambiar_datos(postgres):
    sql = postgres
    # Nhost crea auth.users por su cuenta; esta tabla mínima es solo del contenedor.
    sql('CREATE SCHEMA auth; CREATE TABLE auth.users (id uuid PRIMARY KEY);')
    files = migrations()
    for path in files:
        if path.name.startswith('011_'):
            assert sql("SELECT to_regclass('public.versiones_cotizacion') IS NULL;") == 't'
        sql(path.read_text(encoding='utf-8'))

    assert sql("SELECT modelo||':'||recepcion_habilitada||':'||lector_habilitado "
               "FROM public.e3_configuracion;") == 'claude-opus-5-5:false:false'
    assert sql("SELECT to_regprocedure('public.e3_operar(text,jsonb)') IS NOT NULL "
               "AND to_regclass('public.e3_finales_e4') IS NOT NULL;") == 't'
    sql("""
    INSERT INTO auth.users VALUES ('10000000-0000-0000-0000-000000000001');
    INSERT INTO public.proyectos(id,responsable_id,codigo,nombre)
    VALUES ('20000000-0000-0000-0000-000000000001',
            '10000000-0000-0000-0000-000000000001','PRUEBA','Proyecto ficticio');
    INSERT INTO public.solicitudes_cotizacion(id,proyecto_id,creado_por,nombre,
           moneda,vigencia_dias,fecha_limite,tipo)
    VALUES ('30000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001',
            '10000000-0000-0000-0000-000000000001','Solicitud ficticia','PEN',30,
            current_date+30,'MA');
    INSERT INTO public.proveedores(id,creado_por,nombre)
    VALUES ('40000000-0000-0000-0000-000000000001',
            '10000000-0000-0000-0000-000000000001','Proveedor ficticio');
    INSERT INTO public.solicitud_proveedores(solicitud_id,proveedor_id)
    VALUES ('30000000-0000-0000-0000-000000000001','40000000-0000-0000-0000-000000000001');
    INSERT INTO public.correos_proveedor(id,solicitud_id,proveedor_id,gmail_message_id,
           remitente,recibido_at,estado_correo)
    VALUES ('60000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000001',
            '40000000-0000-0000-0000-000000000001','mensaje-ficticio',
            'proveedor@example.invalid',now(),'respuesta_sin_nueva_cotizacion_ni_ficha_tecnica');
    INSERT INTO public.versiones_cotizacion(id,solicitud_id,proveedor_id,version,origen,correo_id)
    VALUES ('50000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000001',
            '40000000-0000-0000-0000-000000000001',1,'manual','60000000-0000-0000-0000-000000000001');
    INSERT INTO public.documentos(solicitud_id,tipo,nombre_original,storage_file_id,
           subido_por,proveedor_id,version_id,correo_id)
    SELECT '30000000-0000-0000-0000-000000000001','cotizacion_proveedor',nombre,
           gen_random_uuid(),'10000000-0000-0000-0000-000000000001',
           '40000000-0000-0000-0000-000000000001','50000000-0000-0000-0000-000000000001',
           '60000000-0000-0000-0000-000000000001'
    FROM (VALUES ('Primero ficticio.pdf'),('Segundo ficticio.pdf')) AS d(nombre);
    """)
    snapshot = """SELECT jsonb_build_object(
      'versiones',(SELECT jsonb_agg(to_jsonb(v) ORDER BY id) FROM public.versiones_cotizacion v),
      'documentos',(SELECT jsonb_agg(to_jsonb(d) ORDER BY id) FROM public.documentos d),
      'columnas',(SELECT jsonb_agg(jsonb_build_array(attname,format_type(atttypid,atttypmod),attnotnull)
                  ORDER BY attnum) FROM pg_attribute WHERE attrelid='public.versiones_cotizacion'::regclass
                  AND attnum>0 AND NOT attisdropped),
      'reglas',(SELECT jsonb_agg(pg_get_constraintdef(oid) ORDER BY conname) FROM pg_constraint
                WHERE conrelid IN ('public.versiones_cotizacion'::regclass,'public.documentos'::regclass)),
      'indices',(SELECT jsonb_agg(indexdef ORDER BY indexname) FROM pg_indexes
                  WHERE schemaname='public' AND tablename IN ('versiones_cotizacion','documentos')),
      'triggers',(SELECT jsonb_agg(pg_get_triggerdef(oid) ORDER BY tgname) FROM pg_trigger
                  WHERE tgrelid='public.versiones_cotizacion'::regclass AND NOT tgisinternal)
    );"""
    before = json.loads(sql(snapshot))
    base = ROOT / 'db/migraciones/011_base_versiones_cotizacion.sql'
    sql(base.read_text(encoding='utf-8'))
    sql(base.read_text(encoding='utf-8'))
    assert json.loads(sql(snapshot)) == before
    assert len(before['documentos']) == 2
    # Las operaciones y decisiones de E3 también deben funcionar con la base recién creada.
    result = sql((ROOT / 'tests/etapa3/integracion.sql').read_text(encoding='utf-8'))
    assert len(result.splitlines()) == 13
    assert all(line.endswith('|t') for line in result.splitlines())
    assert json.loads(sql(snapshot)) == before
