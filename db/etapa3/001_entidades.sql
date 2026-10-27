-- Aplicar después de la migración 010 de E2. No elimina cotizaciones históricas.
BEGIN;
CREATE TABLE IF NOT EXISTS public.e3_configuracion (
 id boolean PRIMARY KEY DEFAULT true CHECK(id),
 gemini_habilitado boolean NOT NULL DEFAULT false,
 recepcion_habilitada boolean NOT NULL DEFAULT false,
 modelo text NOT NULL DEFAULT 'gemini-3.8-flash',
 parametros jsonb NOT NULL DEFAULT '{"max_archivo_bytes":50000000,"max_paginas":300,"fragmento_caracteres":400,"solapamiento":60,"contexto_caracteres":24000,"retencion_cache_dias":30}'
);
INSERT INTO public.e3_configuracion(id) VALUES(true) ON CONFLICT DO NOTHING;
ALTER TABLE public.e3_configuracion ADD COLUMN IF NOT EXISTS recepcion_habilitada boolean NOT NULL DEFAULT false;
ALTER TABLE public.versiones_cotizacion
 ADD COLUMN IF NOT EXISTS correo_id uuid REFERENCES public.correos_proveedor(id),
 ADD COLUMN IF NOT EXISTS estado_procesamiento text NOT NULL DEFAULT 'pendiente',
 ADD COLUMN IF NOT EXISTS e3_intentos integer NOT NULL DEFAULT 0,
 ADD COLUMN IF NOT EXISTS e3_ciclo integer NOT NULL DEFAULT 1,
 ADD COLUMN IF NOT EXISTS e3_token uuid,
 ADD COLUMN IF NOT EXISTS e3_lease_hasta timestamptz,
 ADD COLUMN IF NOT EXISTS e3_proximo_intento timestamptz,
 ADD COLUMN IF NOT EXISTS e3_fase text NOT NULL DEFAULT 'recepcion',
 ADD COLUMN IF NOT EXISTS e3_error jsonb,
 ADD COLUMN IF NOT EXISTS e3_legado boolean NOT NULL DEFAULT true;
UPDATE public.versiones_cotizacion v SET correo_id=c.id FROM public.correos_proveedor c
 WHERE v.correo_id IS NULL AND v.gmail_message_id=c.gmail_message_id
 AND v.solicitud_id=c.solicitud_id AND v.proveedor_id=c.proveedor_id;
UPDATE public.documentos d SET correo_id=v.correo_id FROM public.versiones_cotizacion v
 WHERE d.version_id=v.id AND d.correo_id IS NULL AND v.correo_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS e3_version_por_correo ON public.versiones_cotizacion(correo_id) WHERE correo_id IS NOT NULL;
ALTER TABLE public.versiones_cotizacion DROP CONSTRAINT IF EXISTS e3_estado_procesamiento_valido;
ALTER TABLE public.versiones_cotizacion ADD CONSTRAINT e3_estado_procesamiento_valido CHECK(estado_procesamiento IN
 ('pendiente','procesando','completado','completado_con_observaciones','reintento_pendiente','error_procesamiento'));
ALTER TABLE public.documentos ADD COLUMN IF NOT EXISTS sha256 text,
 ADD COLUMN IF NOT EXISTS estado_lectura text NOT NULL DEFAULT 'pendiente',
 ADD COLUMN IF NOT EXISTS e3_detalle jsonb NOT NULL DEFAULT '{}';
CREATE UNIQUE INDEX IF NOT EXISTS e3_documento_hash_version ON public.documentos(version_id,sha256) WHERE sha256 IS NOT NULL;
-- Amplía únicamente los tipos afectados; conserva los tipos y restricciones de E1/E2.
DO $m$
DECLARE r record; expresion text;
BEGIN
 FOR r IN SELECT conname,pg_get_constraintdef(oid) def FROM pg_constraint
   WHERE conrelid='public.documentos'::regclass AND contype='c'
   AND (conname IN ('documentos_tipo_valido','documentos_proveedor_segun_tipo')) LOOP
  IF r.def LIKE '%otro_documento%' THEN CONTINUE; END IF;
  expresion:=regexp_replace(r.def,'^CHECK \((.*)\)$','\1');
  EXECUTE format('ALTER TABLE public.documentos DROP CONSTRAINT %I',r.conname);
  EXECUTE format('ALTER TABLE public.documentos ADD CONSTRAINT %I CHECK ((%s) OR (tipo=''otro_documento'' AND proveedor_id IS NOT NULL AND correo_id IS NOT NULL))',r.conname,expresion);
 END LOOP;
 FOR r IN SELECT conname,pg_get_constraintdef(oid) def FROM pg_constraint
   WHERE conrelid='public.notificaciones'::regclass AND contype='c'
   AND pg_get_constraintdef(oid) LIKE '%tipo%' LOOP
  IF r.def LIKE '%version_lista_revision%' THEN CONTINUE; END IF;
  expresion:=regexp_replace(r.def,'^CHECK \((.*)\)$','\1');
  EXECUTE format('ALTER TABLE public.notificaciones DROP CONSTRAINT %I',r.conname);
  EXECUTE format('ALTER TABLE public.notificaciones ADD CONSTRAINT %I CHECK ((%s) OR tipo IN (''version_lista_revision'',''version_con_observaciones'',''nueva_version_disponible'',''error_procesamiento''))',r.conname,expresion);
 END LOOP;
