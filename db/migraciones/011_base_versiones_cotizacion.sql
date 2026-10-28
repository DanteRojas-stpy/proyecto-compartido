-- Base de compatibilidad de E3. Aplicar después de 010 y antes de E3 (012–015).
-- Estructura anterior a E3 comprobada en costflow-dev el 28/10/2026.
-- Las columnas e3_* y de procesamiento se agregan después, en 012_entidades.sql.
-- No copia datos, no crea lecturas históricas y no sustituye tablas existentes.
BEGIN;

CREATE TABLE IF NOT EXISTS public.versiones_cotizacion (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    solicitud_id uuid NOT NULL,
    proveedor_id uuid NOT NULL,
    version integer NOT NULL,
    origen text NOT NULL,
    gmail_message_id text,
    gmail_thread_id text,
    recibido_at timestamptz,
    estado text NOT NULL DEFAULT 'vigente',
    es_final boolean NOT NULL DEFAULT false,
    lista_para_leer boolean NOT NULL DEFAULT false,
    creado_por uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT versiones_solicitud_proveedor_fk
        FOREIGN KEY (solicitud_id, proveedor_id)
        REFERENCES public.solicitud_proveedores(solicitud_id, proveedor_id) ON DELETE CASCADE,
    CONSTRAINT versiones_numero_unico UNIQUE (solicitud_id, proveedor_id, version),
    CONSTRAINT versiones_numero_positivo CHECK (version > 0),
    CONSTRAINT versiones_estado_valido CHECK (estado IN ('vigente', 'reemplazada', 'anulada')),
    CONSTRAINT versiones_origen_valido CHECK (origen IN ('correo', 'manual')),
    CONSTRAINT versiones_final_formalizada CHECK (NOT es_final OR origen = 'correo')
);

CREATE UNIQUE INDEX IF NOT EXISTS versiones_un_correo
    ON public.versiones_cotizacion(solicitud_id, proveedor_id, gmail_message_id)
    WHERE gmail_message_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS versiones_una_final
    ON public.versiones_cotizacion(solicitud_id, proveedor_id) WHERE es_final;

-- Estos campos también existían en Nhost sin una migración en el repositorio.
ALTER TABLE public.documentos
    ADD COLUMN IF NOT EXISTS origen text NOT NULL DEFAULT 'plataforma',
    ADD COLUMN IF NOT EXISTS gmail_message_id text,
    ADD COLUMN IF NOT EXISTS gmail_thread_id text,
    ADD COLUMN IF NOT EXISTS recibido_at timestamptz,
    ADD COLUMN IF NOT EXISTS version_id uuid;

DO $base$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conrelid = 'public.documentos'::regclass
                     AND conname = 'documentos_origen_valido') THEN
        ALTER TABLE public.documentos ADD CONSTRAINT documentos_origen_valido
            CHECK (origen IN ('plataforma', 'correo', 'manual'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conrelid = 'public.documentos'::regclass
                     AND conname = 'documentos_version_id_fkey') THEN
        ALTER TABLE public.documentos ADD CONSTRAINT documentos_version_id_fkey
            FOREIGN KEY (version_id) REFERENCES public.versiones_cotizacion(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger
                   WHERE tgrelid = 'public.versiones_cotizacion'::regclass
                     AND tgname = 'versiones_cotizacion_updated_at' AND NOT tgisinternal) THEN
        CREATE TRIGGER versiones_cotizacion_updated_at
            BEFORE UPDATE ON public.versiones_cotizacion
            FOR EACH ROW EXECUTE FUNCTION public.actualizar_updated_at();
    END IF;
END;
$base$;

CREATE INDEX IF NOT EXISTS documentos_por_version
    ON public.documentos(version_id) WHERE version_id IS NOT NULL;

-- La 002 permitía un solo documento de cada tipo por proveedor/versión.
-- El Nhost actual ya permite varios adjuntos. No se elimina ningún documento.
DROP INDEX IF EXISTS public.documentos_proveedor_version_unique;

COMMIT;
