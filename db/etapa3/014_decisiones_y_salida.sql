BEGIN;
-- La confirmación de E2 sigue usando su sesión; la aceptación final pasa por E3.4.
CREATE OR REPLACE FUNCTION public.validar_estado_correo_proveedor() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE sesion jsonb;actor uuid;actor_e3 uuid;
BEGIN
 BEGIN
  sesion:=nullif(current_setting('hasura.user',true),'')::jsonb;
  IF sesion->>'x-hasura-role'='user' THEN actor:=nullif(sesion->>'x-hasura-user-id','')::uuid; END IF;
  actor_e3:=nullif(current_setting('costflow.e3_actor',true),'')::uuid;
 EXCEPTION WHEN OTHERS THEN actor:=null;actor_e3:=null;END;
 actor:=coalesce(actor_e3,actor);
 IF actor IS NOT NULL THEN
  new.origen_estado:='usuario';new.estado_asignado_por:=actor;new.estado_asignado_at:=now();
 ELSIF tg_op='INSERT' THEN
  new.origen_estado:='agente';new.estado_asignado_por:=null;new.estado_asignado_at:=coalesce(new.estado_asignado_at,now());
 END IF;
 IF new.estado_correo='cotizacion_o_ficha_tecnica_aceptada_final' THEN
  IF actor_e3 IS NULL THEN RAISE EXCEPTION 'Acepta una versión procesada mediante el flujo de decisiones del especialista'; END IF;
  IF NOT EXISTS(SELECT 1 FROM public.versiones_cotizacion v JOIN public.e3_resultados r ON r.version_id=v.id
   WHERE v.correo_id=new.id AND v.estado_procesamiento IN ('completado','completado_con_observaciones')) THEN
   RAISE EXCEPTION 'La versión no terminó de procesarse';
  END IF;
 END IF;
 RETURN new;
