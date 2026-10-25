-- E1: numeración por proyecto y tipo de cotización.
-- Ejecutar una sola vez después de 003_envios_solicitud.sql.

alter table public.solicitudes_cotizacion
    add column tipo text not null default 'SC',
    add column numero integer;

update public.solicitudes_cotizacion
set tipo = case when codigo ~ '^MA-[0-9]+$' then 'MA' else 'SC' end,
    numero = case when codigo ~ '^(MA|SC)-[0-9]+$'
        then substring(codigo from '[0-9]+$')::integer
        else null end;

alter table public.solicitudes_cotizacion
    add constraint solicitudes_tipo_valido check (tipo in ('MA', 'SC')),
    add constraint solicitudes_numero_positivo check (numero is null or numero > 0);

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

    -- Serializa los registros del mismo proyecto, incluso entre usuarios.
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
    new.codigo := new.tipo || '-' || lpad(siguiente::text,
        case when new.tipo = 'MA' then 3 else 2 end, '0');
    return new;
end;
$$;

create trigger solicitudes_asignar_codigo
before insert on public.solicitudes_cotizacion
for each row execute function public.asignar_codigo_solicitud();
