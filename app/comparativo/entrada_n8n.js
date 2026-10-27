/* Coordinación de E5; los cálculos y el llenado pertenecen al servicio Excel. */
function agrupar(entradas) {
  const filas=entradas.flatMap(e=>Array.isArray(e.homologaciones)?e.homologaciones:[e]);
  const grupos=new Map();
  for(const f of filas){
    const key=f.solicitud_id??'sin_solicitud';
    if(!grupos.has(key))grupos.set(key,[]);grupos.get(key).push(f);
  }
  return [...grupos.entries()].map(([solicitud_id,homologaciones])=>{
    const motivos=[];
    for(const f of homologaciones){
      if(f.estado_revision!=='listo_para_cuadro'||f.habilitado_para_cuadro!==true)motivos.push('La homologación aún requiere revisión.');
      if((f.pendientes??[]).some(p=>p.bloqueante))motivos.push('Hay pendientes bloqueantes.');
      if(!f.plantilla?.storage_file_id)motivos.push('Falta la plantilla registrada en Nhost.');
      if(!(f.decisiones??[]).some(d=>d.tipo==='homologacion_validada'&&d.version_id===f.version_id&&d.aprobado_por&&d.aprobado_at))motivos.push('Falta decisión de validación del especialista.');
      if(!(f.partidas??[]).length||(f.partidas??[]).some(p=>p.correspondencia!=='validada_especialista'||!p.comparable))motivos.push('Faltan correspondencias y valores comparables validados.');
    }
    const vistos=new Set();for(const f of homologaciones){if(vistos.has(f.proveedor_id))motivos.push('Proveedor duplicado: resolver su versión o alternativa.');vistos.add(f.proveedor_id);}
    if(homologaciones.length>7)motivos.push('La plantilla compartida admite siete bloques.');
    if(homologaciones.some(f=>JSON.stringify(f.plantilla)!==JSON.stringify(homologaciones[0].plantilla)))motivos.push('No mezclar plantillas.');
    return {estado:motivos.length?'pendiente_validacion':'verificar_fuente',solicitud_id,
      motivos:[...new Set(motivos)],datos:{homologaciones,revision:entradas[0]?.revision??0,
        presupuesto_meta:entradas[0]?.presupuesto_meta??null},
      plantilla:homologaciones[0]?.plantilla??null};
  });
}
function verificar(respuesta, grupo){
  if(respuesta.errors?.length)throw new Error('Nhost: '+respuesta.errors.map(e=>e.message).join('; '));
  const d=respuesta.data;if(!d)throw new Error('Nhost no devolvió datos.');
  const motivos=[];
  if(d.versiones.length>200)throw new Error('Demasiadas versiones: no se usará una consulta incompleta.');
  if(!Array.isArray(d.plantillas)||d.plantillas.length!==1||d.plantillas[0].storage_file_id!==grupo.plantilla.storage_file_id)
    motivos.push('La plantilla registrada cambió después de la homologación.');
  const base=grupo.datos.homologaciones[0].base??[];
  if(!Array.isArray(d.partidas)||base.length!==d.partidas.length||base.some(b=>!d.partidas.some(p=>
    p.id===b.id&&p.descripcion===b.descripcion&&p.unidad===b.unidad&&Number(p.metrado)===Number(b.metrado))))
    motivos.push('El itemizado cambió después de la homologación.');
  for(const r of grupo.datos.homologaciones){
    const p=d.participaciones.find(p=>p.proveedor_id===r.proveedor_id);
    const v=d.versiones.find(v=>v.id===r.version_id&&v.proveedor_id===r.proveedor_id);
    if(!p?.considerado||p.estado_respuesta!=='envio_cotizacion'||p.detalle_respuesta!=='cotizacion_definitiva')motivos.push('El proveedor ya no está en estado de cotización definitiva.');
    if(!v?.es_final||v.estado!=='vigente'||v.origen!=='correo')motivos.push('La versión validada ya no es final vigente.');
    if(v&&d.versiones.some(x=>x.proveedor_id===r.proveedor_id&&x.version>v.version&&x.estado!=='anulada'))motivos.push('Existe una versión posterior pendiente de resolver.');
    if(d.aclaraciones.some(x=>x.proveedor_id===r.proveedor_id))motivos.push('Hay aclaraciones abiertas.');
  }
  return {...grupo,estado:motivos.length?'pendiente_validacion':'generar',motivos};
}
module.exports={agrupar,verificar};
