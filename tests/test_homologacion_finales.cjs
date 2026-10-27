const test = require('node:test');
const assert = require('node:assert/strict');
const r = require('../app/homologacion/finales.js');
const contrato = require('../plantillas/homologacion/contratos/ascensores-plantilla-5.2.json');
const id = n => `${String(n).padStart(8,'0')}-1111-4111-8111-111111111111`;
function fuente() {
  const candidato = {solicitud_id:id(1),proveedor_id:id(2),entrada:r.prepararEntrada()};
  const v={id:id(3),solicitud_id:id(1),proveedor_id:id(2),version:2,es_final:true,estado:'vigente',origen:'correo'};
  const docs=[4,5].map(n=>({id:id(n),solicitud_id:id(1),proveedor_id:id(2),version_id:id(3),tipo:'cotizacion_proveedor',storage_file_id:id(n+10),nombre_original:'oferta'+n+'.pdf'}));
  const data={participacion:{estado_respuesta:'envio_cotizacion',detalle_respuesta:'cotizacion_definitiva',considerado:true},
    solicitud:{id:id(1),moneda:'PEN'},proveedor:{id:id(2),nombre:'Proveedor ficticio'},versiones:[v],
    documentos:[...docs,{id:id(9),tipo:'plantilla_comparativo',nombre_original:contrato.archivo,storage_file_id:id(19)}],
    partidas:[{id:id(7),descripcion:'Ascensor',unidad:'und',metrado:2}],aclaraciones:[],correos:[]};
  return {candidato,data};
}
test('sin cotización definitiva se espera; no se acepta solo respondio o ficha técnica',()=>{
  assert.equal(r.seleccionarParticipaciones({data:{solicitud_proveedores:[]}},r.prepararEntrada())[0].estado,'esperando_insumos');
  const p={...fuente().candidato,estado_respuesta:'no_envio_cotizacion',detalle_respuesta:'ficha_tecnica_sin_cotizacion',considerado:true};
  assert.equal(r.seleccionarParticipaciones({data:{solicitud_proveedores:[p]}},r.prepararEntrada())[0].estado,'esperando_insumos');
  assert.throws(()=>r.seleccionarParticipaciones({errors:[{message:'fallo'}]},{}),/Nhost/);
});
test('solo versión final vigente, sin aclaraciones ni una versión posterior sin resolver',()=>{
  const {data,candidato}=fuente();
  assert.equal(r.seleccionarVersion({data},candidato,contrato).estado,'leer_documentos');
  for(const cambiar of [d=>d.versiones[0].es_final=false,d=>d.versiones[0].estado='reemplazada',
    d=>d.aclaraciones.push({id:'abierta'}),d=>d.versiones.push({...d.versiones[0],id:id(31),version:3,es_final:false})]){
    const copia=structuredClone(data);cambiar(copia);
    assert.equal(r.seleccionarVersion({data:copia},candidato,contrato).estado,'esperando_insumos');
  }
});
test('la plantilla y el itemizado son necesarios; se excluyen adjuntos de otras versiones',()=>{
  const {data,candidato}=fuente();
  data.documentos.push({...data.documentos[0],id:id(50),version_id:id(51)});
  assert.equal(r.seleccionarVersion({data},candidato,contrato).contexto.documentos.length,2);
  data.documentos.find(x=>x.tipo==='plantilla_comparativo').nombre_original='otra.xlsx';
  assert.equal(r.seleccionarVersion({data},candidato,contrato).estado,'esperando_insumos');
  data.documentos.find(x=>x.tipo==='plantilla_comparativo').nombre_original=contrato.archivo;
  data.partidas=[];
  assert.equal(r.seleccionarVersion({data},candidato,contrato).estado,'esperando_insumos');
});
test('no se prepara una propuesta parcial ni se mezclan versiones/proveedores',()=>{
  const {data,candidato}=fuente(), c=r.seleccionarVersion({data},candidato,contrato).contexto;
  const archivos=c.documentos.map(documento=>({documento,contexto:c,texto:'Texto de prueba'}));
  assert.equal(r.prepararPeticiones(archivos)[0].estado,'homologar');
  assert.equal(r.prepararPeticiones(archivos.slice(0,1))[0].estado,'esperando_insumos');
  assert.equal(r.prepararPeticiones([archivos[0],archivos[0]])[0].estado,'esperando_insumos');
  const otro=structuredClone(archivos);for(const a of otro){a.contexto.version.id=id(91);a.contexto.proveedor_id=id(92);}
  assert.equal(r.prepararPeticiones([...archivos,...otro]).length,2);
  archivos[1].error='sin texto';assert.equal(r.prepararPeticiones(archivos)[0].estado,'esperando_insumos');
});
test('las credenciales o un texto del proveedor no sustituyen un cambio autorizado',()=>{
  assert.throws(()=>r.prepararEntrada({tipo_cambio:{valor:3.7}}),/requiere/);
  assert.throws(()=>r.prepararEntrada({solicitud_id:'no-es-uuid'}),/UUID/);
  assert.equal(r.prepararEntrada().tipo_cambio,null);
});
test('no convierte un número ambiguo ni un vacío en cero',()=>{
  assert.equal(r.numero('1,234'),null);assert.equal(r.numero(null),null);assert.equal(r.numero('0'),0);
  assert.equal(r.numero('US$ 1,250.50'),1250.5);assert.equal(r.numero('36.937,55'),36937.55);
});
test('rechaza datos sin cita literal y no aprueba equivalencias que propone la IA',()=>{
  const {data,candidato}=fuente(),c=r.seleccionarVersion({data},candidato,contrato).contexto;
  const f={documento_id:id(4),pagina:1,cita:'Precio USD 150.00',valor_texto:'150.00'};
  const preparado={contexto:c,fuentes:[{id:id(4),texto:'Precio USD 150.00. Cantidad 2.'}]};
  assert(r.evidenciaValida(f,preparado.fuentes));
  assert(!r.evidenciaValida({...f,valor_texto:'100.00'},preparado.fuentes));
  const item={descripcion:{...f,valor_texto:'Ascensor'},cantidad:{...f,cita:'Cantidad 2.',valor_texto:'2'},
    unidad:null,precio_unitario:f,parcial:{...f,valor_texto:'300.00'},partida_id_propuesta:id(7)};
  const out=r.validarPropuesta({output:{items:[item],campos:[],observaciones:[]}},preparado);
  assert.equal(out.proveedor_id,id(2));assert.equal(out.estado_revision,'requiere_revision');
  assert.equal(out.partidas[0].original.parcial,null);assert.equal(out.partidas[0].valores_numericos_originales.precio_unitario,150);
  assert.equal(out.partidas[0].comparable,null);assert.equal(out.habilitado_para_cuadro,false);
});
test('un cambio a aclaraciones durante la IA invalida la salida y no entrega una final antigua',()=>{
  const d={version:{es_final:true,estado:'vigente',origen:'correo'},participacion:{considerado:true,
    estado_respuesta:'envio_cotizacion',detalle_respuesta:'cotizacion_definitiva'},posteriores:[],aclaraciones:[]};
  const propuesta={solicitud_id:id(1),proveedor_id:id(2),version_id:id(3),estado:'homologacion_propuesta'};
  assert.deepEqual(r.comprobarVigencia({data:d},propuesta),propuesta);
  d.participacion.estado_respuesta='envio_cotizacion_con_aclaracion';
  assert.equal(r.comprobarVigencia({data:d},propuesta).estado,'esperando_insumos');
});
