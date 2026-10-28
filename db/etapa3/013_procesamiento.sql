BEGIN;
CREATE OR REPLACE FUNCTION public.e3_acceso(p_usuario uuid,p_solicitud uuid) RETURNS boolean
LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM public.solicitudes_cotizacion s LEFT JOIN public.proyectos p ON p.id=s.proyecto_id
 WHERE s.id=p_solicitud AND (s.creado_por=p_usuario OR p.responsable_id=p_usuario));
$$;
CREATE OR REPLACE FUNCTION public.e3_operar(p_operacion text,p jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $f$
DECLARE
 v public.versiones_cotizacion%ROWTYPE;c public.correos_proveedor%ROWTYPE;
 d jsonb;x jsonb;r jsonb;salida jsonb;doc_id uuid;token uuid;tipo_aviso text;numero integer;
 intento integer;estado_nuevo text;fase text;modelo text;ultimo_id uuid;usuario uuid;
BEGIN
 CASE p_operacion
 WHEN 'configuracion' THEN
  SELECT to_jsonb(t) INTO r FROM public.e3_configuracion t WHERE id; RETURN r;
 WHEN 'eventos' THEN
  IF NOT(SELECT recepcion_habilitada FROM public.e3_configuracion WHERE id) THEN RETURN jsonb_build_object('eventos','[]'::jsonb,'resultado','configuracion_pendiente'); END IF;
  UPDATE public.e3_eventos SET estado='pendiente',lease_hasta=null WHERE estado='en_curso' AND lease_hasta<now();
  WITH elegidos AS (SELECT correo_id FROM public.e3_eventos
   WHERE estado='pendiente' AND disponible_at<=now() AND (lease_hasta IS NULL OR lease_hasta<now())
   ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 5),
  tomados AS (UPDATE public.e3_eventos e SET lease_hasta=now()+interval '15 minutes',estado='en_curso'
   FROM elegidos q WHERE e.correo_id=q.correo_id RETURNING e.correo_id)
  SELECT coalesce(jsonb_agg(jsonb_build_object('correo_id',correo_id)),'[]') INTO r FROM tomados;
  RETURN jsonb_build_object('eventos',r);
 WHEN 'preparar_correo' THEN
  IF NOT(SELECT recepcion_habilitada FROM public.e3_configuracion WHERE id) THEN RETURN jsonb_build_object('resultado','configuracion_pendiente','motivo','Falta verificar la credencial de Storage. No se consumió un intento.'); END IF;
  SELECT * INTO c FROM public.correos_proveedor WHERE id=(p->>'correo_id')::uuid FOR UPDATE;
  IF NOT FOUND THEN RETURN jsonb_build_object('resultado','rechazado','motivo','El correo no existe.'); END IF;
  IF c.estado_correo<>'cotizacion_o_ficha_tecnica_recibida' OR c.origen_estado<>'usuario' OR c.estado_asignado_por IS NULL
   OR jsonb_array_length(c.adjuntos)=0 THEN
   UPDATE public.e3_eventos SET estado='terminado',lease_hasta=null WHERE correo_id=c.id;
   RETURN jsonb_build_object('resultado','rechazado','motivo','E3 requiere un correo documental confirmado por el usuario.');
  END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended(c.solicitud_id::text||c.proveedor_id::text,0));
  SELECT * INTO v FROM public.versiones_cotizacion WHERE correo_id=c.id;
  IF FOUND AND NOT(coalesce((p->>'reintento_autorizado')::boolean,false)
    AND v.e3_fase='recepcion' AND v.estado_procesamiento IN ('pendiente','reintento_pendiente')) THEN
   UPDATE public.e3_eventos SET estado='terminado',lease_hasta=null WHERE correo_id=c.id;
   RETURN jsonb_build_object('resultado','version_existente','correo_id',c.id,'version_id',v.id);
  END IF;
  IF v.id IS NULL THEN
   SELECT coalesce(max(version),0)+1 INTO numero FROM public.versiones_cotizacion WHERE solicitud_id=c.solicitud_id AND proveedor_id=c.proveedor_id;
   INSERT INTO public.versiones_cotizacion(solicitud_id,proveedor_id,version,origen,gmail_message_id,gmail_thread_id,recibido_at,correo_id,creado_por,e3_legado)
    VALUES(c.solicitud_id,c.proveedor_id,numero,'correo',c.gmail_message_id,c.gmail_thread_id,c.recibido_at,c.id,c.estado_asignado_por,false) RETURNING * INTO v;
  END IF;
  token:=gen_random_uuid();
  UPDATE public.versiones_cotizacion SET e3_token=token,e3_lease_hasta=now()+interval '15 minutes' WHERE id=v.id;
  RETURN jsonb_build_object('resultado','version_creada','correo_id',c.id,'version_id',v.id,'numero_version',v.version,
   'solicitud_id',c.solicitud_id,'proveedor_id',c.proveedor_id,'gmail_message_id',c.gmail_message_id,'token',token,'correo',to_jsonb(c));
 WHEN 'version' THEN
  SELECT * INTO v FROM public.versiones_cotizacion WHERE id=(p->>'version_id')::uuid;
  IF NOT FOUND THEN RAISE EXCEPTION 'La versión no existe'; END IF;
  SELECT * INTO c FROM public.correos_proveedor WHERE id=v.correo_id;
  SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY t.created_at,t.id),'[]') INTO d FROM public.documentos t WHERE version_id=v.id;
  RETURN jsonb_build_object('version',to_jsonb(v),'correo',to_jsonb(c),'documentos',d);
 WHEN 'registrar_documentos' THEN
  SELECT * INTO v FROM public.versiones_cotizacion WHERE id=(p->>'version_id')::uuid FOR UPDATE;
  IF v.e3_token IS DISTINCT FROM (p->>'token')::uuid OR v.estado_procesamiento IN ('completado','completado_con_observaciones') THEN RAISE EXCEPTION 'Recepción vencida o ya terminada'; END IF;
  SELECT * INTO c FROM public.correos_proveedor WHERE id=v.correo_id;
  IF jsonb_array_length(p->'documentos')=0 THEN RAISE EXCEPTION 'El correo no entregó archivos'; END IF;
  FOR d IN SELECT value FROM jsonb_array_elements(p->'documentos') LOOP
   IF d->>'sha256' !~ '^[a-f0-9]{64}$' THEN RAISE EXCEPTION 'Huella SHA-256 inválida'; END IF;
   INSERT INTO public.documentos(id,solicitud_id,proveedor_id,correo_id,version_id,version,tipo,nombre_original,storage_file_id,mime_type,tamano_bytes,
    subido_por,origen,gmail_message_id,gmail_thread_id,recibido_at,sha256,e3_detalle)
    VALUES((d->>'documento_id')::uuid,v.solicitud_id,v.proveedor_id,c.id,v.id,v.version,'otro_documento',d->>'nombre_original',
     (d->>'storage_file_id')::uuid,d->>'mime_type',(d->>'tamano_bytes')::bigint,c.estado_asignado_por,'correo',c.gmail_message_id,c.gmail_thread_id,c.recibido_at,d->>'sha256',d)
    ON CONFLICT(id) DO NOTHING;
  END LOOP;
  UPDATE public.versiones_cotizacion SET e3_fase='lectura',e3_token=null,e3_lease_hasta=null,lista_para_leer=true WHERE id=v.id;
  UPDATE public.e3_eventos SET estado='terminado',lease_hasta=null WHERE correo_id=c.id;
  RETURN jsonb_build_object('resultado','documentos_registrados','version_id',v.id,'correo_id',c.id);
 WHEN 'iniciar_lectura' THEN
  SELECT * INTO v FROM public.versiones_cotizacion WHERE id=(p->>'version_id')::uuid FOR UPDATE;
  IF v.id IS NULL THEN RAISE EXCEPTION 'La versión no existe'; END IF;
  IF v.estado_procesamiento IN ('completado','completado_con_observaciones') THEN RETURN jsonb_build_object('resultado','ya_completada','version_id',v.id); END IF;
  IF NOT(SELECT gemini_habilitado FROM public.e3_configuracion WHERE id) THEN RETURN jsonb_build_object('resultado','configuracion_pendiente','version_id',v.id,'motivo','Falta configurar Gemini. No se consumió un intento.'); END IF;
  IF v.e3_fase<>'lectura' THEN RAISE EXCEPTION 'La recepción no terminó'; END IF;
  IF v.estado_procesamiento='procesando' AND v.e3_lease_hasta>now() THEN RETURN jsonb_build_object('resultado','en_curso','version_id',v.id); END IF;
  IF v.e3_intentos>=3 THEN RETURN jsonb_build_object('resultado','intentos_agotados','version_id',v.id); END IF;
  SELECT * INTO c FROM public.correos_proveedor WHERE id=v.correo_id;
  IF c.origen_estado<>'usuario' OR c.estado_correo NOT IN ('cotizacion_o_ficha_tecnica_recibida','cotizacion_o_ficha_tecnica_aceptada_final') THEN RAISE EXCEPTION 'El correo dejó de estar confirmado'; END IF;
  token:=gen_random_uuid();
  UPDATE public.versiones_cotizacion SET estado_procesamiento='procesando',e3_intentos=e3_intentos+1,
   e3_token=token,e3_lease_hasta=now()+interval '15 minutes',e3_error=null,e3_legado=false WHERE id=v.id RETURNING * INTO v;
  INSERT INTO public.e3_ejecuciones(id,version_id,correo_id,ciclo,intento,fase,estado)
   VALUES(token,v.id,c.id,v.e3_ciclo,v.e3_intentos,'lectura','procesando');
  RETURN jsonb_build_object('resultado','iniciada','version_id',v.id,'correo_id',c.id,'token',token,'intento',v.e3_intentos,'ciclo',v.e3_ciclo);
 WHEN 'guardar_fuentes' THEN
  SELECT * INTO v FROM public.versiones_cotizacion WHERE id=(p->>'version_id')::uuid FOR UPDATE;
  IF v.e3_token IS DISTINCT FROM (p->>'token')::uuid OR v.estado_procesamiento<>'procesando' THEN RAISE EXCEPTION 'Intento de lectura vencido'; END IF;
  FOR d IN SELECT value FROM jsonb_array_elements(p->'documentos') LOOP
   doc_id:=(d->>'documento_id')::uuid;
   IF NOT EXISTS(SELECT 1 FROM public.documentos WHERE id=doc_id AND version_id=v.id) THEN RAISE EXCEPTION 'Documento de otra versión'; END IF;
   UPDATE public.documentos SET estado_lectura='procesado',sha256=coalesce(sha256,d->>'sha256'),e3_detalle=e3_detalle||(d-'fragmentos') WHERE id=doc_id;
   FOR x IN SELECT value FROM jsonb_array_elements(d->'fragmentos') LOOP
    INSERT INTO public.e3_fragmentos(id,version_id,documento_id,texto,ubicacion,embedding,modelo_embedding)
     VALUES((x->>'id')::uuid,v.id,doc_id,x->>'texto',x->'ubicacion',
      CASE WHEN x->'embedding' IS NOT NULL THEN ARRAY(SELECT jsonb_array_elements_text(x->'embedding'))::double precision[] END,d->>'modelo_embedding')
     ON CONFLICT(id) DO UPDATE SET texto=excluded.texto,ubicacion=excluded.ubicacion,embedding=excluded.embedding;
   END LOOP;
  END LOOP;
  RETURN jsonb_build_object('resultado','fuentes_guardadas');
 WHEN 'renovar_lease' THEN
  UPDATE public.versiones_cotizacion SET e3_lease_hasta=now()+interval '15 minutes'
   WHERE id=(p->>'version_id')::uuid AND e3_token=(p->>'token')::uuid AND estado_procesamiento='procesando';
  IF NOT FOUND THEN RAISE EXCEPTION 'La lectura ya no tiene un intento vigente'; END IF;
  RETURN jsonb_build_object('resultado','lease_renovado');
 WHEN 'guardar_resultado' THEN
  SELECT * INTO v FROM public.versiones_cotizacion WHERE id=(p->>'version_id')::uuid FOR UPDATE;
  IF v.estado_procesamiento IN ('completado','completado_con_observaciones') THEN RETURN jsonb_build_object('resultado','ya_completada','version_id',v.id); END IF;
  IF v.e3_token IS DISTINCT FROM (p->>'token')::uuid OR v.estado_procesamiento<>'procesando' THEN RAISE EXCEPTION 'Intento vencido: no se guardaron datos'; END IF;
  IF NOT EXISTS(SELECT 1 FROM public.correos_proveedor WHERE id=v.correo_id AND origen_estado='usuario' AND estado_correo IN ('cotizacion_o_ficha_tecnica_recibida','cotizacion_o_ficha_tecnica_aceptada_final')) THEN RAISE EXCEPTION 'El correo dejó de estar confirmado'; END IF;
  r:=p->'resultado';
  IF jsonb_typeof(r) IS DISTINCT FROM 'object'
   OR r->>'version_id' IS DISTINCT FROM v.id::text OR r->>'correo_id' IS DISTINCT FROM v.correo_id::text
   OR r->>'solicitud_id' IS DISTINCT FROM v.solicitud_id::text OR r->>'proveedor_id' IS DISTINCT FROM v.proveedor_id::text
   OR jsonb_typeof(r->'datos_comerciales') IS DISTINCT FROM 'object'
   OR jsonb_typeof(r->'procesamiento') IS DISTINCT FROM 'object'
   OR r#>>'{procesamiento,modelo}' IS NULL THEN RAISE EXCEPTION 'Contrato JSON o pertenencia inválidos'; END IF;
  FOREACH tipo_aviso IN ARRAY ARRAY['items','evidencias','documentos','observaciones','especificaciones_tecnicas'] LOOP
   IF jsonb_typeof(r->tipo_aviso) IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'Falta una lista obligatoria del contrato JSON'; END IF;
  END LOOP;
  r:=r||jsonb_build_object('numero_version',v.version,'es_final',v.es_final);
  IF (SELECT count(*) FROM public.documentos WHERE version_id=v.id)<>jsonb_array_length(r->'documentos') THEN RAISE EXCEPTION 'Cobertura documental incompleta'; END IF;
  IF (SELECT count(DISTINCT value->>'documento_id') FROM jsonb_array_elements(r->'documentos'))<>jsonb_array_length(r->'documentos') THEN RAISE EXCEPTION 'Documentos duplicados en el resultado'; END IF;
  FOR d IN SELECT value FROM jsonb_array_elements(r->'evidencias') LOOP
   IF NOT EXISTS(SELECT 1 FROM public.e3_fragmentos f WHERE f.id=(d->>'fragmento_id')::uuid AND f.version_id=v.id AND f.documento_id=(d->>'documento_id')::uuid
     AND position(d->>'texto_fuente' IN f.texto)>0) THEN RAISE EXCEPTION 'Evidencia inexistente o de otra versión'; END IF;
   INSERT INTO public.e3_evidencias(id,version_id,documento_id,fragmento_id,campo,texto_fuente,ubicacion,confianza,datos)
    VALUES((d->>'id')::uuid,v.id,(d->>'documento_id')::uuid,(d->>'fragmento_id')::uuid,d->>'campo',d->>'texto_fuente',d->'ubicacion',(d->>'confianza')::double precision,d);
  END LOOP;
  FOR d IN SELECT value FROM jsonb_array_elements(r->'items') LOOP
   IF NOT EXISTS(SELECT 1 FROM public.documentos WHERE id=(d->>'documento_id')::uuid AND version_id=v.id) THEN RAISE EXCEPTION 'Ítem de otra versión'; END IF;
   INSERT INTO public.e3_items(id,version_id,documento_id,datos) VALUES((d->>'id')::uuid,v.id,(d->>'documento_id')::uuid,d);
  END LOOP;
  FOR d IN SELECT value FROM jsonb_array_elements(r->'especificaciones_tecnicas') LOOP
   IF NOT EXISTS(SELECT 1 FROM public.documentos WHERE id=(d->>'documento_id')::uuid AND version_id=v.id) THEN RAISE EXCEPTION 'Especificación de otra versión'; END IF;
   INSERT INTO public.e3_especificaciones(id,version_id,documento_id,datos) VALUES((d->>'id')::uuid,v.id,(d->>'documento_id')::uuid,d);
  END LOOP;
  FOR d IN SELECT value FROM jsonb_array_elements(r->'documentos') LOOP
   IF NOT EXISTS(SELECT 1 FROM public.documentos WHERE id=(d->>'documento_id')::uuid AND version_id=v.id) THEN RAISE EXCEPTION 'Documento fuera de versión'; END IF;
   IF d->>'tipo_documental' NOT IN ('cotizacion_proveedor','ficha_tecnica_proveedor','anexo_proveedor','otro_documento') THEN RAISE EXCEPTION 'Tipo documental inválido'; END IF;
   UPDATE public.documentos SET tipo=d->>'tipo_documental',estado_lectura='completado',e3_detalle=e3_detalle||d WHERE id=(d->>'documento_id')::uuid;
  END LOOP;
  FOR d IN SELECT value FROM jsonb_array_elements(r->'observaciones') LOOP
   IF d->>'documento_id' IS NOT NULL AND NOT EXISTS(SELECT 1 FROM public.documentos WHERE id=(d->>'documento_id')::uuid AND version_id=v.id) THEN RAISE EXCEPTION 'Observación de otra versión'; END IF;
   IF EXISTS(SELECT 1 FROM jsonb_array_elements_text(d->'evidencia_ids') a WHERE NOT EXISTS(SELECT 1 FROM public.e3_evidencias ee WHERE ee.id=a::uuid AND ee.version_id=v.id)) THEN RAISE EXCEPTION 'Observación con evidencia inexistente'; END IF;
   INSERT INTO public.e3_observaciones(id,version_id,documento_id,tipo,descripcion,severidad,requiere_aclaracion,evidencia_ids)
    VALUES((d->>'observacion_id')::uuid,v.id,(d->>'documento_id')::uuid,d->>'tipo',d->>'descripcion',d->>'severidad',(d->>'requiere_aclaracion')::boolean,
     ARRAY(SELECT jsonb_array_elements_text(d->'evidencia_ids'))::uuid[]);
  END LOOP;
  estado_nuevo:=CASE WHEN jsonb_array_length(r->'observaciones')>0 THEN 'completado_con_observaciones' ELSE 'completado' END;
  r:=jsonb_set(r,'{estado_procesamiento}',to_jsonb(estado_nuevo));
  INSERT INTO public.e3_resultados(version_id,correo_id,solicitud_id,proveedor_id,resultado,modelo,uso_ocr,uso_rag)
   VALUES(v.id,v.correo_id,v.solicitud_id,v.proveedor_id,r,r#>>'{procesamiento,modelo}',(r#>>'{procesamiento,uso_ocr}')::boolean,(r#>>'{procesamiento,uso_rag}')::boolean);
  UPDATE public.versiones_cotizacion SET estado_procesamiento=estado_nuevo,e3_token=null,e3_lease_hasta=null,e3_error=null,e3_proximo_intento=null WHERE id=v.id;
  UPDATE public.e3_ejecuciones SET estado=estado_nuevo,finished_at=now() WHERE id=(p->>'token')::uuid;
  RETURN jsonb_build_object('resultado','procesamiento_completado','version_id',v.id,'correo_id',v.correo_id,'estado_procesamiento',estado_nuevo);
 WHEN 'fallo' THEN
  SELECT * INTO v FROM public.versiones_cotizacion WHERE id=(p->>'version_id')::uuid FOR UPDATE;
  IF v.id IS NULL THEN RAISE EXCEPTION 'Versión inexistente al registrar error'; END IF;
  IF v.estado_procesamiento IN ('completado','completado_con_observaciones') THEN RETURN jsonb_build_object('resultado','ya_completada'); END IF;
  IF p->>'token' IS NOT NULL AND v.e3_token IS DISTINCT FROM (p->>'token')::uuid THEN RETURN jsonb_build_object('resultado','intento_vencido'); END IF;
  intento:=v.e3_intentos;token:=v.e3_token;fase:=coalesce(p->>'fase',v.e3_fase);
  IF NOT EXISTS(SELECT 1 FROM public.e3_ejecuciones WHERE id=token) THEN
   intento:=intento+1;token:=gen_random_uuid();
   INSERT INTO public.e3_ejecuciones(id,version_id,correo_id,ciclo,intento,fase,estado)
    VALUES(token,v.id,v.correo_id,v.e3_ciclo,intento,fase,'procesando');
  END IF;
  estado_nuevo:=CASE WHEN intento>=3 OR NOT coalesce((p->>'recuperable')::boolean,true) THEN 'error_procesamiento' ELSE 'reintento_pendiente' END;
  UPDATE public.e3_ejecuciones SET estado=estado_nuevo,detalle=p->'error',finished_at=now() WHERE id=token;
  UPDATE public.versiones_cotizacion SET estado_procesamiento=estado_nuevo,e3_intentos=intento,e3_error=p->'error',e3_token=null,e3_lease_hasta=null,
   e3_proximo_intento=CASE WHEN estado_nuevo='reintento_pendiente' THEN now()+CASE WHEN intento=1 THEN interval '30 seconds' ELSE interval '120 seconds' END END WHERE id=v.id;
  UPDATE public.e3_eventos SET estado=CASE WHEN estado_nuevo='error_procesamiento' THEN 'fallido' ELSE 'pendiente' END,
   lease_hasta=null,disponible_at=now()+interval '2 minutes' WHERE correo_id=v.correo_id AND fase='recepcion';
  RETURN jsonb_build_object('resultado',estado_nuevo,'version_id',v.id,'correo_id',v.correo_id,'intento',intento);
 WHEN 'recuperar' THEN
  FOR v IN SELECT * FROM public.versiones_cotizacion WHERE e3_fase='recepcion'
   AND estado_procesamiento='pendiente' AND e3_lease_hasta<now() FOR UPDATE SKIP LOCKED LOOP
   PERFORM public.e3_operar('fallo',jsonb_build_object('version_id',v.id,'token',v.e3_token,'fase','recepcion','recuperable',true,
    'error',jsonb_build_object('tipo','recepcion_interrumpida','mensaje','La descarga de adjuntos no terminó a tiempo')));
  END LOOP;
  FOR v IN SELECT * FROM public.versiones_cotizacion WHERE estado_procesamiento='procesando' AND e3_lease_hasta<now() FOR UPDATE SKIP LOCKED LOOP
   PERFORM public.e3_operar('fallo',jsonb_build_object('version_id',v.id,'token',v.e3_token,'recuperable',true,'error',jsonb_build_object('tipo','ejecucion_estancada','mensaje','Venció el tiempo de procesamiento')));
  END LOOP;
  SELECT coalesce(jsonb_agg(jsonb_build_object('version_id',q.id,'correo_id',q.correo_id,'fase',q.e3_fase,'reintento_autorizado',true)),'[]') INTO r
   FROM (SELECT * FROM public.versiones_cotizacion WHERE
    ((estado_procesamiento='reintento_pendiente' AND e3_proximo_intento<=now())
      OR (estado_procesamiento='pendiente' AND e3_fase='lectura' AND NOT e3_legado)) AND e3_intentos<3
    AND (e3_fase='recepcion' OR (SELECT gemini_habilitado FROM public.e3_configuracion WHERE id)) ORDER BY e3_proximo_intento LIMIT 5) q;
  SELECT coalesce(jsonb_agg(jsonb_build_object('version_id',vv.id,'correo_id',vv.correo_id)),'[]') INTO d
   FROM public.versiones_cotizacion vv WHERE vv.estado_procesamiento IN ('error_procesamiento','completado','completado_con_observaciones')
   AND NOT EXISTS(SELECT 1 FROM public.notificaciones n WHERE n.datos->>'version_id'=vv.id::text AND n.tipo IN ('error_procesamiento','version_lista_revision','version_con_observaciones','nueva_version_disponible'));
  RETURN jsonb_build_object('reintentos',r,'definitivos',d);
 WHEN 'notificar' THEN
  SELECT * INTO v FROM public.versiones_cotizacion WHERE id=(p->>'version_id')::uuid;
  SELECT * INTO c FROM public.correos_proveedor WHERE id=v.correo_id;
  IF c.id IS NULL OR jsonb_array_length(c.adjuntos)=0 THEN RETURN jsonb_build_object('resultado','sin_notificacion'); END IF;
  IF v.estado_procesamiento NOT IN ('completado','completado_con_observaciones','error_procesamiento') THEN RETURN jsonb_build_object('resultado','sin_notificacion'); END IF;
  SELECT coalesce(s.creado_por,pr.responsable_id) INTO usuario FROM public.solicitudes_cotizacion s LEFT JOIN public.proyectos pr ON pr.id=s.proyecto_id WHERE s.id=v.solicitud_id;
  IF usuario IS NULL THEN RAISE EXCEPTION 'La solicitud no tiene especialista para la notificación'; END IF;
  tipo_aviso:=CASE WHEN v.estado_procesamiento='error_procesamiento' THEN 'error_procesamiento'
   WHEN EXISTS(SELECT 1 FROM public.e3_resultados rr JOIN public.versiones_cotizacion vv ON vv.id=rr.version_id
    WHERE vv.solicitud_id=v.solicitud_id AND vv.proveedor_id=v.proveedor_id AND vv.version<v.version) THEN 'nueva_version_disponible'
   WHEN EXISTS(SELECT 1 FROM public.e3_observaciones WHERE version_id=v.id AND severidad IN ('alta','media')) THEN 'version_con_observaciones' ELSE 'version_lista_revision' END;
  INSERT INTO public.notificaciones(usuario_id,solicitud_id,proveedor_id,tipo,titulo,mensaje,datos,dedupe_key)
   VALUES(usuario,v.solicitud_id,v.proveedor_id,tipo_aviso,'Versión '||v.version||' de cotización o ficha técnica',
    CASE WHEN tipo_aviso='error_procesamiento' THEN
     CASE WHEN v.e3_intentos>=3 THEN 'No fue posible procesar los archivos después de tres intentos. Revisa el error o solicita un nuevo intento.'
     ELSE 'El archivo presenta un error que impide procesarlo. Revisa el detalle o solicita un nuevo intento.' END
     ELSE 'La información está disponible para la revisión del especialista.' END,
    jsonb_build_object('correo_id',c.id,'version_id',v.id,'color',CASE WHEN tipo_aviso='error_procesamiento' THEN 'rojo' WHEN EXISTS(SELECT 1 FROM public.e3_observaciones WHERE version_id=v.id AND severidad IN ('alta','media')) THEN 'ambar' ELSE 'azul' END,
     'icono',CASE WHEN tipo_aviso='error_procesamiento' THEN 'error' ELSE 'documento' END,'ruta','/versiones/'||v.id,'intentos',v.e3_intentos,'acciones',jsonb_build_array('ver_version','ver_archivo')),
    'e3:'||c.id||':'||v.id||':'||tipo_aviso) ON CONFLICT(dedupe_key) DO NOTHING RETURNING id INTO ultimo_id;
  IF ultimo_id IS NULL THEN SELECT id INTO ultimo_id FROM public.notificaciones WHERE dedupe_key='e3:'||c.id||':'||v.id||':'||tipo_aviso; END IF;
  RETURN jsonb_build_object('resultado','notificacion_registrada','notificacion_id',ultimo_id,'tipo',tipo_aviso);
 WHEN 'decision' THEN
  RETURN public.e3_decidir((p->>'usuario_id_verificado')::uuid,p->'accion');
 WHEN 'documento_accesible' THEN
  SELECT to_jsonb(dd) INTO r FROM public.documentos dd WHERE dd.id=(p->>'documento_id')::uuid
   AND public.e3_acceso((p->>'usuario_id_verificado')::uuid,dd.solicitud_id);
  RETURN coalesce(r,'{}'::jsonb);
 ELSE RAISE EXCEPTION 'Operación interna de E3 no reconocida';
 END CASE;
END;$f$;
REVOKE ALL ON FUNCTION public.e3_operar(text,jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.e3_acceso(uuid,uuid) FROM PUBLIC;
COMMIT;
