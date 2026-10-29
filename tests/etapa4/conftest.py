"""Contenedor PostgreSQL aislado y lista de migraciones, compartidos por las pruebas de E4 y E5."""
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def migraciones():
    archivos = [*ROOT.glob('db/migraciones/*.sql'), *ROOT.glob('db/etapa3/*.sql'), *ROOT.glob('db/etapa4/*.sql')]
    return sorted(archivos, key=lambda p: int(p.name.split('_', 1)[0]))


@pytest.fixture
def postgres():
    imagen = os.environ.get('COSTFLOW_TEST_POSTGRES_IMAGE')
    if not imagen:
        pytest.skip('Definir COSTFLOW_TEST_POSTGRES_IMAGE para probar PostgreSQL aislado.')
    if not shutil.which('docker'):
        pytest.fail('Se solicitó la prueba PostgreSQL, pero Docker no está disponible.')
    nombre = 'costflow-e4-' + uuid.uuid4().hex[:12]
    subprocess.run(['docker', 'run', '--rm', '-d', '--name', nombre, '--network', 'none', '--tmpfs', '/var/lib/postgresql:rw',
                    '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', imagen], check=True, capture_output=True, timeout=120)
    try:
        for _ in range(90):
            if subprocess.run(['docker', 'exec', nombre, 'pg_isready', '-q', '-U', 'postgres'], capture_output=True, timeout=5).returncode == 0:
                break
            time.sleep(0.5)
        else:
            pytest.fail('PostgreSQL de prueba no inició a tiempo.')

        def sql(texto):
            r = subprocess.run(['docker', 'exec', '-i', nombre, 'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', 'postgres'],
                               input=texto, capture_output=True, text=True, encoding='utf-8', timeout=120)
            assert r.returncode == 0, r.stderr
            return r.stdout.strip()
        yield sql
    finally:
        subprocess.run(['docker', 'rm', '-f', nombre], capture_output=True, timeout=20)


def instalar(sql):
    """Esquema mínimo de Nhost y todas las migraciones, en orden."""
    sql('CREATE SCHEMA auth; CREATE TABLE auth.users (id uuid PRIMARY KEY);')
    for ruta in migraciones():
        sql(ruta.read_text(encoding='utf-8'))
