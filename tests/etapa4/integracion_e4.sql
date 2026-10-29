-- Prueba de e4_operar contra el esquema instalado. Todo es ficticio y se revierte al terminar.
BEGIN;
CREATE TEMP TABLE e4_prueba(caso text,correcto boolean) ON COMMIT DROP;
DO $t$
DECLARE
 usuario uuid:=gen_random_uuid();ajeno uuid:=gen_random_uuid();proyecto uuid:=gen_random_uuid();solicitud uuid:=gen_random_uuid();
 proveedor uuid:=gen_random_uuid();correo uuid:=gen_random_uuid();ver uuid:=gen_random_uuid();
 r jsonb;e jsonb;token uuid;token_viejo uuid;h uuid;cuadro uuid;ejecucion uuid;
BEGIN
 INSERT INTO auth.users VALUES(usuario),(ajeno);
 INSERT INTO public.proyectos(id,responsable_id,codigo,nombre) VALUES(proyecto,usuario,'E4-PRUEBA','Proyecto ficticio');
 INSERT INTO public.solicitudes_cotizacion(id,proyecto_id,creado_por,nombre,moneda,vigencia_dias,fecha_limite,tipo)
  VALUES(solicitud,proyecto,usuario,'Solicitud ficticia','USD',30,current_date+30,'MA');
 INSERT INTO public.proveedores(id,creado_por,nombre) VALUES(proveedor,usuario,'Proveedor ficticio');
 INSERT INTO public.solicitud_proveedores(solicitud_id,proveedor_id) VALUES(solicitud,proveedor);
 INSERT INTO public.correos_proveedor(id,solicitud_id,proveedor_id,gmail_message_id,remitente,recibido_at,estado_correo,origen_estado,estado_asignado_por,adjuntos)
  VALUES(correo,solicitud,proveedor,'e4-'||correo,'proveedor@example.invalid',now(),'cotizacion_o_ficha_tecnica_recibida','usuario',usuario,jsonb_build_array(jsonb_build_object('nombre','x.pdf')));
 INSERT INTO public.versiones_cotizacion(id,solicitud_id,proveedor_id,version,origen,correo_id) VALUES(ver,solicitud,proveedor,1,'correo',correo);

 -- Sin sesión, con usuario ajeno y sin finales, no se puede solicitar.
 r:=public.e4_operar('solicitar_e4',jsonb_build_object('solicitud_id',solicitud));
 ASSERT (r->>'http_code')::int=401,'Se aceptó una solicitud sin sesión';
 INSERT INTO e4_prueba VALUES('sin_sesion_no_solicita',true);
 r:=public.e4_operar('solicitar_e4',jsonb_build_object('solicitud_id',solicitud,'usuario_id_verificado',ajeno));
 ASSERT (r->>'http_code')::int=403,'Un usuario ajeno pudo homologar';
 INSERT INTO e4_prueba VALUES('usuario_ajeno_rechazado',true);
 r:=public.e4_operar('solicitar_e4',jsonb_build_object('solicitud_id',solicitud,'usuario_id_verificado',usuario));
 ASSERT (r->>'http_code')::int=409 AND r->>'mensaje' LIKE '%finales%','Se homologó sin versiones finales';
 INSERT INTO e4_prueba VALUES('sin_finales_no_homologa',true);

 -- La versión aceptada como final es la única entrada de E4.
 PERFORM set_config('costflow.e3_actor',usuario::text,true);
 INSERT INTO public.e3_resultados(version_id,correo_id,solicitud_id,proveedor_id,resultado,modelo,uso_ocr,uso_rag)
  VALUES(ver,correo,solicitud,proveedor,jsonb_build_object('version_id',ver,'datos_comerciales',jsonb_build_object('moneda','USD','total',100)),'prueba',false,false);
 UPDATE public.versiones_cotizacion SET es_final=true,estado_procesamiento='completado',estado='vigente' WHERE id=ver;
 UPDATE public.correos_proveedor SET estado_correo='cotizacion_o_ficha_tecnica_aceptada_final' WHERE id=correo;
 PERFORM set_config('costflow.e3_actor','',true);
 ASSERT (SELECT count(*) FROM public.e3_finales_e4 WHERE solicitud_id=solicitud)=1,'La versión final no llegó a la vista de E4';

 r:=public.e4_operar('solicitar_e4',jsonb_build_object('solicitud_id',solicitud,'usuario_id_verificado',usuario));
 ASSERT (r->>'http_code')::int=200 AND (r->>'finales')::int=1,'No se pudo solicitar E4';
 ejecucion:=(r->>'ejecucion_id')::uuid;
 INSERT INTO e4_prueba VALUES('solicita_con_final_y_sesion',true);
 r:=public.e4_operar('solicitar_e4',jsonb_build_object('solicitud_id',solicitud,'usuario_id_verificado',usuario));
 ASSERT (r->>'http_code')::int=409 AND (r->>'ejecucion_id')::uuid=ejecucion,'Una segunda pulsación creó otra homologación';
 INSERT INTO e4_prueba VALUES('segunda_pulsacion_no_duplica',true);

 r:=public.e4_operar('tomar_e4','{}'::jsonb);
 ASSERT r->>'resultado'='tomada' AND (r->>'ejecucion_id')::uuid=ejecucion,'No se tomó la homologación pendiente';
 token:=(r->>'token')::uuid;
 ASSERT public.e4_operar('tomar_e4','{}'::jsonb)->>'resultado'='vacio','Se tomó dos veces la misma homologación';
 INSERT INTO e4_prueba VALUES('se_toma_una_sola_vez',true);

 r:=public.e4_operar('entrada_e4',jsonb_build_object('ejecucion_id',ejecucion,'token',gen_random_uuid()));
 ASSERT r->>'resultado'='intento_vencido','Un token ajeno obtuvo la entrada';
 r:=public.e4_operar('entrada_e4',jsonb_build_object('ejecucion_id',ejecucion,'token',token));
 ASSERT jsonb_array_length(r#>'{paquete,finales}')=1 AND jsonb_array_length(r#>'{paquete,proveedores}')=1
  AND r#>>'{paquete,solicitud,moneda}'='USD' AND r#>>'{paquete,finales,0,resultado,datos_comerciales,total}'='100','La entrada de E4 no trae lo esperado';
 ASSERT (r#>>'{paquete,partidas}')='[]','Sin itemizado cargado, partidas debe ir vacía';
 INSERT INTO e4_prueba VALUES('entrada_solo_con_token_y_con_finales',true);

 -- Un fallo recuperable devuelve la homologación a la cola; al tercer intento se cierra con aviso.
 r:=public.e4_operar('fallo_e4',jsonb_build_object('ejecucion_id',ejecucion,'token',token,'error','Saturación','recuperable',true));
 ASSERT r->>'resultado'='reintento_pendiente','El primer fallo no volvió a la cola';
 FOR i IN 2..3 LOOP
  r:=public.e4_operar('tomar_e4','{}'::jsonb);token_viejo:=token;token:=(r->>'token')::uuid;
  ASSERT r->>'resultado'='tomada','No se volvió a tomar tras el fallo';
  r:=public.e4_operar('fallo_e4',jsonb_build_object('ejecucion_id',ejecucion,'token',token,'error','Saturación','recuperable',true));
 END LOOP;
 ASSERT r->>'resultado'='error_definitivo','El tercer fallo no cerró la homologación';
 ASSERT (SELECT count(*) FROM public.notificaciones WHERE tipo='homologacion_error' AND solicitud_id=solicitud)=1,'Falta el aviso de error';
 ASSERT public.e4_operar('guardar_e4',jsonb_build_object('ejecucion_id',ejecucion,'token',token_viejo,'estado_revision','requiere_revision','resultado','{}'::jsonb,'version_ids','[]'::jsonb,'huella','x','modelo','m'))->>'resultado'='intento_vencido','Un token viejo guardó resultados';
 INSERT INTO e4_prueba VALUES('fallos_reintentos_y_aviso_de_error',true);

 -- Nueva solicitud: guardar, avisar y generar el cuadro.
 r:=public.e4_operar('solicitar_e4',jsonb_build_object('solicitud_id',solicitud,'usuario_id_verificado',usuario));
 ASSERT (r->>'http_code')::int=200,'No se pudo volver a solicitar E4 tras un error';
 ejecucion:=(r->>'ejecucion_id')::uuid;
 r:=public.e4_operar('tomar_e4','{}'::jsonb);token:=(r->>'token')::uuid;
 r:=public.e4_operar('guardar_e4',jsonb_build_object('ejecucion_id',ejecucion,'token',token,'estado_revision','requiere_revision',
  'resultado',jsonb_build_object('estado_revision','requiere_revision'),'version_ids',jsonb_build_array(ver),'huella','abc','modelo','claude-sonnet-5-5','tokens_entrada',100,'tokens_salida',50));
 ASSERT r->>'resultado'='guardada','No se guardó la homologación';
 h:=(r->>'homologacion_id')::uuid;
 ASSERT (SELECT estado FROM public.e4_ejecuciones WHERE id=ejecucion)='completado','La ejecución no quedó completada';
 ASSERT (SELECT count(*) FROM public.notificaciones WHERE tipo='homologacion_lista' AND usuario_id=usuario)=1,'Falta el aviso al especialista';
 INSERT INTO e4_prueba VALUES('guarda_y_avisa',true);

 ASSERT (SELECT homologacion_id FROM public.e4_estado_solicitud WHERE solicitud_id=solicitud)=h,'La vista de estado no muestra la homologación';
 ASSERT (SELECT estado_revision FROM public.e4_estado_solicitud WHERE solicitud_id=solicitud)='requiere_revision','La vista de estado no muestra la revisión';
 INSERT INTO e4_prueba VALUES('vista_de_estado',true);

 -- E5 exige una homologación previa y no se duplica.
 r:=public.e4_operar('solicitar_e5',jsonb_build_object('solicitud_id',solicitud,'usuario_id_verificado',ajeno));
 ASSERT (r->>'http_code')::int=403,'Un usuario ajeno pidió el cuadro';
 r:=public.e4_operar('solicitar_e5',jsonb_build_object('solicitud_id',solicitud,'usuario_id_verificado',usuario));
 ASSERT (r->>'http_code')::int=200 AND r->>'mensaje' LIKE '%borrador%','Con pendientes debe pedirse como borrador';
 cuadro:=(r->>'cuadro_id')::uuid;
 ASSERT (public.e4_operar('solicitar_e5',jsonb_build_object('solicitud_id',solicitud,'usuario_id_verificado',usuario))->>'http_code')::int=409,'Se duplicó el cuadro';
 INSERT INTO public.documentos(solicitud_id,tipo,nombre_original,storage_file_id,subido_por) VALUES(solicitud,'plantilla_comparativo','plantilla ficticia.xlsx',gen_random_uuid(),usuario);
 r:=public.e4_operar('tomar_e5','{}'::jsonb);token:=(r->>'token')::uuid;
 ASSERT r->>'resultado'='tomada' AND (r->>'cuadro_id')::uuid=cuadro,'No se tomó el cuadro';
 r:=public.e4_operar('entrada_e5',jsonb_build_object('cuadro_id',cuadro,'token',token));
 ASSERT r->>'resultado'='entrada' AND r#>>'{plantilla,nombre_original}'='plantilla ficticia.xlsx' AND (r->>'revision')::int=1
  AND r->>'estado_revision'='requiere_revision','La entrada de E5 no trae la plantilla y la homologación';
 r:=public.e4_operar('guardar_e5',jsonb_build_object('cuadro_id',cuadro,'token',token,'estado','borrador','nombre_archivo','cuadro_rev1.xlsx',
  'storage_file_id',gen_random_uuid(),'validacion',jsonb_build_object('totales_recalculados',true,'pendientes',2)));
 ASSERT r->>'resultado'='guardado','No se guardó el cuadro';
 ASSERT (SELECT e5_estado||':'||nombre_archivo FROM public.e4_estado_solicitud WHERE solicitud_id=solicitud)='borrador:cuadro_rev1.xlsx','La vista no muestra el cuadro';
 ASSERT (SELECT count(*) FROM public.notificaciones WHERE tipo='cuadro_listo' AND usuario_id=usuario)=1,'Falta el aviso del cuadro';
 -- La siguiente revisión no pisa la anterior.
 r:=public.e4_operar('solicitar_e5',jsonb_build_object('solicitud_id',solicitud,'usuario_id_verificado',usuario));
 ASSERT (SELECT revision FROM public.e5_cuadros WHERE id=(r->>'cuadro_id')::uuid)=2,'La revisión del cuadro no es correlativa';
 INSERT INTO e4_prueba VALUES('cuadro_borrador_revision_y_aviso',true);
END;$t$;
SELECT caso||'|'||correcto FROM e4_prueba;
ROLLBACK;
