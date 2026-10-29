"""Los importes de las fichas reales de TK, Schindler y Powertech deben leerse completos.

Los textos son los que traen los PDF y los originales son los que devolvió el modelo, con etiquetas incluidas.
"""
from decimal import Decimal

import pytest

from app.etapa3 import contract
from test_contrato import sample


def armar(texto, valores, originales, items=()):
    data, source, context = sample()
    doc = source['documento_id']
    source['fragmentos'][0]['texto'] = texto
    data['evidencias'][0]['texto_fuente'] = texto
    base = {'moneda': None, 'subtotal': None, 'impuestos': None, 'total': None,
            'plazo_entrega': None, 'condiciones_pago': None, 'vigencia_oferta': None}
    data['comerciales'][0]['valores'] = {**base, **valores}
    data['comerciales'][0]['originales'] = {**base, **originales}
    data['items'] = []
    for item in items:
        completo = {'referencia_item': None, 'descripcion': None, 'cantidad': None, 'unidad': None, 'unidad_normalizada': None,
                    'precio_unitario': None, 'parcial': None, **item['valores']}
        originales = {'descripcion': None, 'cantidad': None, 'unidad': None, 'precio_unitario': None, 'parcial': None, **item['originales']}
        data['items'].append({'documento_id': doc, **completo, 'originales': originales, 'evidencia_ids': ['e1']})
    return data, source, context


def tipos(resultado):
    return {o['tipo'] for o in resultado['observaciones']}


@pytest.mark.parametrize('original, esperado, convencion', [
    ('Valor total de venta (sin I.G.V): 73,600.00 USD', '73600.00', None),
    ('I.G.V. 18%: 13,248.00 USD', '13248.00', None),
    ('TOTAL:\n86,848.00 USD', '86848.00', None),
    ('+1 x', '1', None),
    ('Cantidad 2', '2', None),
    ('I.G.V $\n13,604.40', '13604.40', None),
    ('Costo total US$ 73.875,10', '73875.10', None),
    ('I.G.V. 18% US$ 13.297,52', '13297.52', None),
    ('US$ 36.937,55', '36937.55', None),
    ('36,800', '36800', 'us'),
    ('36.937', '36937', 'eu'),
    ('1,250,000', '1250000', 'us'),
])
def test_cifras_con_etiqueta_y_ambos_formatos_se_leen(original, esperado, convencion):
    assert contract.number(original, convencion) == Decimal(esperado)


@pytest.mark.parametrize('original, convencion', [
    ('36,800', None),          # sin la convención del documento, 36,800 puede ser 36.8
    ('36.937', None),
    ('36,800', 'eu'),          # en un documento europeo la coma es decimal
    ('2 x 3', None),           # dos cifras: no se elige una
    ('I.G.V.', None),
    ('1,25,000', 'us'),
])
def test_cifras_ambiguas_siguen_sin_leerse(original, convencion):
    assert contract.number(original, convencion) is None


def test_convencion_del_documento():
    assert contract.detect_convention(['Subtotal 73,600.00 USD, IGV 13,248.00 USD']) == 'us'
    assert contract.detect_convention(['Valor 73.875,10 e IGV 13.297,52']) == 'eu'
    assert contract.detect_convention(['36,800 sin decimales']) is None
    assert contract.detect_convention(['1,234.50 y 1.234,50']) is None


def test_schindler_importes_cantidad_y_items_duplicados():
    texto = ('Ítem 00100 - Schindler 3000 - 630 kg, 17 parada, 1.75 m/s - Edificio. Valor de venta (sin I.G.V.): +1 x 36,800 = 36,800.00 USD\n'
             'Ítem 00200 - Schindler 3000 - 630 kg, 17 parada, 1.75 m/s - Edificio. Valor de venta (sin I.G.V.): +1 x 36,800 = 36,800.00 USD\n'
             'PRECIO TOTAL: Valor total de venta (sin I.G.V): 73,600.00 USD | I.G.V. 18%: 13,248.00 USD | TOTAL:\n86,848.00 USD\n'
             'Schindler 3000 - 630 kg, 17 parada, 1.75 m/s Edificio\nSchindler 3000 - 630 kg, 17 parada, 1.75 m/s Edificio.')
    item = lambda ref: {'valores': {'referencia_item': ref, 'descripcion': 'Schindler 3000 - 630 kg, 17 parada, 1.75 m/s - Edificio',
                                    'cantidad': 1, 'precio_unitario': 36800, 'parcial': 36800},
                        'originales': {'descripcion': 'Schindler 3000 - 630 kg, 17 parada, 1.75 m/s - Edificio',
                                       'cantidad': '+1 x', 'precio_unitario': '36,800', 'parcial': '36,800.00 USD'}}
    repetido = lambda d: {'valores': {'descripcion': d}, 'originales': {'descripcion': d}}
    data, source, context = armar(
        texto,
        {'moneda': 'USD', 'subtotal': 73600, 'impuestos': 13248, 'total': 86848},
        {'moneda': 'USD', 'subtotal': 'Valor total de venta (sin I.G.V): 73,600.00 USD', 'impuestos': 'I.G.V. 18%: 13,248.00 USD',
         'total': 'TOTAL:\n86,848.00 USD'},
        [item('00100'), item('00200'), repetido('Schindler 3000 - 630 kg, 17 parada, 1.75 m/s Edificio'),
         repetido('Schindler 3000 - 630 kg, 17 parada, 1.75 m/s Edificio.')])
    resultado = contract.combine([data], [source], context, 'claude-prueba')
    comercial = resultado['datos_comerciales']
    assert (comercial['moneda'], comercial['subtotal'], comercial['impuestos'], comercial['total']) == ('USD', 73600, 13248, 86848)
    assert len(resultado['items']) == 2, 'los ítems vacíos que repiten la descripción deben descartarse'
    assert all(i['cantidad'] == 1 and i['precio_unitario'] == 36800 and i['parcial'] == 36800 for i in resultado['items'])
    assert not {'numero_ambiguo', 'moneda_ambigua'} & tipos(resultado)
    faltantes = [o for o in resultado['observaciones'] if o['tipo'] == 'campo_item_faltante']
    assert faltantes and all('unidad' in o['descripcion'] and not o['requiere_aclaracion'] for o in faltantes)


