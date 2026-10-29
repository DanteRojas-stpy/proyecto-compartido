import pytest

from app.etapa3 import contract
from test_contrato import sample


def test_confianza_ocr_no_puede_superar_la_fuente():
    data, source, context = sample()
    source['fragmentos'][0]['ubicacion']['confianza'] = .6
    result = contract.combine([data], [source], context, 'prueba')
    assert result['evidencias'][0]['confianza'] == .6


def test_unidad_normalizada_no_inventa_conversion():
    data, source, context = sample()
    data['items'][0]['unidad_normalizada'] = 'm2'
    result = contract.combine([data], [source], context, 'prueba')
    assert result['items'][0]['unidad_normalizada'] == 'unidad'
    assert result['items'][0]['cantidad'] == 2


def test_numero_tecnico_falso_no_se_guarda():
    data, source, context = sample()
    data['especificaciones_tecnicas'] = [{'documento_id': source['documento_id'], 'referencia_item': 'A',
        'campo': 'capacidad', 'valor_original': '100', 'valor_numerico': 200,
        'unidad_original': None, 'unidad_normalizada': None, 'evidencia_ids': ['e1']}]
    with pytest.raises(ValueError, match='especificación'):
        contract.combine([data], [source], context, 'prueba')


def test_moneda_ambigua_no_se_asume_usd():
    data, source, context = sample()
    # Un documento que solo escribe "$", sin nombrar la moneda en ninguna parte.
    source['fragmentos'][0]['texto'] = source['fragmentos'][0]['texto'].replace('USD ', '$ ') + ' $'
    data['evidencias'][0]['texto_fuente'] = source['fragmentos'][0]['texto']
    data['comerciales'][0]['originales']['moneda'] = '$'
    result = contract.combine([data], [source], context, 'prueba')
    assert result['datos_comerciales']['moneda'] is None
    assert any(o['tipo'] == 'moneda_ambigua' and o['requiere_aclaracion'] for o in result['observaciones'])
    assert result['datos_comerciales']['total'] == 236


def test_moneda_con_formato_invalido_no_descarta_la_lectura():
    data, source, context = sample()
    data['comerciales'][0]['valores']['moneda'] = 'Soles'
    data['comerciales'][0]['originales']['moneda'] = 'USD'
    result = contract.combine([data], [source], context, 'prueba')
    assert result['datos_comerciales']['moneda'] is None
    assert any(o['tipo'] == 'moneda_ambigua' for o in result['observaciones'])


def test_un_numero_no_puede_salir_de_recortar_otro():
    data, source, context = sample()
    source['fragmentos'][0]['texto'] = source['fragmentos'][0]['texto'].replace('precio USD 100 ', 'precio USD 1000 ')
    data['evidencias'][0]['texto_fuente'] = source['fragmentos'][0]['texto']
    with pytest.raises(ValueError, match='valor completo'):
        contract.combine([data], [source], context, 'prueba')
