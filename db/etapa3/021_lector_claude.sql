-- 021: el lector de E3 es Claude.
-- Cambia el nombre de la bandera que habilita la lectura (gemini_habilitado -> lector_habilitado), reescribe las funciones
-- que la usan y deja claude-opus-5-5 como modelo predeterminado. Las filas que seguían con un modelo de Gemini pasan a ese modelo.
-- Requiere 012-015. Se puede repetir.
BEGIN;

DO $m$
DECLARE r record;
BEGIN
 IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='e3_configuracion' AND column_name='gemini_habilitado') THEN
  ALTER TABLE public.e3_configuracion RENAME COLUMN gemini_habilitado TO lector_habilitado;
 END IF;
 -- Las funciones se compilan al ejecutarse: se vuelven a crear con el nombre nuevo.
 FOR r IN SELECT p.oid FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
   WHERE n.nspname='public' AND p.prosrc LIKE '%gemini_habilitado%' LOOP
  EXECUTE replace(pg_get_functiondef(r.oid),'gemini_habilitado','lector_habilitado');
 END LOOP;
END;$m$;

ALTER TABLE public.e3_configuracion ALTER COLUMN modelo SET DEFAULT 'claude-opus-5-5';
UPDATE public.e3_configuracion SET modelo='claude-opus-5-5' WHERE modelo LIKE 'gemini%';

COMMIT;
