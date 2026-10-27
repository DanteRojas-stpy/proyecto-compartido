import copy
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('configurar_nhost_e3', Path(__file__).resolve().parents[2] / 'scripts/configurar_etapa3_nhost.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_publicacion_preserva_otras_etapas_y_exige_revision_actual():
    other = {'table': {'schema': 'public', 'name': 'otra_etapa'}, 'select_permissions': [{'role': 'otro_rol', 'permission': {'columns': ['id'], 'filter': {}}}]}
    snapshot = {'resource_version': 17, 'metadata': {'version': 3, 'sources': [{'name': 'default', 'kind': 'postgres', 'configuration': {'connection_info': {'database_url': {'from_env': 'DATABASE_URL'}}}, 'tables': [other, {'table': {'schema': 'public', 'name': 'versiones_cotizacion'}}]}]}}
    original = copy.deepcopy(snapshot)
    request = module.replacement(snapshot)
    assert snapshot == original
    assert request['resource_version'] == 17
    assert request['args']['allow_inconsistent_metadata'] is False
    tables = request['args']['metadata']['sources'][0]['tables']
    assert next(t for t in tables if t['table']['name'] == 'otra_etapa') == other
    for t in tables:
        if t['table']['name'] in module.TABLES:
            permission = next(p for p in t['select_permissions'] if p['role'] == 'user')['permission']
            assert 'X-Hasura-User-Id' in str(permission['filter'])
            assert 'insert_permissions' not in t and 'update_permissions' not in t
    assert not any(t['table']['name'] in {'e3_configuracion', 'e3_eventos'} for t in tables)


def test_no_publica_si_no_puede_controlar_cambios_concurrentes():
    with pytest.raises(ValueError, match='revisión'):
        module.replacement({'metadata': {'sources': []}})
