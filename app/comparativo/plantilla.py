"""Parche de celdas para la plantilla compartida; conserva las demás partes OOXML."""
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
HOJA = 'xl/worksheets/sheet1.xml'
CONTRATO = 'ascensores-plantilla-5.2-v1'
BLOQUES = [('H','I','J','K'),('L','M','N','O'),('P','Q','R','S'),
           ('T','U','V','W'),('X','Y','Z','AA'),('AB','AC','AD','AE'),('AF','AG','AH','AI')]
FILAS = {'adelanto_garantia':26,'fondo_garantia':27,'contacto':28,'viga_divisoria':29,
         'plazo_envio':30,'garantia':31,'mantenimiento_gratuito':32,'forma_pago':33,
         'caracteristicas_cabina':34,'consideraciones':36,'obras_en_ejecucion':39}


class DatosPendientes(ValueError):
    pass


def numero(v, nombre, opcional=False):
    if v is None and opcional:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
        raise DatosPendientes(f'{nombre}: se requiere un número validado no negativo.')
    return v


def validar(datos):
    registros = datos.get('homologaciones', [])
    if not registros or len(registros) > len(BLOQUES):
        raise DatosPendientes('Se requieren de 1 a 7 homologaciones validadas para esta plantilla.')
    primero = registros[0]
    vistos = set()
    base = primero.get('base', [])
    if len(base) != 1:
        raise DatosPendientes('El mapeo cubre una partida en la fila 13; requiere otro mapeo para más filas.')
    tc = None
    proveedores = []
    for r in registros:
        if r.get('estado_revision') != 'listo_para_cuadro' or r.get('habilitado_para_cuadro') is not True:
            raise DatosPendientes('La salida de E4 todavía requiere validación de homologación.')
        if any(p.get('bloqueante') for p in r.get('pendientes', [])):
            raise DatosPendientes('Hay pendientes bloqueantes sin resolver.')
        if r.get('solicitud_id') != primero.get('solicitud_id') or r.get('plantilla') != primero.get('plantilla'):
            raise DatosPendientes('No mezclar solicitudes ni plantillas en un cuadro.')
        if r.get('base') != base or r.get('moneda_comparacion') != 'PEN':
            raise DatosPendientes('La base o moneda no corresponde al mapeo aprobado en soles.')
        if r.get('plantilla', {}).get('contrato') != CONTRATO:
            raise DatosPendientes('Contrato de plantilla no reconocido.')
        pid = r.get('proveedor_id')
        if not pid or pid in vistos:
            raise DatosPendientes('Proveedores duplicados o sin identificación; no se elige una versión automáticamente.')
        vistos.add(pid)
        postores = r.get('postores', [])
        if len(postores) != 1 or postores[0].get('id') != pid:
            raise DatosPendientes('La homologación debe identificar al proveedor.')
        postor = postores[0]
        version = postor.get('version', {})
        if version.get('id') != r.get('version_id') or version.get('es_final') is not True or version.get('estado') != 'vigente':
            raise DatosPendientes('La versión no está identificada como final vigente.')
        items = r.get('partidas', [])
        if len(items) != 1:
            raise DatosPendientes('Esta plantilla requiere un ítem o agrupación validada por proveedor.')
        item = items[0]
        aprobado = any(d.get('tipo') == 'homologacion_validada' and d.get('version_id') == r.get('version_id')
                       and d.get('aprobado_por') and d.get('aprobado_at') for d in r.get('decisiones', []))
        if not aprobado or item.get('correspondencia') != 'validada_especialista':
            raise DatosPendientes('Falta la decisión registrada del especialista para la correspondencia técnica.')
        c = item.get('comparable') or {}
        if c.get('partida_id') != base[0].get('id') or c.get('unidad') != base[0].get('unidad'):
            raise DatosPendientes('La partida o unidad comparable no coincide con la base.')
        cantidad = numero(c.get('cantidad'), 'cantidad')
        pen = numero(c.get('precio_unitario_pen'), 'precio_unitario_pen')
        usd = numero(c.get('precio_unitario_usd'), 'precio_unitario_usd', opcional=True)
        parcial = numero(c.get('parcial_pen'), 'parcial_pen')
        if abs(cantidad * pen - parcial) > .02:
            raise DatosPendientes('Cantidad por precio unitario no coincide con el parcial validado.')
        if usd is not None:
            cambio = r.get('tipo_cambio') or {}
            valor = numero(cambio.get('valor'), 'tipo_cambio.valor')
            if not valor or cambio.get('sentido') != 'USD_PEN' or not cambio.get('fecha') or not cambio.get('fuente') or not cambio.get('aprobado_por'):
                raise DatosPendientes('Falta tipo de cambio autorizado, fecha y fuente.')
            if tc is not None and tc != valor:
                raise DatosPendientes('La plantilla tiene un solo TC; no admite cambios distintos por proveedor.')
            tc = valor
            if abs(usd * valor - pen) > .01:
                raise DatosPendientes('Los precios validados en dólares y soles no coinciden con el TC.')
        totales = r.get('totales_validados') or {}
        t = {k: numero(totales.get(k), k, opcional=True) for k in
             ['gastos_generales_pen','utilidad_pen','igv_tasa','subtotal_sin_igv_pen','total_con_igv_pen']}
        if t['igv_tasa'] is not None and t['igv_tasa'] != .18:
            raise DatosPendientes('La plantilla especifica IGV 18%; otra tasa requiere adaptar el mapeo.')
        if t['subtotal_sin_igv_pen'] is not None and (t['gastos_generales_pen'] is None or t['utilidad_pen'] is None):
            raise DatosPendientes('Para contrastar el subtotal faltan gastos generales o utilidad validados.')
        if t['total_con_igv_pen'] is not None and (t['subtotal_sin_igv_pen'] is None or t['igv_tasa'] is None):
            raise DatosPendientes('Para contrastar el total faltan subtotal o tratamiento del IGV validados.')
        if all(t[k] is not None for k in ['gastos_generales_pen','utilidad_pen','subtotal_sin_igv_pen']):
            if abs(parcial+t['gastos_generales_pen']+t['utilidad_pen']-t['subtotal_sin_igv_pen']) > .02:
                raise DatosPendientes('El subtotal declarado no concuerda con los componentes validados.')
        if all(t[k] is not None for k in ['igv_tasa','subtotal_sin_igv_pen','total_con_igv_pen']):
            if abs(t['subtotal_sin_igv_pen']*(1+t['igv_tasa'])-t['total_con_igv_pen']) > .02:
                raise DatosPendientes('El total con IGV no concuerda con el declarado.')
        campos = {f['campo_id']:f.get('valor_original') for f in postor.get('campos', [])}
        proveedores.append({'nombre':postor['nombre'], 'cantidad':cantidad,'pen':pen,'usd':usd,
                            'parcial':parcial,'totales':t,'campos':campos})
    return registros, base[0], proveedores, tc


