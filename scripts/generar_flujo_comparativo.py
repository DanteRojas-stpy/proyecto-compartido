"""E5 coordina entrada validada -> servicio Excel -> archivo y comprobaciones."""
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT=Path(__file__).resolve().parents[1]
REGLAS=(ROOT/'app/comparativo/entrada_n8n.js').read_text(encoding='utf-8').split('module.exports=')[0]
URL='https://zgorsmkvfyytsouacrpa.hasura.sa-east-1.nhost.run/v1/graphql'
SERVICIO='http://host.docker.internal:18775'
QUERY='''query ValidarCuadro($s: uuid!) {
 participaciones: solicitud_proveedores(where: {solicitud_id: {_eq: $s}}) {
  proveedor_id considerado estado_respuesta detalle_respuesta
 }
 versiones: versiones_cotizacion(where: {solicitud_id: {_eq: $s}}, limit: 201) {
  id proveedor_id version estado es_final origen
 }
 aclaraciones: aclaraciones_proveedor(where: {solicitud_id: {_eq: $s}, estado: {_eq: "abierta"}}) { proveedor_id }
 plantillas: documentos(where: {solicitud_id: {_eq: $s}, tipo: {_eq: "plantilla_comparativo"}}, limit: 2) { storage_file_id }
 partidas(where: {solicitud_id: {_eq: $s}}, limit: 1001) { id descripcion unidad metrado }
}'''


def nodo(name,typ,p=None,version=1,**extra):
    return {'id':str(uuid5(NAMESPACE_URL,'costflow-e5/'+name)),'name':name,'type':'n8n-nodes-base.'+typ,
            'typeVersion':version,'position':[0,0],'parameters':p or {},**extra}


def code(name,body):return nodo(name,'code',{'jsCode':REGLAS+'\n'+body},2)


def cond(name,exp):
    return nodo(name,'if',{'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict','version':2},
        'conditions':[{'leftValue':exp,'rightValue':True,'operator':{'type':'boolean','operation':'true','singleValue':True}}],
        'combinator':'and'},'options':{}},2.2)


def generar():
    n=[nodo('Revisar entrada del cuadro','manualTrigger'),
       nodo('Recibir salida de homologación','executeWorkflowTrigger',{'inputSource':'passthrough'},1.1),
       code('Agrupar y comprobar validación','return agrupar($input.all().map(x=>x.json)).map(json=>({json}));'),
       cond('¿Homologación validada?',"={{ $json.estado === 'verificar_fuente' }}"),
       nodo('Revalidar finales en Nhost','httpRequest',{'method':'POST','url':URL,'authentication':'genericCredentialType','genericAuthType':'httpHeaderAuth',
            'sendBody':True,'specifyBody':'json','jsonBody':'={{ { query: '+json.dumps(QUERY.replace('}}','} }'))+', variables: { s: $json.solicitud_id } } }}',
            'options':{'timeout':30000}},4.2),
       code('Comprobar vigencia de la fuente',"return $input.all().map((x,i)=>({json:verificar(x.json,$('Agrupar y comprobar validación').itemMatching(i).json),pairedItem:{item:i}}));"),
       cond('¿Fuente vigente?',"={{ $json.estado === 'generar' }}"),
       nodo('Descargar plantilla compartida','httpRequest',{'url':"={{ 'https://zgorsmkvfyytsouacrpa.storage.sa-east-1.nhost.run/v1/files/' + $json.plantilla.storage_file_id }}",
            'authentication':'genericCredentialType','genericAuthType':'httpHeaderAuth',
            'options':{'timeout':120000,'response':{'response':{'responseFormat':'file','outputPropertyName':'plantilla'}}}},4.2),
       code('Preparar pedido del Excel',"const out=[];for(const [i,x] of $input.all().entries()){const base=$('Comprobar vigencia de la fuente').itemMatching(i).json;const b=await this.helpers.getBinaryDataBuffer(i,'plantilla');out.push({json:{datos:base.datos,plantilla_base64:b.toString('base64')},pairedItem:{item:i}});}return out;"),
       nodo('Generar Excel con formato preservado','httpRequest',{'method':'POST','url':SERVICIO+'/generar',
            'authentication':'genericCredentialType','genericAuthType':'httpHeaderAuth','sendBody':True,'specifyBody':'json','jsonBody':'={{ $json }}',
            'options':{'timeout':240000}},4.2),
       cond('¿Archivo generado?',"={{ ['generado_validado','generado_con_observaciones'].includes($json.estado) }}"),
       nodo('Obtener cuadro comparativo','httpRequest',{'url':'={{ '+json.dumps(SERVICIO)+' + $json.ruta_descarga }}',
            'authentication':'genericCredentialType','genericAuthType':'httpHeaderAuth',
            'options':{'timeout':120000,'response':{'response':{'responseFormat':'file','outputPropertyName':'cuadro'}}}},4.2),
       code('Entregar cuadro y validación',"return $input.all().map((x,i)=>{const informe=$('Generar Excel con formato preservado').itemMatching(i).json;return {json:informe,binary:{cuadro:{...x.binary.cuadro,fileName:informe.archivo}},pairedItem:{item:i}}});"),
       nodo('Pendiente de datos validados','noOp'),
       nodo('Skill de cuadro comparativo','stickyNote',{'content':
           '## E5: elaborar cuadro comparativo\nSkill: elaborar-cuadro-comparativo/SKILL.md.\nRecibe los registros de E4; una propuesta sin revisar termina pendiente. No aprueba equivalencias.\nAgrupa proveedores de la misma solicitud, verifica finales en Nhost, descarga su plantilla y llama al servicio Excel local autenticado.\nEl servicio conserva formato, hojas, comentarios y extensiones; comprueba cálculos y totales.\nEl Excel se descarga en el nodo final. No se envía por correo ni se sube a Nhost. El #REF! previo en AP9 se informa como observación.\nConectar la cabecera Nhost a sus dos nodos HTTP y CostFlow Excel local a los tres del servicio.','width':690,'height':320})]
    c={}
    def link(a,b,out=0):
        ramas=c.setdefault(a,{'main':[]})['main']
        while len(ramas)<=out:ramas.append([])
        ramas[out].append({'node':b,'type':'main','index':0})
    for a in ['Revisar entrada del cuadro','Recibir salida de homologación']:link(a,'Agrupar y comprobar validación')
    chain=[x['name'] for x in n[2:13]]
    for a,b in zip(chain,chain[1:]):link(a,b)
    for a in ['¿Homologación validada?','¿Fuente vigente?','¿Archivo generado?']:link(a,'Pendiente de datos validados',1)
    for i,x in enumerate(n):x['position']=[(i%6)*280,(i//6)*260]
    return {'id':'costflowE5Cuadro01','name':'CostFlow - E5 Elaborar cuadro comparativo','active':False,'nodes':n,'connections':c,'pinData':{},
            'settings':{'executionOrder':'v1','timezone':'America/Lima','saveDataSuccessExecution':'all','saveDataErrorExecution':'all'}}


if __name__=='__main__':
    p=ROOT/'n8n/flujos/e5-elaborar-cuadro-comparativo.json'
    p.write_text(json.dumps(generar(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(p)
