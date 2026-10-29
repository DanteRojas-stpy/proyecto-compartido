-- 020: descarga del cuadro (E5) con la sesión del especialista.
-- El Excel lo guarda n8n en Storage y el navegador no puede leerlo directamente. La Function e4-operar (operación descargar_e5)
-- verifica la sesión, usa esta función para comprobar que el cuadro es de una solicitud a la que el usuario tiene acceso
-- y entrega el archivo. Requiere 017. Se puede repetir.
BEGIN;

CREATE OR REPLACE FUNCTION public.e5_cuadro_para_descarga(p_usuario uuid,p_cuadro uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $f$
DECLARE c public.e5_cuadros%ROWTYPE;
BEGIN
 IF p_usuario IS NULL THEN RETURN jsonb_build_object('ok',false,'http_code',401,'mensaje','Inicia sesión para descargar el cuadro.'); END IF;
 SELECT * INTO c FROM public.e5_cuadros WHERE id=p_cuadro;
 IF c.id IS NULL OR NOT public.e3_acceso(p_usuario,c.solicitud_id) THEN
  RETURN jsonb_build_object('ok',false,'http_code',403,'mensaje','No tienes acceso a este cuadro.');
 END IF;
 IF c.estado NOT IN ('borrador','validado') OR c.storage_file_id IS NULL THEN
  RETURN jsonb_build_object('ok',false,'http_code',409,'mensaje','El cuadro todavía no tiene un archivo para descargar.');
 END IF;
 RETURN jsonb_build_object('ok',true,'http_code',200,'storage_file_id',c.storage_file_id,'nombre_archivo',coalesce(c.nombre_archivo,'cuadro-comparativo.xlsx'));
END;$f$;
REVOKE ALL ON FUNCTION public.e5_cuadro_para_descarga(uuid,uuid) FROM PUBLIC;
COMMIT;
