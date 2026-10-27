import copy
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import pytest
from app.comparativo import plantilla as p
from datos_comparativo import datos_validados


def test_no_acepta_propuesta_de_e4_sin_revision_ni_con_solo_cambiar_el_indicador():
    d=datos_validados();r=d['homologaciones'][0]
    r['estado_revision']='requiere_revision';r['habilitado_para_cuadro']=False
    with pytest.raises(p.DatosPendientes):p.planificar(d)
    r['estado_revision']='listo_para_cuadro';r['habilitado_para_cuadro']=True;r['decisiones']=[]
    with pytest.raises(p.DatosPendientes,match='decisión'):p.planificar(d)


def test_rechaza_mezcla_versiones_numeros_ambiguos_y_cambio_sin_autorizar():
    for alterar in [lambda d:d['homologaciones'][1].update(solicitud_id='otra'),
                    lambda d:d['homologaciones'][1].update(proveedor_id=d['homologaciones'][0]['proveedor_id']),
                    lambda d:d['homologaciones'][0]['partidas'][0]['comparable'].update(precio_unitario_pen='370,00'),
                    lambda d:d['homologaciones'][0]['tipo_cambio'].update(aprobado_por=None),
                    lambda d:d['homologaciones'][0]['partidas'][0]['comparable'].update(parcial_pen=1)]:
        d=datos_validados();alterar(d)
        with pytest.raises(p.DatosPendientes):p.planificar(d)


def test_faltante_no_es_cero_y_formula_conserva_tc_editable():
    plan,_=p.planificar(datos_validados());c=plan['celdas']
    assert c['F5']['valor']==3.7 and c['J13']['formula'].endswith('I13*$F$5)')
    assert c['M13']['valor'] is None and c['N13']['valor']==400
    assert c['E13']['valor'] is None  # No reutilizar presupuesto histórico.
    assert c['K17']['valor']==0 and c['P13']['valor'] is None
    assert 'Ingresar meta' in c['H23']['formula']
    assert c['H31']['valor']=='24 meses' and c['H28']['valor'] is None


def test_preserva_partes_y_formatos_y_reporta_ref_previo(tmp_path,monkeypatch):
    datos=datos_validados();plan,_=p.planificar(datos)
    filas={}
    for cell in plan['celdas']:
        row=''.join(filter(str.isdigit,cell));filas.setdefault(row,[]).append(f'<c r="{cell}" s="1"><v>0</v></c>')
    xml='<worksheet xmlns="'+p.NS['s']+'"><sheetViews><sheetView workbookViewId="0"/></sheetViews><cols><col min="2" max="2" width="40"/></cols><sheetData>'
    xml+=''.join('<row r="'+row+'">'+''.join(cells)+'</row>' for row,cells in filas.items())
    xml+='<row r="40"><c r="AP40"><f>AL40+#REF!</f><v>0</v></c></row></sheetData><mergeCells><mergeCell ref="H6:K6"/></mergeCells><extLst><ext uri="prueba"/></extLst></worksheet>'
    origen=tmp_path/'plantilla.xlsx';destino=tmp_path/'resultado.xlsx'
    with ZipFile(origen,'w') as z:
        z.writestr(p.HOJA,xml);z.writestr('xl/styles.xml','estilos intactos')
        z.writestr('xl/comments1.xml','comentarios intactos');z.writestr('xl/worksheets/sheet2.xml','hoja intacta')
        z.writestr('xl/workbook.xml','<workbook><calcPr calcMode="manual"/></workbook>')
        z.writestr('xl/calcChain.xml','<calcChain/>')
        z.writestr('[Content_Types].xml','<Types><Override PartName="/xl/calcChain.xml"/></Types>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Target="calcChain.xml"/></Relationships>')
    perfil=tmp_path/'plantillas/homologacion/contratos';perfil.mkdir(parents=True)
    (perfil/'ascensores-plantilla-5.2.json').write_text(json.dumps({'sha256_origen':hashlib.sha256(origen.read_bytes()).hexdigest()}))
    monkeypatch.setattr(p,'ROOT',tmp_path)
    def cache_stub(plan):
        c={cell:'' for cell,v in plan['celdas'].items() if v.get('formula')}
        c.update(K13=740,K19=740,K21=873.2,O13=800,O19=800,O21=944)
        return c
    reporte=p.generar(datos,origen,destino,calculador=cache_stub)
    assert reporte['estado']=='generado_con_observaciones'
    assert reporte['validacion']['referencias_invalidas_preexistentes']==['AP40']
    with ZipFile(origen) as a,ZipFile(destino) as b:
        assert a.read('xl/styles.xml')==b.read('xl/styles.xml')
        assert a.read('xl/comments1.xml')==b.read('xl/comments1.xml')
        assert a.read('xl/worksheets/sheet2.xml')==b.read('xl/worksheets/sheet2.xml')
        assert 'xl/calcChain.xml' not in b.namelist()
        sheet=ET.fromstring(b.read(p.HOJA));assert sheet.find('.//s:c[@r="K21"]/s:v',p.NS).text=='873.2'
    with pytest.raises(ValueError,match='sobrescribir'):p.generar(datos,origen,destino,calculador=cache_stub)


def test_flujo_se_regenera_y_consume_estado_pendiente_sin_llamar_servicio():
    root=Path(__file__).resolve().parents[1]
    mod=runpy.run_path(str(root/'scripts/generar_flujo_comparativo.py'))
    assert mod['generar']()==json.loads((root/'n8n/flujos/e5-elaborar-cuadro-comparativo.json').read_text(encoding='utf-8'))
    programa="const {agrupar}=require('./app/comparativo/entrada_n8n.js');console.log(JSON.stringify(agrupar([{estado:'esperando_insumos'}])));"
    r=subprocess.run(['node','-e',programa],cwd=root,check=True,capture_output=True,text=True)
    assert json.loads(r.stdout)[0]['estado']=='pendiente_validacion'


def test_no_genera_si_la_plantilla_o_el_itemizado_cambiaron_despues_de_revisar():
    root=Path(__file__).resolve().parents[1];d=datos_validados();registros=d['homologaciones']
    fuente={'participaciones':[{'proveedor_id':r['proveedor_id'],'considerado':True,'estado_respuesta':'envio_cotizacion','detalle_respuesta':'cotizacion_definitiva'} for r in registros],
            'versiones':[{'id':r['version_id'],'proveedor_id':r['proveedor_id'],'version':1,'es_final':True,'estado':'vigente','origen':'correo'} for r in registros],
            'aclaraciones':[],'plantillas':[{'storage_file_id':registros[0]['plantilla']['storage_file_id']}],'partidas':registros[0]['base']}
    programa="const {agrupar,verificar}=require('./app/comparativo/entrada_n8n.js');const p=JSON.parse(require('fs').readFileSync(0,'utf8'));const g=agrupar(p.registros)[0];const a=verificar({data:p.fuente},g);p.fuente.plantillas[0].storage_file_id='otra';const b=verificar({data:p.fuente},g);p.fuente.partidas[0].metrado=99;const c=verificar({data:p.fuente},g);console.log(JSON.stringify([a.estado,b.motivos,c.motivos]));"
    r=subprocess.run(['node','-e',programa],cwd=root,input=json.dumps({'registros':registros,'fuente':fuente}),capture_output=True,text=True,encoding='utf-8',check=True)
    a,b,c=json.loads(r.stdout);assert a=='generar'
    assert any('plantilla' in x for x in b) and any('itemizado' in x for x in c)
