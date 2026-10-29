-- 018: tipo de cambio autorizado para el cuadro comparativo (E5).
-- E4 nunca inventa el tipo de cambio: lo indica el especialista al pedir el cuadro (valor, fecha y fuente) y queda en e5_cuadros.
-- Reemplaza e4_operar de 017 con solicitar_e5 y entrada_e5 ampliadas. Requiere 017. Se puede repetir.
BEGIN;

ALTER TABLE public.e5_cuadros ADD COLUMN IF NOT EXISTS tipo_cambio jsonb;

CREATE OR REPLACE FUNCTION public.e4_operar(p_operacion text,p jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $f$
DECLARE
 usuario uuid;solicitud uuid;e public.e4_ejecuciones%ROWTYPE;c public.e5_cuadros%ROWTYPE;h public.e4_homologaciones%ROWTYPE;
 nuevo uuid;finales integer;paquete jsonb;cambio jsonb;
BEGIN
 CASE p_operacion
 WHEN 'solicitar_e4' THEN
  usuario:=nullif(p->>'usuario_id_verificado','')::uuid;solicitud:=nullif(p->>'solicitud_id','')::uuid;
  IF usuario IS NULL THEN RETURN jsonb_build_object('ok',false,'http_code',401,'mensaje','Inicia sesión para homologar.'); END IF;
  IF solicitud IS NULL OR NOT public.e3_acceso(usuario,solicitud) THEN RETURN jsonb_build_object('ok',false,'http_code',403,'mensaje','No tienes acceso a esta solicitud.'); END IF;
  SELECT count(*) INTO finales FROM public.e3_finales_e4 WHERE solicitud_id=solicitud;
  IF finales=0 THEN RETURN jsonb_build_object('ok',false,'http_code',409,'mensaje','Todavía no hay cotizaciones aceptadas como finales para homologar.'); END IF;
  SELECT * INTO e FROM public.e4_ejecuciones WHERE solicitud_id=solicitud AND estado IN ('pendiente','en_curso');
  IF e.id IS NOT NULL THEN RETURN jsonb_build_object('ok',false,'http_code',409,'ejecucion_id',e.id,'mensaje','Ya hay una homologación en curso para esta solicitud.'); END IF;
  INSERT INTO public.e4_ejecuciones(solicitud_id,solicitado_por) VALUES(solicitud,usuario) RETURNING id INTO nuevo;
  RETURN jsonb_build_object('ok',true,'http_code',200,'ejecucion_id',nuevo,'finales',finales,'mensaje','Homologación solicitada.');
 WHEN 'tomar_e4' THEN
  UPDATE public.e4_ejecuciones SET estado=CASE WHEN intentos>=3 THEN 'error' ELSE 'pendiente' END,
   error=CASE WHEN intentos>=3 THEN 'Venció el tiempo de procesamiento' ELSE error END,
   lease_hasta=NULL,token=NULL,finished_at=CASE WHEN intentos>=3 THEN now() ELSE finished_at END
   WHERE estado='en_curso' AND lease_hasta<now();
  SELECT * INTO e FROM public.e4_ejecuciones WHERE estado='pendiente' ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED;
  IF e.id IS NULL THEN RETURN jsonb_build_object('resultado','vacio'); END IF;
  UPDATE public.e4_ejecuciones SET estado='en_curso',token=gen_random_uuid(),intentos=intentos+1,
   lease_hasta=now()+interval '15 minutes',started_at=coalesce(started_at,now()) WHERE id=e.id RETURNING * INTO e;
  RETURN jsonb_build_object('resultado','tomada','ejecucion_id',e.id,'solicitud_id',e.solicitud_id,'token',e.token,'intento',e.intentos);
 WHEN 'entrada_e4' THEN
  SELECT * INTO e FROM public.e4_ejecuciones WHERE id=(p->>'ejecucion_id')::uuid;
  IF e.id IS NULL OR e.estado<>'en_curso' OR e.token IS DISTINCT FROM (p->>'token')::uuid THEN RETURN jsonb_build_object('resultado','intento_vencido'); END IF;
  SELECT jsonb_build_object('ejecucion_id',e.id,'fecha_evaluacion',now(),
   'solicitud',(SELECT jsonb_build_object('id',s.id,'codigo',s.codigo,'nombre',s.nombre,'moneda',s.moneda,'fecha_limite',s.fecha_limite,
      'proyecto',jsonb_build_object('codigo',pr.codigo,'nombre',pr.nombre))
     FROM public.solicitudes_cotizacion s JOIN public.proyectos pr ON pr.id=s.proyecto_id WHERE s.id=e.solicitud_id),
   'partidas',coalesce((SELECT jsonb_agg(jsonb_build_object('id',x.id,'codigo',x.codigo,'descripcion',x.descripcion,'unidad',x.unidad,'metrado',x.metrado) ORDER BY x.orden,x.created_at)
     FROM public.partidas x WHERE x.solicitud_id=e.solicitud_id),'[]'::jsonb),
   'proveedores',coalesce((SELECT jsonb_agg(jsonb_build_object('id',pv.id,'nombre',pv.nombre,'estado',sp.estado) ORDER BY pv.nombre)
     FROM public.solicitud_proveedores sp JOIN public.proveedores pv ON pv.id=sp.proveedor_id WHERE sp.solicitud_id=e.solicitud_id),'[]'::jsonb),
   'finales',coalesce((SELECT jsonb_agg(jsonb_build_object('version_id',f.version_id,'proveedor_id',f.proveedor_id,'numero_version',f.numero_version,'resultado',f.resultado) ORDER BY f.proveedor_id)
     FROM public.e3_finales_e4 f WHERE f.solicitud_id=e.solicitud_id),'[]'::jsonb)) INTO paquete;
  RETURN jsonb_build_object('resultado','entrada','paquete',paquete);
 WHEN 'guardar_e4' THEN
  SELECT * INTO e FROM public.e4_ejecuciones WHERE id=(p->>'ejecucion_id')::uuid FOR UPDATE;
  IF e.id IS NULL OR e.estado<>'en_curso' OR e.token IS DISTINCT FROM (p->>'token')::uuid THEN RETURN jsonb_build_object('resultado','intento_vencido'); END IF;
  IF p->>'estado_revision' NOT IN ('listo_para_cuadro','requiere_revision') THEN RAISE EXCEPTION 'Estado de revisión no válido'; END IF;
  INSERT INTO public.e4_homologaciones(ejecucion_id,solicitud_id,estado_revision,resultado,version_ids,huella,modelo,tokens_entrada,tokens_salida)
   VALUES(e.id,e.solicitud_id,p->>'estado_revision',p->'resultado',ARRAY(SELECT jsonb_array_elements_text(p->'version_ids'))::uuid[],p->>'huella',p->>'modelo',
    nullif(p->>'tokens_entrada','')::integer,nullif(p->>'tokens_salida','')::integer) RETURNING * INTO h;
  UPDATE public.e4_ejecuciones SET estado='completado',finished_at=now(),token=NULL,lease_hasta=NULL,error=NULL WHERE id=e.id;
  INSERT INTO public.notificaciones(usuario_id,solicitud_id,proveedor_id,tipo,titulo,mensaje,datos,dedupe_key)
   VALUES(e.solicitado_por,e.solicitud_id,NULL,'homologacion_lista','Homologación (E4) lista',
    CASE WHEN h.estado_revision='listo_para_cuadro' THEN 'La homologación está lista para generar el cuadro comparativo.'
         ELSE 'La homologación tiene pendientes que debes revisar antes de generar el cuadro comparativo.' END,
    jsonb_build_object('homologacion_id',h.id,'estado_revision',h.estado_revision,'color',CASE WHEN h.estado_revision='listo_para_cuadro' THEN 'azul' ELSE 'ambar' END),
    'e4:'||h.id) ON CONFLICT(dedupe_key) DO NOTHING;
  RETURN jsonb_build_object('resultado','guardada','homologacion_id',h.id);
 WHEN 'fallo_e4' THEN
  SELECT * INTO e FROM public.e4_ejecuciones WHERE id=(p->>'ejecucion_id')::uuid FOR UPDATE;
  IF e.id IS NULL OR e.estado<>'en_curso' OR e.token IS DISTINCT FROM (p->>'token')::uuid THEN RETURN jsonb_build_object('resultado','intento_vencido'); END IF;
  IF e.intentos>=3 OR NOT coalesce((p->>'recuperable')::boolean,true) THEN
   UPDATE public.e4_ejecuciones SET estado='error',error=left(coalesce(p->>'error','Error sin detalle'),1500),finished_at=now(),token=NULL,lease_hasta=NULL WHERE id=e.id;
   INSERT INTO public.notificaciones(usuario_id,solicitud_id,proveedor_id,tipo,titulo,mensaje,datos,dedupe_key)
    VALUES(e.solicitado_por,e.solicitud_id,NULL,'homologacion_error','No se pudo homologar','La homologación (E4) no terminó. Revisa el detalle o vuelve a solicitarla.',
     jsonb_build_object('ejecucion_id',e.id,'color','rojo'),'e4-error:'||e.id) ON CONFLICT(dedupe_key) DO NOTHING;
   RETURN jsonb_build_object('resultado','error_definitivo');
  END IF;
  UPDATE public.e4_ejecuciones SET estado='pendiente',error=left(coalesce(p->>'error','Error sin detalle'),1500),token=NULL,lease_hasta=NULL WHERE id=e.id;
  RETURN jsonb_build_object('resultado','reintento_pendiente');
 WHEN 'solicitar_e5' THEN
  usuario:=nullif(p->>'usuario_id_verificado','')::uuid;solicitud:=nullif(p->>'solicitud_id','')::uuid;
  IF usuario IS NULL THEN RETURN jsonb_build_object('ok',false,'http_code',401,'mensaje','Inicia sesión para generar el cuadro.'); END IF;
  IF solicitud IS NULL OR NOT public.e3_acceso(usuario,solicitud) THEN RETURN jsonb_build_object('ok',false,'http_code',403,'mensaje','No tienes acceso a esta solicitud.'); END IF;
  SELECT * INTO h FROM public.e4_homologaciones WHERE solicitud_id=solicitud ORDER BY created_at DESC LIMIT 1;
  IF h.id IS NULL THEN RETURN jsonb_build_object('ok',false,'http_code',409,'mensaje','Primero homologa las cotizaciones finales (E4).'); END IF;
  SELECT * INTO c FROM public.e5_cuadros WHERE solicitud_id=solicitud AND estado IN ('pendiente','en_curso');
  IF c.id IS NOT NULL THEN RETURN jsonb_build_object('ok',false,'http_code',409,'cuadro_id',c.id,'mensaje','Ya se está generando un cuadro para esta solicitud.'); END IF;
  cambio:=nullif(p->'tipo_cambio','null'::jsonb);
  IF cambio IS NOT NULL THEN
   IF jsonb_typeof(cambio->'valor')<>'number' OR (cambio->>'valor')::numeric<=0 OR coalesce(cambio->>'fecha','')='' OR coalesce(cambio->>'fuente','')='' THEN
    RETURN jsonb_build_object('ok',false,'http_code',400,'mensaje','El tipo de cambio necesita un valor positivo, la fecha y la fuente.');
   END IF;
   cambio:=jsonb_build_object('valor',(cambio->>'valor')::numeric,'fecha',cambio->>'fecha','fuente',left(cambio->>'fuente',200),'sentido','USD_PEN','autorizado_por',usuario);
  END IF;
  INSERT INTO public.e5_cuadros(homologacion_id,solicitud_id,solicitado_por,revision,tipo_cambio)
   VALUES(h.id,solicitud,usuario,coalesce((SELECT max(revision) FROM public.e5_cuadros WHERE solicitud_id=solicitud),0)+1,cambio) RETURNING id INTO nuevo;
  RETURN jsonb_build_object('ok',true,'http_code',200,'cuadro_id',nuevo,'estado_revision',h.estado_revision,
   'mensaje',CASE WHEN h.estado_revision='listo_para_cuadro' THEN 'Cuadro solicitado.' ELSE 'Cuadro solicitado como borrador: la homologación tiene pendientes.' END);
 WHEN 'tomar_e5' THEN
  UPDATE public.e5_cuadros SET estado=CASE WHEN intentos>=3 THEN 'error' ELSE 'pendiente' END,
   error=CASE WHEN intentos>=3 THEN 'Venció el tiempo de procesamiento' ELSE error END,
   lease_hasta=NULL,token=NULL,finished_at=CASE WHEN intentos>=3 THEN now() ELSE finished_at END
   WHERE estado='en_curso' AND lease_hasta<now();
  SELECT * INTO c FROM public.e5_cuadros WHERE estado='pendiente' ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED;
  IF c.id IS NULL THEN RETURN jsonb_build_object('resultado','vacio'); END IF;
  UPDATE public.e5_cuadros SET estado='en_curso',token=gen_random_uuid(),intentos=intentos+1,lease_hasta=now()+interval '15 minutes' WHERE id=c.id RETURNING * INTO c;
  RETURN jsonb_build_object('resultado','tomada','cuadro_id',c.id,'solicitud_id',c.solicitud_id,'token',c.token,'intento',c.intentos);
 WHEN 'entrada_e5' THEN
  SELECT * INTO c FROM public.e5_cuadros WHERE id=(p->>'cuadro_id')::uuid;
  IF c.id IS NULL OR c.estado<>'en_curso' OR c.token IS DISTINCT FROM (p->>'token')::uuid THEN RETURN jsonb_build_object('resultado','intento_vencido'); END IF;
  SELECT * INTO h FROM public.e4_homologaciones WHERE id=c.homologacion_id;
  RETURN jsonb_build_object('resultado','entrada','cuadro_id',c.id,'revision',c.revision,'solicitud_id',c.solicitud_id,
   'homologacion_id',h.id,'estado_revision',h.estado_revision,'homologacion',h.resultado,'tipo_cambio',c.tipo_cambio,
   'solicitud',(SELECT jsonb_build_object('codigo',s.codigo,'nombre',s.nombre,'proyecto',pr.codigo) FROM public.solicitudes_cotizacion s JOIN public.proyectos pr ON pr.id=s.proyecto_id WHERE s.id=c.solicitud_id),
   'plantilla',(SELECT jsonb_build_object('documento_id',d.id,'nombre_original',d.nombre_original,'storage_file_id',d.storage_file_id)
     FROM public.documentos d WHERE d.solicitud_id=c.solicitud_id AND d.tipo='plantilla_comparativo' ORDER BY d.created_at DESC LIMIT 1));
 WHEN 'guardar_e5' THEN
  SELECT * INTO c FROM public.e5_cuadros WHERE id=(p->>'cuadro_id')::uuid FOR UPDATE;
  IF c.id IS NULL OR c.estado<>'en_curso' OR c.token IS DISTINCT FROM (p->>'token')::uuid THEN RETURN jsonb_build_object('resultado','intento_vencido'); END IF;
  IF p->>'estado' NOT IN ('borrador','validado') THEN RAISE EXCEPTION 'Estado del cuadro no válido'; END IF;
  UPDATE public.e5_cuadros SET estado=p->>'estado',nombre_archivo=p->>'nombre_archivo',storage_file_id=(p->>'storage_file_id')::uuid,
   validacion=p->'validacion',finished_at=now(),token=NULL,lease_hasta=NULL,error=NULL WHERE id=c.id;
  INSERT INTO public.notificaciones(usuario_id,solicitud_id,proveedor_id,tipo,titulo,mensaje,datos,dedupe_key)
   VALUES(c.solicitado_por,c.solicitud_id,NULL,'cuadro_listo','Cuadro comparativo (E5) listo',
    CASE WHEN p->>'estado'='validado' THEN 'El cuadro comparativo está validado y listo para descargar.'
         ELSE 'El cuadro comparativo se generó como borrador: tiene pendientes o comprobaciones sin cumplir.' END,
    jsonb_build_object('cuadro_id',c.id,'estado',p->>'estado','color',CASE WHEN p->>'estado'='validado' THEN 'azul' ELSE 'ambar' END),
    'e5:'||c.id) ON CONFLICT(dedupe_key) DO NOTHING;
  RETURN jsonb_build_object('resultado','guardado','cuadro_id',c.id);
 WHEN 'fallo_e5' THEN
  SELECT * INTO c FROM public.e5_cuadros WHERE id=(p->>'cuadro_id')::uuid FOR UPDATE;
  IF c.id IS NULL OR c.estado<>'en_curso' OR c.token IS DISTINCT FROM (p->>'token')::uuid THEN RETURN jsonb_build_object('resultado','intento_vencido'); END IF;
  IF c.intentos>=3 OR NOT coalesce((p->>'recuperable')::boolean,true) THEN
   UPDATE public.e5_cuadros SET estado='error',error=left(coalesce(p->>'error','Error sin detalle'),1500),finished_at=now(),token=NULL,lease_hasta=NULL WHERE id=c.id;
   INSERT INTO public.notificaciones(usuario_id,solicitud_id,proveedor_id,tipo,titulo,mensaje,datos,dedupe_key)
    VALUES(c.solicitado_por,c.solicitud_id,NULL,'cuadro_error','No se pudo generar el cuadro','El cuadro comparativo (E5) no terminó. Revisa el detalle o vuelve a solicitarlo.',
     jsonb_build_object('cuadro_id',c.id,'color','rojo'),'e5-error:'||c.id) ON CONFLICT(dedupe_key) DO NOTHING;
   RETURN jsonb_build_object('resultado','error_definitivo');
  END IF;
  UPDATE public.e5_cuadros SET estado='pendiente',error=left(coalesce(p->>'error','Error sin detalle'),1500),token=NULL,lease_hasta=NULL WHERE id=c.id;
  RETURN jsonb_build_object('resultado','reintento_pendiente');
 ELSE RAISE EXCEPTION 'Operación E4/E5 desconocida: %',p_operacion;
 END CASE;
END;$f$;
REVOKE ALL ON FUNCTION public.e4_operar(text,jsonb) FROM PUBLIC;
COMMIT;
