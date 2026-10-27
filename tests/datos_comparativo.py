"""Solo datos ficticios para verificar E5 y el servicio Excel."""
def id_prueba(n):
    return f'{n:08d}-2222-4222-8222-222222222222'


def datos_validados():
    registros=[]
    for n,pen,usd in [(1,370,100),(2,400,None)]:
        pid=id_prueba(n);vid=id_prueba(n+10)
        registros.append({'solicitud_id':id_prueba(100),'proveedor_id':pid,'version_id':vid,
            'proyecto':{'codigo':'TEST','nombre':'Proyecto ficticio'},
            'estado_revision':'listo_para_cuadro','habilitado_para_cuadro':True,'moneda_comparacion':'PEN',
            'base':[{'id':id_prueba(200),'descripcion':'Ascensor de prueba','unidad':'und','metrado':2}],
            'plantilla':{'documento_id':id_prueba(300),'storage_file_id':id_prueba(301),
                        'nombre':'HISTORICO_COMPARATIVO_ASCENSOR_5.2-aecode - plantilla.xlsx','contrato':'ascensores-plantilla-5.2-v1'},
            'postores':[{'id':pid,'nombre':f'PROVEEDOR FICTICIO {n}',
                'version':{'id':vid,'version':1,'es_final':True,'estado':'vigente','origen':'correo'},
                'campos':[{'campo_id':'garantia','valor_original':'24 meses'},
                          {'campo_id':'plazo_envio','valor_original':'6 meses'}]}],
            'partidas':[{'correspondencia':'validada_especialista','comparable':{
                'partida_id':id_prueba(200),'unidad':'und','cantidad':2,'precio_unitario_usd':usd,
                'precio_unitario_pen':pen,'parcial_pen':pen*2}}],
            'tipo_cambio':{'valor':3.7,'sentido':'USD_PEN','fecha':'2026-10-27','fuente':'Cambio ficticio de prueba','aprobado_por':'especialista_ficticio'} if usd else None,
            'totales_validados':{'gastos_generales_pen':0,'utilidad_pen':0,'igv_tasa':.18,
                                'subtotal_sin_igv_pen':pen*2,'total_con_igv_pen':round(pen*2*1.18,2)},
            'decisiones':[{'tipo':'homologacion_validada','version_id':vid,'aprobado_por':'especialista_ficticio',
                           'aprobado_at':'2026-10-27T00:00:00-05:00'}],'pendientes':[]})
    return {'homologaciones':registros,'revision':0}
