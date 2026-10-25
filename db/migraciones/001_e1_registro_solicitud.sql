-- E1: registro de solicitudes de cotizacion para Nhost.
-- Ejecutar una sola vez en Database > SQL Console.
-- Los permisos de GraphQL y Storage se configuran despues desde Nhost.

create extension if not exists pgcrypto;

create table public.proyectos (
    id uuid primary key default gen_random_uuid(),
    responsable_id uuid not null references auth.users(id) on delete cascade,
    codigo text not null,
    nombre text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint proyectos_codigo_no_vacio check (btrim(codigo) <> ''),
    constraint proyectos_nombre_no_vacio check (btrim(nombre) <> ''),
    constraint proyectos_responsable_codigo_unique unique (responsable_id, codigo)
);

create table public.solicitudes_cotizacion (
    id uuid primary key default gen_random_uuid(),
    proyecto_id uuid not null references public.proyectos(id) on delete cascade,
    creado_por uuid not null references auth.users(id) on delete cascade,
    codigo text not null,
    nombre text not null,
    moneda text not null default 'PEN',
    vigencia_dias integer not null,
    fecha_limite date,
    estado text not null default 'borrador',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint solicitudes_codigo_no_vacio check (btrim(codigo) <> ''),
    constraint solicitudes_nombre_no_vacio check (btrim(nombre) <> ''),
    constraint solicitudes_moneda_valida check (moneda in ('PEN', 'USD')),
    constraint solicitudes_vigencia_positiva check (vigencia_dias > 0),
    constraint solicitudes_estado_valido check (estado in ('borrador', 'lista', 'en_proceso', 'cerrada', 'cancelada')),
    constraint solicitudes_proyecto_codigo_unique unique (proyecto_id, codigo)
);

create table public.proveedores (
    id uuid primary key default gen_random_uuid(),
    creado_por uuid not null references auth.users(id) on delete cascade,
    nombre text not null,
    ruc text,
    correo text,
    contacto text,
    telefono text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint proveedores_nombre_no_vacio check (btrim(nombre) <> ''),
    constraint proveedores_ruc_formato check (ruc is null or ruc ~ '^[0-9]{11}$'),
    constraint proveedores_correo_formato check (correo is null or correo ~* '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$')
);

create unique index proveedores_creador_ruc_unique
    on public.proveedores (creado_por, ruc)
    where ruc is not null;

create unique index proveedores_creador_correo_unique
    on public.proveedores (creado_por, lower(correo))
    where correo is not null;

create table public.solicitud_proveedores (
    solicitud_id uuid not null references public.solicitudes_cotizacion(id) on delete cascade,
    proveedor_id uuid not null references public.proveedores(id) on delete restrict,
    estado text not null default 'seleccionado',
    created_at timestamptz not null default now(),
    primary key (solicitud_id, proveedor_id),
    constraint solicitud_proveedores_estado_valido check (estado in ('seleccionado', 'invitado', 'respondio', 'descartado'))
);

create table public.documentos (
    id uuid primary key default gen_random_uuid(),
    solicitud_id uuid not null references public.solicitudes_cotizacion(id) on delete cascade,
    tipo text not null,
    nombre_original text not null,
    storage_file_id uuid not null,
    mime_type text,
    tamano_bytes bigint,
    subido_por uuid not null references auth.users(id) on delete cascade,
    created_at timestamptz not null default now(),
    constraint documentos_tipo_valido check (tipo in ('itemizado', 'plantilla_comparativo', 'cuadro_procura')),
    constraint documentos_nombre_no_vacio check (btrim(nombre_original) <> ''),
    constraint documentos_tamano_valido check (tamano_bytes is null or tamano_bytes >= 0),
    constraint documentos_storage_file_unique unique (storage_file_id),
    constraint documentos_tipo_por_solicitud_unique unique (solicitud_id, tipo)
);

create table public.partidas (
    id uuid primary key default gen_random_uuid(),
    solicitud_id uuid not null references public.solicitudes_cotizacion(id) on delete cascade,
    codigo text,
    descripcion text not null,
    unidad text not null,
    metrado numeric(18, 4) not null,
    orden integer not null default 0,
    created_at timestamptz not null default now(),
    constraint partidas_descripcion_no_vacia check (btrim(descripcion) <> ''),
    constraint partidas_unidad_no_vacia check (btrim(unidad) <> ''),
    constraint partidas_metrado_no_negativo check (metrado >= 0)
);

create or replace function public.actualizar_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger proyectos_updated_at
before update on public.proyectos
for each row execute function public.actualizar_updated_at();

create trigger solicitudes_updated_at
before update on public.solicitudes_cotizacion
for each row execute function public.actualizar_updated_at();

create trigger proveedores_updated_at
before update on public.proveedores
for each row execute function public.actualizar_updated_at();