def planificar(datos):
    registros, base, proveedores, tc = validar(datos)
    celdas = {}
    def valor(c, v):
        if isinstance(v, str) and len(v) > 32767:
            raise DatosPendientes(f'Texto demasiado largo para {c}; no se recorta automáticamente.')
        celdas[c] = {'valor':v}
    def formula(c, f): celdas[c] = {'formula':f}
    valor('I3', base['descripcion']); valor('F5', tc)
    formula('B3','"COMPARATIVO - "&$I$3')
    valor('B13', base['descripcion']); valor('C13', base['unidad'])
    meta = datos.get('presupuesto_meta')
    for col in ['D','E']: valor(col+'13', None)
    for row in [17,18]: valor('F'+str(row), None)
    if meta:
        valor('D13', numero(meta.get('cantidad'), 'meta.cantidad'))
        valor('E13', numero(meta.get('precio_unitario_pen'), 'meta.precio_unitario_pen'))
        valor('F17', numero(meta.get('gastos_generales_pen'), 'meta.gastos_generales_pen'))
        valor('F18', numero(meta.get('utilidad_pen'), 'meta.utilidad_pen'))
    formula('F13','IF(COUNT(D13,E13)<>2,"",D13*E13)')
    for dest, src in [('F11','F13'),('F9','F11'),('F16','F9')]:formula(dest,f'IF(ISNUMBER({src}),{src},"")')
    formula('F19','IF(COUNT(F16:F18)<>3,"",SUM(F16:F18))')
    formula('F20','IF(ISNUMBER(F19),F19*0.18,"")');formula('F21','IF(COUNT(F19:F20)<>2,"",F19+F20)')
    for index, (cant, pusd, ppen, total) in enumerate(BLOQUES):
        p = proveedores[index] if index < len(proveedores) else None
        valor(cant+'6', p['nombre'] if p else None)
        valor(cant+'13', p['cantidad'] if p else None)
        valor(pusd+'13', p['usd'] if p else None)
        if p and p['usd'] is None: valor(ppen+'13', p['pen'])
        else: formula(ppen+'13',f'IF(COUNT({pusd}13,$F$5)<>2,"",{pusd}13*$F$5)')
        formula(total+'13',f'IF(COUNT({cant}13,{ppen}13)<>2,"",{cant}13*{ppen}13)')
        for row, prev in [(11,13),(9,11),(16,9)]: formula(total+str(row),f'IF(ISNUMBER({total}{prev}),{total}{prev},"")')
        formula(total+'15',f'IF(COUNT({cant}13,{pusd}13)<>2,"",{cant}13*{pusd}13)')
        valor(total+'17',p['totales']['gastos_generales_pen'] if p else None)
        valor(total+'18',p['totales']['utilidad_pen'] if p else None)
        formula(total+'19',f'IF(COUNT({total}16:{total}18)<>3,"",SUM({total}16:{total}18))')
        if p and p['totales']['igv_tasa'] is not None:formula(total+'20',f'IF(ISNUMBER({total}19),{total}19*0.18,"")')
        else:valor(total+'20',None)
        formula(total+'21',f'IF(COUNT({total}19:{total}20)<>2,"",{total}19+{total}20)')
        formula(cant+'23',f'IF(ISNUMBER($F$21),IF(ISNUMBER({total}21),$F$21-{total}21,""),"Ingresar meta")' if p else '""')
        for key, row in FILAS.items(): valor(cant+str(row),p['campos'].get(key) if p else None)
    return {'celdas':celdas}, proveedores


