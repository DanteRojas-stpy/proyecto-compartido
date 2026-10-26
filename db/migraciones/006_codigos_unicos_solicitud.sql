-- E1: códigos únicos por usuario y tipo entre todos sus proyectos.
-- Ejecutar una vez después de 005_fechas_y_partida_critica.sql.

begin;

lock table public.solicitudes_cotizacion in access exclusive mode;

-- Renumera los registros de prueba existentes en orden de creación. Primero
-- usa códigos temporales para evitar colisiones durante la actualización.
with numeradas as (
    select
        id,
        row_number() over (
            partition by creado_por, tipo
            order by created_at, id
        )::integer as numero_nuevo
    from public.solicitudes_cotizacion
)
update public.solicitudes_cotizacion as solicitud
set numero = numeradas.numero_nuevo,
    codigo = 'TEMP-' || replace(solicitud.id::text, '-', '')
from numeradas
where numeradas.id = solicitud.id;

update public.solicitudes_cotizacion
set codigo = tipo || '-' || lpad(numero::text, 3, '0');

alter table public.solicitudes_cotizacion
    drop constraint if exists solicitudes_proyecto_codigo_unique,
    alter column numero set not null;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.solicitudes_cotizacion'::regclass
          and conname = 'solicitudes_creador_codigo_unique'
    ) then
        alter table public.solicitudes_cotizacion
            add constraint solicitudes_creador_codigo_unique
            unique (creado_por, codigo);
    end if;

    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.solicitudes_cotizacion'::regclass
          and conname = 'solicitudes_creador_tipo_numero_unique'
    ) then
        alter table public.solicitudes_cotizacion
            add constraint solicitudes_creador_tipo_numero_unique
            unique (creado_por, tipo, numero);
    end if;
end;
$$;

create or replace function public.asignar_codigo_solicitud()
returns trigger
language plpgsql
as $$
declare
    siguiente integer;
begin
    if new.tipo not in ('MA', 'SC') then
        raise exception 'Tipo de solicitud inválido: %', new.tipo;
    end if;
    if new.fecha_limite is null
       or new.fecha_limite < (now() at time zone 'America/Lima')::date then
        raise exception 'La fecha fin para recibir ofertas debe ser hoy o posterior';
    end if;

    perform 1
    from public.proyectos
    where id = new.proyecto_id
      and responsable_id = new.creado_por;
    if not found then
        raise exception 'Proyecto inexistente o no pertenece al usuario';
    end if;

    -- Evita que dos solicitudes simultáneas del mismo usuario y tipo reciban
    -- el mismo correlativo, incluso si pertenecen a proyectos distintos.
    perform pg_advisory_xact_lock(hashtextextended(
        'costflow:solicitud:' || new.creado_por::text || ':' || new.tipo,
        0
    ));

    select coalesce(max(numero), 0) + 1
    into siguiente
    from public.solicitudes_cotizacion
    where creado_por = new.creado_por
      and tipo = new.tipo;

    new.numero := siguiente;
    new.codigo := new.tipo || '-' || lpad(siguiente::text, 3, '0');
    return new;
end;
$$;

commit;
