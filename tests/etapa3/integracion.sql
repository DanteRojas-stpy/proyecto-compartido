-- Prueba contra el esquema instalado. Los registros de prueba se revierten al terminar.
-- No cambia correos, decisiones ni documentos reales; no llama Gmail, Storage ni Gemini.
BEGIN;
CREATE TEMP TABLE e3_prueba_resultados(caso text,correcto boolean) ON COMMIT DROP;
DO $t$
DECLARE
 plantilla public.correos_proveedor%ROWTYPE;c public.correos_proveedor%ROWTYPE;
 usuario uuid;sin_docs uuid;mail1 uuid:=gen_random_uuid();mail2 uuid:=gen_random_uuid();
 v1 uuid;v2 uuid;token1 uuid;token2 uuid;d1 uuid:=gen_random_uuid();d2 uuid:=gen_random_uuid();
 f1 uuid:=gen_random_uuid();f2 uuid:=gen_random_uuid();obs uuid:=gen_random_uuid();ev uuid:=gen_random_uuid();
 respuesta jsonb;contexto jsonb;documentos jsonb;resultado jsonb;prev_int integer;cantidad integer; i integer;
BEGIN
 UPDATE public.e3_configuracion SET recepcion_habilitada=true WHERE id;
 SELECT cp.* INTO plantilla FROM public.correos_proveedor cp JOIN public.solicitudes_cotizacion s ON s.id=cp.solicitud_id
 WHERE s.creado_por IS NOT NULL ORDER BY cp.created_at LIMIT 1;
 IF plantilla.id IS NULL THEN RAISE EXCEPTION 'La prueba necesita una solicitud y un proveedor existentes'; END IF;
 SELECT creado_por INTO usuario FROM public.solicitudes_cotizacion WHERE id=plantilla.solicitud_id;
 PERFORM set_config('hasura.user',jsonb_build_object('x-hasura-role','user','x-hasura-user-id',usuario)::text,true);
 sin_docs:=gen_random_uuid();
 SELECT * INTO c FROM jsonb_populate_record(null::public.correos_proveedor,to_jsonb(plantilla)||jsonb_build_object(
  'id',sin_docs,'gmail_message_id','prueba-e3-'||sin_docs,'adjuntos','[]'::jsonb,
  'estado_correo','cotizacion_o_ficha_tecnica_recibida','origen_estado','usuario','estado_asignado_por',usuario));
 INSERT INTO public.correos_proveedor SELECT c.*;
 respuesta:=public.e3_operar('preparar_correo',jsonb_build_object('correo_id',sin_docs));
 ASSERT respuesta->>'resultado'='rechazado','Se aceptó un correo sin documentos';
 INSERT INTO e3_prueba_resultados VALUES('sin_documentos_no_crea_version',true);
 PERFORM set_config('hasura.user','{}',true);
 c.id:=gen_random_uuid();c.gmail_message_id:='prueba-e3-'||c.id;c.adjuntos:=jsonb_build_array(jsonb_build_object('nombre','prueba.pdf'));
 INSERT INTO public.correos_proveedor SELECT c.*;
 respuesta:=public.e3_operar('preparar_correo',jsonb_build_object('correo_id',c.id));
 ASSERT respuesta->>'resultado'='rechazado','Se procesó un correo sin confirmación del usuario';
 INSERT INTO e3_prueba_resultados VALUES('correo_solo_propuesto_por_agente_no_se_procesa',true);
 PERFORM set_config('hasura.user',jsonb_build_object('x-hasura-role','user','x-hasura-user-id',usuario)::text,true);
 FOR i IN 1..2 LOOP
  SELECT * INTO c FROM jsonb_populate_record(null::public.correos_proveedor,to_jsonb(plantilla)||jsonb_build_object(
   'id',CASE WHEN i=1 THEN mail1 ELSE mail2 END,'gmail_message_id','prueba-e3-'||CASE WHEN i=1 THEN mail1 ELSE mail2 END,
   'adjuntos',jsonb_build_array(jsonb_build_object('nombre','prueba.pdf')),'recibido_at',now()+i*interval '1 second',
   'estado_correo','cotizacion_o_ficha_tecnica_recibida','origen_estado','usuario','estado_asignado_por',usuario));
  INSERT INTO public.correos_proveedor SELECT c.*;
  contexto:=public.e3_operar('preparar_correo',jsonb_build_object('correo_id',c.id));
  ASSERT contexto->>'resultado'='version_creada','No se creó versión de correo confirmado';
  IF i=1 THEN v1:=(contexto->>'version_id')::uuid;token1:=(contexto->>'token')::uuid;
  ELSE v2:=(contexto->>'version_id')::uuid;token2:=(contexto->>'token')::uuid;END IF;
  respuesta:=public.e3_operar('preparar_correo',jsonb_build_object('correo_id',c.id));
  ASSERT respuesta->>'resultado'='version_existente','La segunda recepción duplicó una versión';
 END LOOP;
 ASSERT (SELECT version FROM public.versiones_cotizacion WHERE id=v2)=(SELECT version+1 FROM public.versiones_cotizacion WHERE id=v1),'Numeración no correlativa';
 INSERT INTO e3_prueba_resultados VALUES('una_version_por_correo_y_numeracion',true);
 documentos:=jsonb_build_array(
  jsonb_build_object('documento_id',d1,'storage_file_id',gen_random_uuid(),'nombre_original','Prueba A.pdf','mime_type','application/pdf','tamano_bytes',10,'sha256',repeat('a',64)),
  jsonb_build_object('documento_id',d2,'storage_file_id',gen_random_uuid(),'nombre_original','Prueba B.pdf','mime_type','application/pdf','tamano_bytes',10,'sha256',repeat('b',64)));
 respuesta:=public.e3_operar('registrar_documentos',jsonb_build_object('version_id',v1,'token',token1,'documentos',documentos));
 ASSERT (SELECT count(*) FROM public.documentos WHERE version_id=v1 AND correo_id=mail1)=2,'Archivos fuera de su versión';
 INSERT INTO e3_prueba_resultados VALUES('dos_archivos_misma_version',true);
 UPDATE public.e3_configuracion SET gemini_habilitado=false WHERE id;
 respuesta:=public.e3_operar('iniciar_lectura',jsonb_build_object('version_id',v1));
 ASSERT respuesta->>'resultado'='configuracion_pendiente','No se respetó Gemini pendiente';
 ASSERT (SELECT e3_intentos FROM public.versiones_cotizacion WHERE id=v1)=0,'Se consumió un intento sin clave';
 INSERT INTO e3_prueba_resultados VALUES('sin_gemini_no_consume_intentos',true);
 UPDATE public.e3_configuracion SET gemini_habilitado=true WHERE id;
 contexto:=public.e3_operar('iniciar_lectura',jsonb_build_object('version_id',v1));token1:=(contexto->>'token')::uuid;
 respuesta:=public.e3_operar('guardar_fuentes',jsonb_build_object('version_id',v1,'token',token1,'documentos',jsonb_build_array(
  jsonb_build_object('documento_id',d1,'fragmentos',jsonb_build_array(jsonb_build_object('id',f1,'texto','Equipo de prueba 100','ubicacion',jsonb_build_object('pagina',1)))),
  jsonb_build_object('documento_id',d2,'fragmentos',jsonb_build_array(jsonb_build_object('id',f2,'texto','Ficha técnica de prueba','ubicacion',jsonb_build_object('pagina',1)))))));
 resultado:=jsonb_build_object('version_id',v1,'correo_id',mail1,'solicitud_id',c.solicitud_id,'proveedor_id',c.proveedor_id,
  'documentos',jsonb_build_array(jsonb_build_object('documento_id',d1,'tipo_documental','cotizacion_proveedor'),jsonb_build_object('documento_id',d2,'tipo_documental','ficha_tecnica_proveedor')),
  'items','[]'::jsonb,'especificaciones_tecnicas','[]'::jsonb,'evidencias',jsonb_build_array(jsonb_build_object('id',ev,'fragmento_id',f1,
   'documento_id',d1,'campo','descripcion','texto_fuente','Equipo de prueba 100','ubicacion',jsonb_build_object('pagina',1),'confianza',1)),
  'observaciones',jsonb_build_array(
   jsonb_build_object('observacion_id',obs,'documento_id',d1,'tipo','prueba','descripcion','Requiere aclaración con severidad baja',
     'severidad','baja','requiere_aclaracion',true,'evidencia_ids',jsonb_build_array(ev))),
  'datos_comerciales','{}'::jsonb,'procesamiento',jsonb_build_object('modelo','prueba_sin_ia','uso_ocr',false,'uso_rag',false));
 BEGIN
  PERFORM public.e3_operar('guardar_resultado',jsonb_build_object('version_id',v1,'token',token1,'resultado',resultado-'items'));
  RAISE EXCEPTION 'Se guardó un resultado incompleto';
 EXCEPTION WHEN raise_exception THEN
  IF SQLERRM='Se guardó un resultado incompleto' THEN RAISE; END IF;
 END;
 ASSERT NOT EXISTS(SELECT 1 FROM public.e3_resultados WHERE version_id=v1),'Guardado parcial no revertido';
 respuesta:=public.e3_operar('guardar_resultado',jsonb_build_object('version_id',v1,'token',token1,'resultado',resultado));
 ASSERT respuesta->>'resultado'='procesamiento_completado','El guardado transaccional no terminó';
 respuesta:=public.e3_decidir(usuario,jsonb_build_object('accion','aceptar_version','version_id',v1));
 ASSERT (respuesta->>'http_code')::int=409 AND (respuesta->>'requiere_confirmacion')::boolean AND (respuesta->>'pendientes')::int>=1,'Una observación pendiente no pidió confirmación';
 -- El especialista decide: confirmando, la versión se acepta con sus observaciones. Se deshace para no alterar el resto de la prueba.
 BEGIN
  respuesta:=public.e3_decidir(usuario,jsonb_build_object('accion','aceptar_version','version_id',v1,'aceptar_con_observaciones',true));
  ASSERT (respuesta->>'http_code')::int=200 AND (respuesta->>'observaciones_pendientes_al_aceptar')::int>=1,'Aceptar con observaciones confirmadas no funcionó';
  RAISE EXCEPTION USING ERRCODE='P0099',MESSAGE='deshacer la aceptación de prueba';
 EXCEPTION WHEN SQLSTATE 'P0099' THEN NULL;
 END;
 respuesta:=public.e3_decidir(usuario,jsonb_build_object('accion','descartar_observacion','observacion_id',obs));
 ASSERT (respuesta->>'http_code')::int=400,'Descarte sin motivo aceptado';
 respuesta:=public.e3_decidir(usuario,jsonb_build_object('accion','solicitar_aclaracion','version_id',v1,'motivo','Confirmar dato','medio','correo','observacion_ids',jsonb_build_array(obs)));
 ASSERT respuesta->>'ok'='true' AND respuesta->>'correo_enviado'='false','La aclaración no se registró como gestión sin envío';
 respuesta:=public.e3_decidir(usuario,jsonb_build_object('accion','solicitar_aclaracion','version_id',v1,'motivo','Confirmar dato','medio','correo','observacion_ids',jsonb_build_array(obs)));
 ASSERT respuesta->>'repetida'='true','Una aclaración repetida no fue idempotente';
 respuesta:=public.e3_decidir(usuario,jsonb_build_object('accion','aceptar_version','version_id',v1));
 ASSERT (respuesta->>'http_code')::int=409,'Una aclaración solicitada dejó de bloquear';
 respuesta:=public.e3_decidir(usuario,jsonb_build_object('accion','descartar_observacion','observacion_id',obs,'motivo','Verificado en evidencia'));
 ASSERT respuesta->>'ok'='true','No se pudo descartar con motivo';
 INSERT INTO e3_prueba_resultados VALUES('aclaracion_bloquea_independiente_severidad_y_descarte_auditado',true);
 respuesta:=public.e3_decidir(usuario,jsonb_build_object('accion','aceptar_version','version_id',v1));
 ASSERT respuesta->>'ok'='true',coalesce(respuesta->>'mensaje','Aceptar versión anterior falló');
 ASSERT (SELECT es_final FROM public.versiones_cotizacion WHERE id=v1),'No aceptó la anterior aunque existe una más nueva';
 ASSERT EXISTS(SELECT 1 FROM public.e3_finales_e4 WHERE version_id=v1),'E4 no encuentra la final en su vista';
 INSERT INTO e3_prueba_resultados VALUES('aceptar_version_anterior_y_salida_e4',true);
 -- Simula otra versión ya procesada, para probar cambio de final sin releer.
 UPDATE public.versiones_cotizacion SET e3_fase='lectura',estado_procesamiento='completado',lista_para_leer=true WHERE id=v2;
 INSERT INTO public.e3_resultados(version_id,correo_id,solicitud_id,proveedor_id,resultado,modelo,uso_ocr,uso_rag)
  VALUES(v2,mail2,c.solicitud_id,c.proveedor_id,jsonb_set(jsonb_set(resultado,'{version_id}',to_jsonb(v2)),'{correo_id}',to_jsonb(mail2)),'prueba_sin_ia',false,false);
 SELECT e3_intentos INTO prev_int FROM public.versiones_cotizacion WHERE id=v1;
 respuesta:=public.e3_decidir(usuario,jsonb_build_object('accion','aceptar_version','version_id',v2));
 ASSERT respuesta->>'ok'='true',coalesce(respuesta->>'mensaje','Cambiar final falló');
 ASSERT NOT(SELECT es_final FROM public.versiones_cotizacion WHERE id=v1),'La final anterior siguió activa';
 ASSERT (SELECT estado_correo FROM public.correos_proveedor WHERE id=mail1)='cotizacion_o_ficha_tecnica_recibida','No devolvió el correo anterior a recibido';
 ASSERT (SELECT e3_intentos FROM public.versiones_cotizacion WHERE id=v1)=prev_int,'Se releyó la final anterior';
 ASSERT (SELECT count(*) FROM public.e3_resultados WHERE version_id IN (v1,v2))=2,'Se perdió información';
 INSERT INTO e3_prueba_resultados VALUES('cambiar_final_conserva_anterior_sin_relectura',true);
 respuesta:=public.e3_decidir(gen_random_uuid(),jsonb_build_object('accion','aceptar_version','version_id',v1));
 ASSERT (respuesta->>'http_code')::int=403,'Otra cuenta pudo decidir en la solicitud';
 INSERT INTO e3_prueba_resultados VALUES('sin_acceso_no_puede_decidir',true);
 respuesta:=public.e3_operar('notificar',jsonb_build_object('version_id',v1));
 respuesta:=public.e3_operar('notificar',jsonb_build_object('version_id',v1));
 ASSERT (SELECT count(*) FROM public.notificaciones WHERE datos->>'version_id'=v1::text)=1,'Aviso duplicado';
 INSERT INTO e3_prueba_resultados VALUES('notificacion_unica',true);
 BEGIN
  UPDATE public.versiones_cotizacion SET es_final=true WHERE id=v1;
  RAISE EXCEPTION 'La base permitió dos finales activas';
 EXCEPTION WHEN unique_violation THEN NULL;
 END;
 ASSERT (SELECT count(*) FROM public.e3_finales_e4 WHERE correo_id IN (mail1,mail2))=1,'E4 devolvió dos finales históricas';
 ASSERT EXISTS(SELECT 1 FROM public.e3_finales_e4 WHERE correo_id=mail2),'E4 no eligió la del correo final más reciente';
 ASSERT pg_get_viewdef('public.e3_finales_e4'::regclass) LIKE '%recibido_at DESC%','Falta la defensa de E4 por fecha de correo';
 INSERT INTO e3_prueba_resultados VALUES('e4_unicidad_y_defensiva_por_fecha_correo',true);
 PERFORM set_config('costflow.e3_actor','',true);
 BEGIN
  UPDATE public.versiones_cotizacion SET es_final=false WHERE id=v2;
  RAISE EXCEPTION 'Se modificó la final por fuera de E3.4';
 EXCEPTION WHEN raise_exception THEN
  IF SQLERRM='Se modificó la final por fuera de E3.4' THEN RAISE; END IF;
 END;
 INSERT INTO e3_prueba_resultados VALUES('final_solo_mediante_decision_autenticada',true);
 -- El tercer correo simula fallos recuperables sin documentos reales ni servicios externos.
 c.id:=gen_random_uuid();c.gmail_message_id:='prueba-e3-'||c.id;c.estado_correo:='cotizacion_o_ficha_tecnica_recibida';
 INSERT INTO public.correos_proveedor SELECT c.*;
 contexto:=public.e3_operar('preparar_correo',jsonb_build_object('correo_id',c.id));v2:=(contexto->>'version_id')::uuid;
 FOR i IN 1..3 LOOP
  respuesta:=public.e3_operar('fallo',jsonb_build_object('version_id',v2,'token',contexto->>'token','fase','recepcion','recuperable',true,'error',jsonb_build_object('tipo','prueba_recuperable')));
  ASSERT (respuesta->>'intento')::int=i,'Conteo de intentos incorrecto';
  IF i<3 THEN
   ASSERT respuesta->>'resultado'='reintento_pendiente','No se dejó pendiente el reintento';
   contexto:=public.e3_operar('preparar_correo',jsonb_build_object('correo_id',c.id,'reintento_autorizado',true));
  END IF;
 END LOOP;
 ASSERT respuesta->>'resultado'='error_procesamiento','No terminó después de tres fallos';
 respuesta:=public.e3_operar('notificar',jsonb_build_object('version_id',v2));
 ASSERT EXISTS(SELECT 1 FROM public.notificaciones WHERE datos->>'version_id'=v2::text AND datos->>'color'='rojo'),'Error sin notificación roja';
 respuesta:=public.e3_decidir(usuario,jsonb_build_object('accion','reintentar','version_id',v2));
 ASSERT respuesta->>'ok'='true','No autorizó un nuevo ciclo';
 ASSERT (SELECT count(*) FROM public.e3_ejecuciones WHERE version_id=v2)=3,'Se perdió el historial de errores';
 respuesta:=public.e3_decidir(usuario,jsonb_build_object('accion','reintentar','version_id',v2));
 ASSERT respuesta->>'repetida'='true','Repetir la autorización abrió otro ciclo';
 INSERT INTO e3_prueba_resultados VALUES('tres_intentos_y_reintento_manual_con_historial',true);
END;$t$;
SELECT caso,correcto FROM e3_prueba_resultados ORDER BY caso;
ROLLBACK;