END;$m$;
CREATE TABLE IF NOT EXISTS public.e3_eventos (
 correo_id uuid PRIMARY KEY REFERENCES public.correos_proveedor(id),
 estado text NOT NULL DEFAULT 'pendiente',
 disponible_at timestamptz NOT NULL DEFAULT now(),
 lease_hasta timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.e3_ejecuciones (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),version_id uuid NOT NULL REFERENCES public.versiones_cotizacion(id),
 correo_id uuid NOT NULL REFERENCES public.correos_proveedor(id),ciclo integer NOT NULL,intento integer NOT NULL,
 fase text NOT NULL,estado text NOT NULL,detalle jsonb,started_at timestamptz NOT NULL DEFAULT now(),finished_at timestamptz,
 UNIQUE(version_id,ciclo,intento)
);
CREATE TABLE IF NOT EXISTS public.e3_fragmentos (
 id uuid PRIMARY KEY,version_id uuid NOT NULL REFERENCES public.versiones_cotizacion(id),
 documento_id uuid NOT NULL REFERENCES public.documentos(id),texto text NOT NULL,
 ubicacion jsonb NOT NULL,embedding double precision[],modelo_embedding text,created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS e3_fragmentos_version ON public.e3_fragmentos(version_id,documento_id);
CREATE TABLE IF NOT EXISTS public.e3_resultados (
 version_id uuid PRIMARY KEY REFERENCES public.versiones_cotizacion(id),
 correo_id uuid NOT NULL REFERENCES public.correos_proveedor(id),
 solicitud_id uuid NOT NULL REFERENCES public.solicitudes_cotizacion(id),
 proveedor_id uuid NOT NULL REFERENCES public.proveedores(id),resultado jsonb NOT NULL,
 modelo text NOT NULL,uso_ocr boolean NOT NULL,uso_rag boolean NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.e3_items (
 id uuid PRIMARY KEY,version_id uuid NOT NULL REFERENCES public.versiones_cotizacion(id),
 documento_id uuid REFERENCES public.documentos(id),datos jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS public.e3_especificaciones (
 id uuid PRIMARY KEY,version_id uuid NOT NULL REFERENCES public.versiones_cotizacion(id),
 documento_id uuid REFERENCES public.documentos(id),datos jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS public.e3_evidencias (
 id uuid PRIMARY KEY,version_id uuid NOT NULL REFERENCES public.versiones_cotizacion(id),
 documento_id uuid NOT NULL REFERENCES public.documentos(id),fragmento_id uuid NOT NULL REFERENCES public.e3_fragmentos(id),
 campo text NOT NULL,texto_fuente text NOT NULL,ubicacion jsonb NOT NULL,confianza double precision,
 datos jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS public.e3_observaciones (
 id uuid PRIMARY KEY,version_id uuid NOT NULL REFERENCES public.versiones_cotizacion(id),
 documento_id uuid REFERENCES public.documentos(id),tipo text NOT NULL,descripcion text NOT NULL,
 severidad text NOT NULL CHECK(severidad IN ('alta','media','baja')),
 requiere_aclaracion boolean NOT NULL,estado text NOT NULL DEFAULT 'pendiente'
 CHECK(estado IN ('pendiente','descartada','aclaracion_solicitada')),
 evidencia_ids uuid[] NOT NULL DEFAULT '{}',motivo_descarte text,decidido_por uuid REFERENCES auth.users(id),
 decidido_at timestamptz,created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS e3_observaciones_version ON public.e3_observaciones(version_id,estado);
CREATE TABLE IF NOT EXISTS public.e3_decisiones (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),version_id uuid NOT NULL REFERENCES public.versiones_cotizacion(id),
 correo_id uuid NOT NULL REFERENCES public.correos_proveedor(id),usuario_id uuid NOT NULL REFERENCES auth.users(id),
 accion text NOT NULL,motivo text,medio text,observacion_id uuid REFERENCES public.e3_observaciones(id),
 entrada jsonb NOT NULL,resultado jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.e3_aclaraciones (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),version_id uuid NOT NULL REFERENCES public.versiones_cotizacion(id),
 decision_id uuid NOT NULL UNIQUE REFERENCES public.e3_decisiones(id),usuario_id uuid NOT NULL REFERENCES auth.users(id),
 motivo text NOT NULL,medio text NOT NULL,observacion_ids uuid[] NOT NULL DEFAULT '{}',created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.e3_inconsistencias (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),solicitud_id uuid,proveedor_id uuid,tipo text NOT NULL,
 detalle jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION public.e3_prohibir_borrado_observacion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Las observaciones E3 se conservan; utiliza descarte con motivo'; END;$$;
DROP TRIGGER IF EXISTS e3_observaciones_no_borrar ON public.e3_observaciones;
CREATE TRIGGER e3_observaciones_no_borrar BEFORE DELETE ON public.e3_observaciones
 FOR EACH ROW EXECUTE FUNCTION public.e3_prohibir_borrado_observacion();
CREATE OR REPLACE FUNCTION public.e3_evento_correo_confirmado() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF new.estado_correo='cotizacion_o_ficha_tecnica_recibida' AND new.origen_estado='usuario'
 AND new.estado_asignado_por IS NOT NULL AND jsonb_array_length(new.adjuntos)>0
 AND NOT EXISTS(SELECT 1 FROM public.versiones_cotizacion WHERE correo_id=new.id) THEN
  INSERT INTO public.e3_eventos(correo_id) VALUES(new.id) ON CONFLICT DO NOTHING;
 END IF;
 RETURN new;
END;$$;
DROP TRIGGER IF EXISTS e3_confirmacion_encolar ON public.correos_proveedor;
CREATE TRIGGER e3_confirmacion_encolar AFTER INSERT OR UPDATE OF estado_correo,origen_estado ON public.correos_proveedor
 FOR EACH ROW EXECUTE FUNCTION public.e3_evento_correo_confirmado();
-- No se confirman correos ni se encolan lecturas históricas mediante esta migración.
COMMIT;
