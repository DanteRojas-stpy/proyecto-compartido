-- Modelo validado con la credencial del equipo el 27/10/2026.
-- Conserva otros modelos elegidos por el equipo y no activa el procesamiento.
BEGIN;
ALTER TABLE public.e3_configuracion
 ALTER COLUMN modelo SET DEFAULT 'gemini-3.5-flash-lite';
UPDATE public.e3_configuracion
 SET modelo='gemini-3.5-flash-lite'
 WHERE id AND modelo='gemini-3.8-flash';
COMMIT;