def calcular(plan, node, worker):
    with tempfile.TemporaryDirectory(prefix='costflow-calculo-') as temporal:
        entrada=Path(temporal)/'entrada.json'; salida=Path(temporal)/'salida.json'
        entrada.write_text(json.dumps(plan,ensure_ascii=False),encoding='utf-8')
        subprocess.run([str(node),str(worker),str(entrada),str(salida)],check=True,capture_output=True,timeout=180)
        return json.loads(salida.read_text(encoding='utf-8'))


def _celda_xml(original, direccion, dato, caches):
    attrs = dict(re.findall(r'([\w:]+)="([^"]*)"', original.split('>')[0])) if original else {'r':direccion}
    attrs.pop('t',None)
    if dato.get('formula'):
        v = caches[direccion]
        if isinstance(v,str): attrs['t']='str'
        body='<f>'+escape(dato['formula'])+'</f><v>'+escape(str(v) if isinstance(v,str) else repr(v))+'</v>'
    elif dato.get('valor') is None: body=''
    elif isinstance(dato['valor'], str):
        attrs['t']='inlineStr';body='<is><t xml:space="preserve">'+escape(dato['valor'])+'</t></is>'
    else: body='<v>'+repr(dato['valor'])+'</v>'
    return '<c '+ ' '.join(k+'='+quoteattr(v) for k,v in attrs.items())+'>'+body+'</c>'