def test_powertech_formato_europeo_y_etiquetas():
    texto = ('Ascensor Pasajeros | Cantidad 2 | Precio unit. US$ 36.937,55 | Costo total US$ 73.875,10\n'
             'Valor de Venta US$ 73.875,10 | I.G.V. 18% US$ 13.297,52 | Precio Total US$ 87.172,62')
    data, source, context = armar(
        texto,
        {'moneda': 'USD', 'subtotal': 73875.10, 'impuestos': 13297.52, 'total': 87172.62},
        {'moneda': 'US$', 'subtotal': 'Valor de Venta US$ 73.875,10', 'impuestos': 'I.G.V. 18% US$ 13.297,52',
         'total': 'Precio Total US$ 87.172,62'},
        [{'valores': {'descripcion': 'Ascensor Pasajeros', 'cantidad': 2, 'precio_unitario': 36937.55, 'parcial': 73875.10},
          'originales': {'descripcion': 'Ascensor Pasajeros', 'cantidad': 'Cantidad 2', 'precio_unitario': 'US$ 36.937,55',
                         'parcial': 'Costo total US$ 73.875,10'}}])
    resultado = contract.combine([data], [source], context, 'claude-prueba')
    comercial = resultado['datos_comerciales']
    assert (comercial['subtotal'], comercial['impuestos'], comercial['total']) == (73875.10, 13297.52, 87172.62)
    item = resultado['items'][0]
    assert (item['cantidad'], item['precio_unitario'], item['parcial']) == (2, 36937.55, 73875.10)
    assert 'numero_ambiguo' not in tipos(resultado)


def test_tk_signo_dolar_con_dolares_americanos_en_el_mismo_documento():
    texto = ('Equipos: CINNCO 8 personas | Precio Unitario $ 37,790.00 | UND 2 | Sub Total $ 75,580.00 | I.G.V $\n13,604.40 | Total $ 89,184.40\n'
             '30% Cuota inicial. A la firma del contrato a pagar en dólares americanos.')
    data, source, context = armar(
        texto,
        {'moneda': 'USD', 'subtotal': 75580, 'impuestos': 13604.40, 'total': 89184.40},
        {'moneda': '$', 'subtotal': '$ 75,580.00', 'impuestos': 'I.G.V $\n13,604.40', 'total': '$ 89,184.40'})
    resultado = contract.combine([data], [source], context, 'claude-prueba')
    comercial = resultado['datos_comerciales']
    assert comercial['moneda'] == 'USD'
    assert (comercial['subtotal'], comercial['impuestos'], comercial['total']) == (75580, 13604.40, 89184.40)
    assert not {'numero_ambiguo', 'moneda_ambigua'} & tipos(resultado)


def test_dolar_solo_sigue_siendo_ambiguo_si_el_documento_no_nombra_la_moneda():
    data, source, context = armar('Sub Total $ 75,580.00 Total $ 89,184.40', {'moneda': 'USD', 'subtotal': 75580},
                                  {'moneda': '$', 'subtotal': '$ 75,580.00'})
    resultado = contract.combine([data], [source], context, 'claude-prueba')
    assert resultado['datos_comerciales']['moneda'] is None
    assert 'moneda_ambigua' in tipos(resultado)


@pytest.mark.parametrize('frase, esperada', [
    ('a pagar en dólares americanos', 'USD'), ('Total 86,848.00 USD', 'USD'), ('Precio US$ 13.297,52', 'USD'),
    ('precios en soles', 'PEN'), ('solo $ sin nombre', None), ('velocidad 1.75 m/s y 36 MESES', None), ('USD y soles', None),
])
def test_moneda_que_nombra_el_documento(frase, esperada):
    assert contract.detect_currency([frase]) == esperada


def test_especificacion_compuesta_se_conserva_sin_pedir_aclaracion():
    texto = 'Dimensiones de Cabina 1300x1250 mm. Tensión 3 Ph 220V / 1 Ph 220 V (60 Hz)'
    data, source, context = armar(texto, {}, {})
    data['especificaciones_tecnicas'] = [
        {'documento_id': source['documento_id'], 'referencia_item': None, 'campo': 'Dimensiones de Cabina', 'valor_original': '1300x1250',
         'valor_numerico': 1300, 'unidad_original': None, 'unidad_normalizada': None, 'evidencia_ids': ['e1']}]
    resultado = contract.combine([data], [source], context, 'claude-prueba')
    especificacion = resultado['especificaciones_tecnicas'][0]
    assert especificacion['valor_original'] == '1300x1250' and especificacion['valor_numerico'] is None
    observacion = next(o for o in resultado['observaciones'] if o['tipo'] == 'numero_tecnico_ambiguo')
    assert observacion['severidad'] == 'baja' and not observacion['requiere_aclaracion']
