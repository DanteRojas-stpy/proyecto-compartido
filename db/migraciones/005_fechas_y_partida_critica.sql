-- Ejecutar una vez después de 004_proyectos_y_correlativos.sql.
-- Conserva vigencia_dias en registros antiguos, pero ya no la exige al crear.
alter table public.solicitudes_cotizacion
    alter column vigencia_dias drop not null,
    add column partida_critica boolean not null default false,
    add column frecuencia_aviso_dias integer generated always as
        (case when partida_critica then 1 else 2 end) stored;

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
    if new.fecha_limite is null or new.fecha_limite < (now() at time zone 'America/Lima')::date then
        raise exception 'La fecha fin para recibir ofertas debe ser hoy o posterior';
    end if;

    perform 1 from public.proyectos where id = new.proyecto_id for update;
    if not found then
        raise exception 'Proyecto inexistente';
    end if;

    select coalesce(max(coalesce(s.numero,
        case when s.codigo ~ ('^' || new.tipo || '-[0-9]+$')
            then substring(s.codigo from '[0-9]+$')::integer end)), 0) + 1
    into siguiente
    from public.solicitudes_cotizacion s
    where s.proyecto_id = new.proyecto_id and s.tipo = new.tipo;

    new.numero := siguiente;
    new.codigo := new.tipo || '-' || lpad(siguiente::text, 3, '0');
    return new;
end;
$$;
