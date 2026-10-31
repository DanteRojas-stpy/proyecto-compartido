-- 019: el especialista ve el motivo real por el que el cuadro (E5) no terminó (por ejemplo, «faltan bloques en la plantilla»).
-- Los mensajes los escribe el sistema en español; se limitan a 300 caracteres. Requiere 017. Se puede repetir.
BEGIN;

CREATE OR REPLACE VIEW public.e4_estado_solicitud AS
 SELECT s.id AS solicitud_id,
  (SELECT count(*) FROM public.e3_finales_e4 f WHERE f.solicitud_id=s.id)::integer AS finales_e3,
  e.estado AS e4_estado,e.created_at AS e4_solicitada_at,
  CASE WHEN e.error IS NOT NULL THEN 'La homologación no terminó. Vuelve a solicitarla.' END AS e4_error,
  h.id AS homologacion_id,h.estado_revision,h.created_at AS homologada_at,h.modelo AS e4_modelo,
  c.id AS cuadro_id,c.estado AS e5_estado,c.revision AS e5_revision,c.nombre_archivo,c.storage_file_id AS cuadro_storage_file_id,c.created_at AS cuadro_at,
  CASE WHEN c.error IS NOT NULL THEN left(c.error,300) END AS e5_error
 FROM public.solicitudes_cotizacion s
 LEFT JOIN LATERAL (SELECT * FROM public.e4_ejecuciones x WHERE x.solicitud_id=s.id ORDER BY x.created_at DESC LIMIT 1) e ON true
 LEFT JOIN LATERAL (SELECT * FROM public.e4_homologaciones x WHERE x.solicitud_id=s.id ORDER BY x.created_at DESC LIMIT 1) h ON true
 LEFT JOIN LATERAL (SELECT * FROM public.e5_cuadros x WHERE x.solicitud_id=s.id ORDER BY x.created_at DESC LIMIT 1) c ON true;
COMMIT;