END;$$;
CREATE OR REPLACE FUNCTION public.e3_decidir(p_usuario uuid,p jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $f$
DECLARE
 v public.versiones_cotizacion%ROWTYPE;o public.e3_observaciones%ROWTYPE;a public.e3_decisiones%ROWTYPE;
 version_elegida uuid;obs_elegida uuid;id_accion uuid;tipo_accion text;motivo text;medio text;entrada_peticion jsonb;respuesta jsonb;ids uuid[];
BEGIN
 tipo_accion:=p->>'accion';motivo:=nullif(btrim(p->>'motivo'),'');
 medio:=lower(translate(nullif(btrim(p->>'medio'),''),'óÓ','oO'));
 IF tipo_accion NOT IN ('aceptar_version','descartar_observacion','solicitar_aclaracion','reintentar') OR tipo_accion IS NULL THEN
  RETURN jsonb_build_object('ok',false,'http_code',400,'mensaje','Acción no válida.'); END IF;
 IF tipo_accion='descartar_observacion' THEN
  obs_elegida:=(p->>'observacion_id')::uuid;
  SELECT * INTO o FROM public.e3_observaciones WHERE id=obs_elegida;
  IF o.id IS NULL THEN RETURN jsonb_build_object('ok',false,'http_code',404,'mensaje','La observación no existe.'); END IF;
  version_elegida:=o.version_id;
 ELSE version_elegida:=(p->>'version_id')::uuid;END IF;
 SELECT * INTO v FROM public.versiones_cotizacion WHERE id=version_elegida;
 IF v.id IS NULL THEN RETURN jsonb_build_object('ok',false,'http_code',404,'mensaje','La versión no existe.'); END IF;
 IF NOT public.e3_acceso(p_usuario,v.solicitud_id) THEN RETURN jsonb_build_object('ok',false,'http_code',403,'mensaje','No tienes acceso a esta solicitud.'); END IF;
 -- La exclusión es por solicitud/proveedor, no por el número documental elegido.
 PERFORM pg_advisory_xact_lock(hashtextextended(v.solicitud_id::text||v.proveedor_id::text,0));
 SELECT * INTO v FROM public.versiones_cotizacion WHERE id=version_elegida FOR UPDATE;
 IF p->>'solicitud_id' IS NOT NULL AND (p->>'solicitud_id')::uuid<>v.solicitud_id
  OR p->>'proveedor_id' IS NOT NULL AND (p->>'proveedor_id')::uuid<>v.proveedor_id THEN
  RETURN jsonb_build_object('ok',false,'http_code',400,'mensaje','La versión no corresponde a esa solicitud y proveedor.'); END IF;
 IF tipo_accion IN ('descartar_observacion','solicitar_aclaracion') AND motivo IS NULL THEN RETURN jsonb_build_object('ok',false,'http_code',400,'mensaje','El motivo es obligatorio.'); END IF;
 IF length(motivo)>4000 THEN RETURN jsonb_build_object('ok',false,'http_code',400,'mensaje','El motivo supera los 4000 caracteres.'); END IF;
 IF tipo_accion='solicitar_aclaracion' AND (medio IS NULL OR medio NOT IN ('correo','llamada','whatsapp','reunion','otro')) THEN RETURN jsonb_build_object('ok',false,'http_code',400,'mensaje','Selecciona un medio válido.'); END IF;
 entrada_peticion:=jsonb_build_object('accion',tipo_accion,'version_id',v.id,'observacion_id',obs_elegida,'usuario_id',p_usuario,'motivo',motivo,'medio',medio,'observacion_ids',p->'observacion_ids');
 id_accion:=coalesce((p->>'accion_id')::uuid,gen_random_uuid());
 SELECT * INTO a FROM public.e3_decisiones WHERE id=id_accion;
 IF a.id IS NOT NULL THEN
  IF a.entrada IS DISTINCT FROM entrada_peticion THEN RETURN jsonb_build_object('ok',false,'http_code',409,'mensaje','Ese identificador ya se utilizó para otra decisión.'); END IF;
  RETURN a.resultado||jsonb_build_object('repetida',true);
 END IF;
 IF tipo_accion='aceptar_version' THEN
  IF v.estado='anulada' OR v.correo_id IS NULL OR v.estado_procesamiento NOT IN ('completado','completado_con_observaciones')
   OR NOT EXISTS(SELECT 1 FROM public.e3_resultados WHERE version_id=v.id)
   OR NOT EXISTS(SELECT 1 FROM public.correos_proveedor WHERE id=v.correo_id AND origen_estado='usuario'
    AND estado_correo IN ('cotizacion_o_ficha_tecnica_recibida','cotizacion_o_ficha_tecnica_aceptada_final')) THEN
   RETURN jsonb_build_object('ok',false,'http_code',409,'mensaje','Selecciona una versión documental procesada correctamente.'); END IF;
  IF EXISTS(SELECT 1 FROM public.e3_observaciones WHERE version_id=v.id AND requiere_aclaracion AND estado IN ('pendiente','aclaracion_solicitada')) THEN
   RETURN jsonb_build_object('ok',false,'http_code',409,'mensaje','Hay observaciones sin resolver que requieren aclaración, independientemente de su severidad.'); END IF;
  IF v.es_final AND EXISTS(SELECT 1 FROM public.correos_proveedor WHERE id=v.correo_id AND estado_correo='cotizacion_o_ficha_tecnica_aceptada_final') THEN
   RETURN jsonb_build_object('ok',true,'http_code',200,'accion',tipo_accion,'version_id',v.id,'repetida',true,'mensaje','Esta versión ya es la final.'); END IF;
  PERFORM set_config('costflow.e3_actor',p_usuario::text,true);
  PERFORM set_config('hasura.user',jsonb_build_object('x-hasura-role','user','x-hasura-user-id',p_usuario)::text,true);
  UPDATE public.correos_proveedor c SET estado_correo='cotizacion_o_ficha_tecnica_recibida'
   FROM public.versiones_cotizacion anterior WHERE c.id=anterior.correo_id AND anterior.solicitud_id=v.solicitud_id
   AND anterior.proveedor_id=v.proveedor_id AND anterior.id<>v.id AND c.estado_correo='cotizacion_o_ficha_tecnica_aceptada_final';
  UPDATE public.versiones_cotizacion SET es_final=false WHERE solicitud_id=v.solicitud_id AND proveedor_id=v.proveedor_id AND id<>v.id AND es_final;
  UPDATE public.versiones_cotizacion SET es_final=true,estado='vigente' WHERE id=v.id;
  UPDATE public.correos_proveedor SET estado_correo='cotizacion_o_ficha_tecnica_aceptada_final' WHERE id=v.correo_id;
  -- No se cambia el resultado, la lectura ni el estado técnico de la final anterior.
  respuesta:=jsonb_build_object('mensaje','La versión fue aceptada como final.','es_final',true);
 ELSIF tipo_accion='descartar_observacion' THEN
  SELECT * INTO o FROM public.e3_observaciones WHERE id=obs_elegida FOR UPDATE;
  IF o.estado='descartada' THEN RETURN jsonb_build_object('ok',true,'http_code',200,'accion',tipo_accion,'version_id',v.id,'repetida',true,'mensaje','La observación ya fue descartada.'); END IF;
  UPDATE public.e3_observaciones SET estado='descartada',motivo_descarte=motivo,decidido_por=p_usuario,decidido_at=now() WHERE id=o.id;
  respuesta:=jsonb_build_object('mensaje','Observación descartada con motivo.','observacion_id',o.id);
 ELSIF tipo_accion='solicitar_aclaracion' THEN
  ids:=ARRAY(SELECT jsonb_array_elements_text(coalesce(p->'observacion_ids','[]'::jsonb)))::uuid[];
  IF EXISTS(SELECT 1 FROM unnest(ids) i WHERE NOT EXISTS(SELECT 1 FROM public.e3_observaciones WHERE id=i AND version_id=v.id AND estado<>'descartada')) THEN
   RETURN jsonb_build_object('ok',false,'http_code',400,'mensaje','Alguna observación no corresponde a la versión o ya está descartada.'); END IF;
  IF p->>'accion_id' IS NULL THEN
   SELECT * INTO a FROM public.e3_decisiones WHERE version_id=v.id AND accion=tipo_accion AND entrada=entrada_peticion ORDER BY created_at DESC LIMIT 1;
   IF a.id IS NOT NULL THEN RETURN a.resultado||jsonb_build_object('repetida',true); END IF;
  END IF;
  respuesta:=jsonb_build_object('mensaje','Gestión de aclaración registrada. No se envió ningún correo.','correo_enviado',false);
 ELSE
  IF v.estado_procesamiento='reintento_pendiente' AND v.e3_intentos=0 THEN
   RETURN jsonb_build_object('ok',true,'http_code',200,'accion',tipo_accion,'version_id',v.id,'repetida',true,'mensaje','El reintento ya está autorizado y pendiente.'); END IF;
  IF v.e3_legado AND v.estado_procesamiento='pendiente' THEN
   IF NOT EXISTS(SELECT 1 FROM public.correos_proveedor WHERE id=v.correo_id AND origen_estado='usuario' AND estado_asignado_por IS NOT NULL
    AND estado_correo IN ('cotizacion_o_ficha_tecnica_recibida','cotizacion_o_ficha_tecnica_aceptada_final')) THEN
    RETURN jsonb_build_object('ok',false,'http_code',409,'mensaje','Confirma primero el correo histórico como documental en E2.'); END IF;
   UPDATE public.versiones_cotizacion SET e3_fase=CASE WHEN EXISTS(SELECT 1 FROM public.documentos WHERE version_id=v.id) THEN 'lectura' ELSE 'recepcion' END WHERE id=v.id RETURNING * INTO v;
  ELSIF v.estado_procesamiento NOT IN ('error_procesamiento','reintento_pendiente') THEN RETURN jsonb_build_object('ok',false,'http_code',409,'mensaje','La versión no tiene un error pendiente de reintento.'); END IF;
  UPDATE public.versiones_cotizacion SET estado_procesamiento='reintento_pendiente',e3_intentos=0,e3_ciclo=e3_ciclo+1,
   e3_proximo_intento=now(),e3_token=null,e3_lease_hasta=null WHERE id=v.id;
  IF v.e3_fase='recepcion' THEN INSERT INTO public.e3_eventos(correo_id) VALUES(v.correo_id)
   ON CONFLICT(correo_id) DO UPDATE SET estado='pendiente',disponible_at=now(),lease_hasta=null; END IF;
  respuesta:=jsonb_build_object('mensaje','Reintento autorizado. Se conservó el historial anterior.','nuevo_ciclo',v.e3_ciclo+1);
 END IF;
 respuesta:=respuesta||jsonb_build_object('ok',true,'http_code',200,'accion',tipo_accion,'version_id',v.id,'correo_id',v.correo_id,'usuario_id',p_usuario,'fecha',now(),'accion_id',id_accion,'repetida',false);
 INSERT INTO public.e3_decisiones(id,version_id,correo_id,usuario_id,accion,motivo,medio,observacion_id,entrada,resultado)
  VALUES(id_accion,v.id,v.correo_id,p_usuario,tipo_accion,motivo,medio,obs_elegida,entrada_peticion,respuesta);
 IF tipo_accion='solicitar_aclaracion' THEN
  INSERT INTO public.e3_aclaraciones(version_id,decision_id,usuario_id,motivo,medio,observacion_ids) VALUES(v.id,id_accion,p_usuario,motivo,medio,ids);
  UPDATE public.e3_observaciones SET estado='aclaracion_solicitada',decidido_por=p_usuario,decidido_at=now() WHERE id=ANY(ids);
 END IF;
 RETURN respuesta;
EXCEPTION WHEN invalid_text_representation THEN
 RETURN jsonb_build_object('ok',false,'http_code',400,'mensaje','Algún identificador no es un UUID válido.');
WHEN raise_exception OR check_violation OR foreign_key_violation THEN
 RETURN jsonb_build_object('ok',false,'http_code',409,'mensaje',SQLERRM);
END;$f$;
REVOKE ALL ON FUNCTION public.e3_decidir(uuid,jsonb) FROM PUBLIC;
-- Retira la decisión anterior que obligaba a aceptar solo la versión más reciente.
CREATE OR REPLACE FUNCTION public.costflow_accion_especialista_n8n_v1(p_id uuid,p_usuario uuid,p_accion text,p_version uuid,p_observacion uuid,p_motivo text,p_medio text)
RETURNS jsonb LANGUAGE sql AS $$ SELECT jsonb_build_object('ok',false,'http_code',409,'mensaje','Este servicio fue reemplazado por E3.4 con las reglas del 27/10/2026.'); $$;
REVOKE ALL ON FUNCTION public.costflow_accion_especialista_n8n_v1(uuid,uuid,text,uuid,uuid,text,text) FROM PUBLIC;
CREATE OR REPLACE VIEW public.e3_bandeja_versiones AS
 SELECT v.id AS version_id,v.correo_id,v.solicitud_id,v.proveedor_id,v.version AS numero_version,v.es_final,
 v.estado_procesamiento,v.e3_intentos AS intentos,v.e3_legado AS legado,c.recibido_at,c.estado_correo,
 CASE WHEN v.e3_error IS NOT NULL THEN 'La lectura no terminó. Revisa los archivos o solicita un reintento.' END AS error_visible,
 coalesce((SELECT jsonb_agg(jsonb_build_object('documento_id',d.id,'nombre_original',d.nombre_original,'mime_type',d.mime_type)
  ORDER BY d.created_at,d.id) FROM public.documentos d WHERE d.version_id=v.id),'[]'::jsonb) AS documentos
 FROM public.versiones_cotizacion v JOIN public.correos_proveedor c ON c.id=v.correo_id;
CREATE OR REPLACE VIEW public.e3_versiones_estructuradas AS
 SELECT v.id AS version_id,v.correo_id,v.solicitud_id,v.proveedor_id,v.version AS numero_version,v.es_final,
 v.estado_procesamiento,
 r.resultado || jsonb_build_object('es_final',v.es_final,'estado_procesamiento',v.estado_procesamiento,
 'observaciones',coalesce((SELECT jsonb_agg(to_jsonb(o)||jsonb_build_object('observacion_id',o.id) ORDER BY o.created_at,o.id) FROM public.e3_observaciones o WHERE o.version_id=v.id),'[]'::jsonb),
 'decisiones',coalesce((SELECT jsonb_agg(to_jsonb(d) ORDER BY d.created_at) FROM public.e3_decisiones d WHERE d.version_id=v.id),'[]'::jsonb)) AS resultado
 FROM public.versiones_cotizacion v JOIN public.e3_resultados r ON r.version_id=v.id;
CREATE OR REPLACE VIEW public.e3_finales_e4 AS
 SELECT DISTINCT ON (v.solicitud_id,v.proveedor_id) v.*
 FROM public.e3_versiones_estructuradas v JOIN public.correos_proveedor c ON c.id=v.correo_id
 WHERE v.es_final AND c.estado_correo='cotizacion_o_ficha_tecnica_aceptada_final'
 AND v.estado_procesamiento IN ('completado','completado_con_observaciones')
 ORDER BY v.solicitud_id,v.proveedor_id,c.recibido_at DESC,c.id DESC;
CREATE OR REPLACE FUNCTION public.e3_proteger_cambio_final() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (tg_op='INSERT' AND new.es_final) OR (tg_op='UPDATE' AND old.es_final IS DISTINCT FROM new.es_final) THEN
  IF nullif(current_setting('costflow.e3_actor',true),'') IS NULL THEN
   RAISE EXCEPTION 'El cambio de versión final requiere una decisión autenticada mediante E3.4';
  END IF;
 END IF;
 RETURN new;
END;$$;
DROP TRIGGER IF EXISTS e3_final_solo_decision ON public.versiones_cotizacion;
CREATE TRIGGER e3_final_solo_decision BEFORE INSERT OR UPDATE OF es_final ON public.versiones_cotizacion
 FOR EACH ROW EXECUTE FUNCTION public.e3_proteger_cambio_final();
CREATE OR REPLACE FUNCTION public.e3_detectar_finales_inconsistentes() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (SELECT count(*) FROM public.versiones_cotizacion WHERE solicitud_id=new.solicitud_id AND proveedor_id=new.proveedor_id AND es_final)>1 THEN
  INSERT INTO public.e3_inconsistencias(solicitud_id,proveedor_id,tipo,detalle)
   VALUES(new.solicitud_id,new.proveedor_id,'multiples_finales',jsonb_build_object('regla_e4','correo final más reciente'));
 END IF;RETURN new;
END;$$;
DROP TRIGGER IF EXISTS e3_comprobar_finales ON public.versiones_cotizacion;
CREATE TRIGGER e3_comprobar_finales AFTER INSERT OR UPDATE OF es_final ON public.versiones_cotizacion FOR EACH ROW EXECUTE FUNCTION public.e3_detectar_finales_inconsistentes();
INSERT INTO public.e3_inconsistencias(solicitud_id,proveedor_id,tipo,detalle)
 SELECT solicitud_id,proveedor_id,'multiples_finales',jsonb_build_object('versiones',jsonb_agg(id)) FROM public.versiones_cotizacion WHERE es_final GROUP BY solicitud_id,proveedor_id HAVING count(*)>1;
COMMIT;
