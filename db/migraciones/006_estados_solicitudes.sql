-- Estados de negocio de las solicitudes de cotización.
-- Ejecutar una vez después de 005_fechas_y_partida_critica.sql.

alter table public.solicitudes_cotizacion
    add column preparada_para_envio boolean not null default false,
    add column cerrada_at timestamptz;

alter table public.solicitudes_cotizacion
    drop constraint solicitudes_estado_valido;

update public.solicitudes_cotizacion
set preparada_para_envio = estado in ('lista', 'en_proceso', 'cerrada', 'cancelada'),
    cerrada_at = case when estado in ('cerrada', 'cancelada') then updated_at else null end,
    estado = case
        when estado in ('cerrada', 'cancelada') then 'cerrado'
        else 'inicio'
    end;

alter table public.solicitudes_cotizacion
    alter column estado set default 'inicio',
    add constraint solicitudes_estado_valido
        check (estado in ('inicio', 'cerrado', 'cerrado_sin_proveedores')),
    add constraint solicitudes_cierre_coherente
        check (
            (estado = 'inicio' and cerrada_at is null)
            or (estado in ('cerrado', 'cerrado_sin_proveedores') and cerrada_at is not null)
        );

alter table public.documentos
    drop constraint documentos_tipo_valido,
    drop constraint documentos_proveedor_segun_tipo;

alter table public.documentos
    add constraint documentos_tipo_valido
        check (tipo in (
            'itemizado',
            'plantilla_comparativo',
            'cuadro_procura',
            'cuadro_comparativo',
            'cotizacion_proveedor',
            'anexo_proveedor'
        )),
    add constraint documentos_proveedor_segun_tipo
        check (
            (
                tipo in ('itemizado', 'plantilla_comparativo', 'cuadro_procura', 'cuadro_comparativo')
                and proveedor_id is null
            )
            or
            (
                tipo in ('cotizacion_proveedor', 'anexo_proveedor')
                and proveedor_id is not null
            )
        );

create or replace function public.validar_estado_solicitud()
returns trigger
language plpgsql
as $$
declare
    fecha_hoy date := (now() at time zone 'America/Lima')::date;
begin
    if tg_op = 'INSERT' then
        if new.estado <> 'inicio' then
            raise exception 'Una solicitud nueva debe iniciar en estado Inicio';
        end if;
        new.cerrada_at := null;
        return new;
    end if;

    if new.estado = old.estado then
        return new;
    end if;

    if old.estado <> 'inicio' then
        raise exception 'Una solicitud cerrada no puede cambiar de estado';
    end if;

    if new.estado = 'cerrado' then
        if not exists (
            select 1
            from public.documentos d
            where d.solicitud_id = old.id
              and d.tipo = 'cuadro_comparativo'
              and d.documento_estado = 'vigente'
        ) then
            raise exception 'No se puede cerrar la solicitud sin un cuadro comparativo vigente';
        end if;
    elsif new.estado = 'cerrado_sin_proveedores' then
        if old.fecha_limite is null or old.fecha_limite >= fecha_hoy then
            raise exception 'La fecha fin para recibir ofertas todavía no ha vencido';
        end if;
        if exists (
            select 1
            from public.solicitud_proveedores sp
            where sp.solicitud_id = old.id
              and sp.estado = 'respondio'
        ) or exists (
            select 1
            from public.documentos d
            where d.solicitud_id = old.id
              and d.tipo = 'cotizacion_proveedor'
              and d.documento_estado = 'vigente'
        ) then
            raise exception 'La solicitud tiene al menos un proveedor con respuesta u oferta';
        end if;
    else
        raise exception 'Transición de estado no permitida: % a %', old.estado, new.estado;
    end if;

    new.cerrada_at := now();
    return new;
end;
$$;

create trigger solicitudes_validar_estado
before insert or update of estado on public.solicitudes_cotizacion
for each row execute function public.validar_estado_solicitud();

create index solicitudes_estado_fecha_limite_busqueda
    on public.solicitudes_cotizacion (estado, fecha_limite)
    where estado = 'inicio';
