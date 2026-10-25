-- E1: distingue documentos generales y documentos entregados por proveedor.
-- Ejecutar una sola vez despues de 001_e1_registro_solicitud.sql.

alter table public.documentos
    add column proveedor_id uuid,
    add column version integer not null default 1,
    add column documento_estado text not null default 'vigente';

alter table public.documentos
    drop constraint documentos_tipo_valido,
    drop constraint documentos_tipo_por_solicitud_unique;

alter table public.documentos
    add constraint documentos_solicitud_proveedor_fk
        foreign key (solicitud_id, proveedor_id)
        references public.solicitud_proveedores (solicitud_id, proveedor_id)
        on delete restrict,
    add constraint documentos_tipo_valido
        check (tipo in (
            'itemizado',
            'plantilla_comparativo',
            'cuadro_procura',
            'cotizacion_proveedor',
            'anexo_proveedor'
        )),
    add constraint documentos_version_positiva
        check (version > 0),
    add constraint documentos_estado_valido
        check (documento_estado in ('vigente', 'reemplazado', 'anulado')),
    add constraint documentos_proveedor_segun_tipo
        check (
            (
                tipo in ('itemizado', 'plantilla_comparativo', 'cuadro_procura')
                and proveedor_id is null
            )
            or
            (
                tipo in ('cotizacion_proveedor', 'anexo_proveedor')
                and proveedor_id is not null
            )
        );

create unique index documentos_generales_tipo_unique
    on public.documentos (solicitud_id, tipo)
    where proveedor_id is null;

create unique index documentos_proveedor_version_unique
    on public.documentos (solicitud_id, proveedor_id, tipo, version)
    where proveedor_id is not null;

create index documentos_proveedor_busqueda
    on public.documentos (proveedor_id, created_at desc)
    where proveedor_id is not null;