def generar(datos, plantilla, salida, *, node=None, worker=None, calculador=None):
    plan, proveedores = planificar(datos)
    perfil=json.loads((ROOT/'plantillas/homologacion/contratos/ascensores-plantilla-5.2.json').read_text(encoding='utf-8'))
    plantilla=Path(plantilla);salida=Path(salida)
    if hashlib.sha256(plantilla.read_bytes()).hexdigest()!=perfil['sha256_origen']:
        raise DatosPendientes('La plantilla no coincide con la copia inspeccionada. Revisar su mapeo antes de escribir.')
    if plantilla.resolve()==salida.resolve() or salida.exists():raise ValueError('No sobrescribir plantilla ni entregas previas.')
    caches = calculador(plan) if calculador else calcular(plan,node,worker)
    for celda,v in caches.items():
        if isinstance(v,bool) or not isinstance(v,(str,int,float)) or (isinstance(v,(int,float)) and not math.isfinite(v)):
            raise ValueError('Resultado de cálculo no válido: '+celda)
    for i,p in enumerate(proveedores):
        col=BLOQUES[i][3]
        for celda, esperado in [(col+'13',p['parcial']),(col+'19',p['totales']['subtotal_sin_igv_pen']),(col+'21',p['totales']['total_con_igv_pen'])]:
            if esperado is not None and (not isinstance(caches.get(celda),(float,int)) or abs(caches[celda]-esperado)>.02):
                raise ValueError('El cálculo no coincide con el valor validado: '+celda)
    with ZipFile(plantilla) as fuente:
        piezas={n:fuente.read(n) for n in fuente.namelist()}
        original=piezas[HOJA].decode('utf-8');nuevo=original
        for direccion,dato in plan['celdas'].items():
            patron=r'<c\b[^>]*\br="'+direccion+r'"(?=[\s/>])[^>]*(?:/>|>.*?</c>)'
            m=re.search(patron,nuevo,re.DOTALL)
            reemplazo=_celda_xml(m.group() if m else None,direccion,dato,caches)
            if m:nuevo=nuevo[:m.start()]+reemplazo+nuevo[m.end():]
            else:
                fila=re.search(r'<row\b[^>]*\br="'+re.sub(r'\D','',direccion)+r'"[^>]*>(.*?)</row>',nuevo,re.DOTALL)
                if not fila:raise ValueError('Fila no disponible en el mapeo: '+direccion)
                nuevo=nuevo[:fila.end()-6]+reemplazo+nuevo[fila.end()-6:]
        piezas[HOJA]=nuevo.encode('utf-8')
        piezas.pop('xl/calcChain.xml',None)
        for nombre in ['[Content_Types].xml','xl/_rels/workbook.xml.rels']:
            txt=piezas[nombre].decode('utf-8')
            txt=re.sub(r'<(?:Override|Relationship)\b[^>]*(?:calcChain|calcChain\.xml)[^>]*/>','',txt)
            piezas[nombre]=txt.encode('utf-8')
        wb=piezas['xl/workbook.xml'].decode('utf-8');calc=re.search(r'<calcPr\b[^>]*/>',wb)
        if calc:
            attrs=dict(re.findall(r'(\w+)="([^"]*)"',calc.group()));attrs.update(calcMode='auto',fullCalcOnLoad='1',forceFullCalc='1')
            wb=wb[:calc.start()]+'<calcPr '+ ' '.join(k+'='+quoteattr(v) for k,v in attrs.items())+'/>'+wb[calc.end():]
        piezas['xl/workbook.xml']=wb.encode('utf-8')
        salida.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(salida,'x') as destino:
            for info in fuente.infolist():
                if info.filename in piezas: destino.writestr(copy.copy(info),piezas[info.filename])
        permitidos={HOJA,'xl/calcChain.xml','[Content_Types].xml','xl/_rels/workbook.xml.rels','xl/workbook.xml'}
        with ZipFile(salida) as control:
            for nombre in fuente.namelist():
                if nombre not in permitidos and fuente.read(nombre)!=control.read(nombre):raise ValueError('Cambió una parte ajena al llenado: '+nombre)
            a=ET.fromstring(original);b=ET.fromstring(control.read(HOJA))
            for etiqueta in ['cols','mergeCells','conditionalFormatting','extLst','pageMargins','pageSetup','sheetViews']:
                assert [ET.tostring(e) for e in a.findall('s:'+etiqueta,NS)]==[ET.tostring(e) for e in b.findall('s:'+etiqueta,NS)],etiqueta
    errores_previos=[c.get('r') for c in ET.fromstring(original).findall('.//s:c',NS)
                    if '#REF!' in ''.join(c.itertext()) and c.get('r') not in plan['celdas']]
    faltantes=[p['nombre']+': '+k for p in proveedores for k,v in p['totales'].items() if v is None]
    return {'estado':'generado_con_observaciones' if errores_previos or faltantes else 'generado_validado',
            'validacion':{'calculo_ejecutado':True,'totales_contrastados':not faltantes,'partes_ajenas_preservadas':True,
                          'formato_preservado':True,'referencias_invalidas_preexistentes':errores_previos,
                          'datos_no_disponibles':faltantes,'validacion_global':not errores_previos and not faltantes},
            'archivo':salida.name,'proveedores':len(proveedores)}
