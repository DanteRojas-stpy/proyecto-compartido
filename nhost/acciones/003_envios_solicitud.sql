-- E2: trazabilidad de los correos enviados a cada proveedor.
-- Ejecutar una sola vez despues de 002_documentos_por_proveedor.sql.

create table public.envios_solicitud (
    id uuid primary key default gen_random_uuid(),
    solicitud_id uuid not null,
    proveedor_id uuid not null,
    destinatario text not null,
    estado text not null default 'pendiente',
    mensaje_id text,
    intentos integer not null default 0,
    enviado_at timestamptz,
    ultimo_error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint envios_solicitud_proveedor_fk
        foreign key (solicitud_id, proveedor_id)
        references public.solicitud_proveedores (solicitud_id, proveedor_id)
        on delete cascade,
    constraint envios_solicitud_destinatario_no_vacio
        check (btrim(destinatario) <> ''),
    constraint envios_solicitud_estado_valido
        check (estado in ('pendiente', 'enviado', 'error', 'respondido')),
    constraint envios_solicitud_intentos_no_negativos
        check (intentos >= 0),
    constraint envios_solicitud_unico
        unique (solicitud_id, proveedor_id)
);

create index envios_solicitud_estado_busqueda
    on public.envios_solicitud (estado, created_at);

create trigger envios_solicitud_updated_at
before update on public.envios_solicitud
for each row execute function public.actualizar_updated_at();
