-- E2: cada correo del proveedor conserva su propio estado y su historial.
-- Ejecutar una vez después de 009_respuestas_con_ficha_tecnica.sql.

begin;

alter table public.correos_proveedor
    add column estado_correo text,
    add column origen_estado text not null default 'agente',
    add column estado_asignado_por uuid references auth.users(id) on delete restrict,
    add column estado_asignado_at timestamptz not null default now(),
    add constraint correos_proveedor_origen_estado_valido
        check (origen_estado in ('agente', 'usuario'));

-- Las clasificaciones automáticas antiguas nunca se migran como finales. La
-- aceptación final solo puede registrarla el especialista desde la interfaz.
update public.correos_proveedor
set estado_correo = case
    when coalesce(analisis_agente ->> 'detalle', '') in (
        'ficha_tecnica_sin_cotizacion',
        'aclaraciones_pendientes',
        'cotizacion_definitiva'
    ) then 'cotizacion_o_ficha_tecnica_recibida'
    else 'respuesta_sin_nueva_cotizacion_ni_ficha_tecnica'
end;

alter table public.correos_proveedor
    alter column estado_correo set not null,
    add constraint correos_proveedor_estado_correo_valido
        check (estado_correo in (
            'respuesta_sin_nueva_cotizacion_ni_ficha_tecnica',
            'cotizacion_o_ficha_tecnica_recibida',
            'cotizacion_o_ficha_tecnica_aceptada_final'
        )),
    add constraint correos_proveedor_estado_actor_coherente
        check (
            (origen_estado = 'agente' and estado_asignado_por is null)
            or (origen_estado = 'usuario' and estado_asignado_por is not null)
        );

create table public.historial_estados_correo (
    id uuid primary key default gen_random_uuid(),
    correo_id uuid not null references public.correos_proveedor(id) on delete cascade,
    solicitud_id uuid not null,
    proveedor_id uuid not null,
    estado_anterior text,
    estado_nuevo text not null,
    origen text not null,
    cambiado_por uuid references auth.users(id) on delete restrict,
    created_at timestamptz not null default now(),
    constraint historial_estados_correo_participacion_fk
        foreign key (solicitud_id, proveedor_id)
        references public.solicitud_proveedores (solicitud_id, proveedor_id)
        on delete cascade,
    constraint historial_estados_correo_estado_anterior_valido
        check (estado_anterior is null or estado_anterior in (
            'respuesta_sin_nueva_cotizacion_ni_ficha_tecnica',
            'cotizacion_o_ficha_tecnica_recibida',
            'cotizacion_o_ficha_tecnica_aceptada_final'
        )),
    constraint historial_estados_correo_estado_nuevo_valido
        check (estado_nuevo in (
            'respuesta_sin_nueva_cotizacion_ni_ficha_tecnica',
            'cotizacion_o_ficha_tecnica_recibida',
            'cotizacion_o_ficha_tecnica_aceptada_final'
        )),
    constraint historial_estados_correo_origen_valido
        check (origen in ('agente', 'usuario'))
);

create index historial_estados_correo_correo_busqueda
    on public.historial_estados_correo (correo_id, created_at desc);
create index historial_estados_correo_participacion_busqueda
    on public.historial_estados_correo (solicitud_id, proveedor_id, created_at desc);

-- Vincula las cotizaciones y fichas que recuperará E3 con el correo de origen.
alter table public.documentos
    add column correo_id uuid references public.correos_proveedor(id) on delete set null;

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
            'ficha_tecnica_proveedor',
            'anexo_proveedor'
        )),
    add constraint documentos_proveedor_segun_tipo
        check (
            (
                tipo in ('itemizado', 'plantilla_comparativo', 'cuadro_procura', 'cuadro_comparativo')
                and proveedor_id is null
                and correo_id is null
            )
            or
            (
                tipo in ('cotizacion_proveedor', 'ficha_tecnica_proveedor', 'anexo_proveedor')
                and proveedor_id is not null
            )
        );

create index documentos_correo_busqueda
    on public.documentos (correo_id, created_at desc)
    where correo_id is not null;

create or replace function public.validar_documento_correo_origen()
returns trigger
language plpgsql
as $$
begin
    if new.tipo in ('cotizacion_proveedor', 'ficha_tecnica_proveedor', 'anexo_proveedor')
       and new.correo_id is null then
        raise exception 'Los documentos de proveedor deben indicar el correo de origen';
    end if;
    if new.correo_id is not null and not exists (
        select 1
        from public.correos_proveedor c
        where c.id = new.correo_id
          and c.solicitud_id = new.solicitud_id
          and c.proveedor_id = new.proveedor_id
    ) then
        raise exception 'El documento no corresponde al proveedor y solicitud del correo';
    end if;
    return new;
end;
$$;

create trigger documentos_validar_correo_origen_insertar
before insert on public.documentos
for each row execute function public.validar_documento_correo_origen();

create trigger documentos_validar_correo_origen_actualizar
before update of correo_id, solicitud_id, proveedor_id, tipo on public.documentos
for each row execute function public.validar_documento_correo_origen();

create or replace function public.validar_estado_correo_proveedor()
returns trigger
language plpgsql
as $$
declare
    sesion jsonb;
    actor uuid;
begin
    begin
        sesion := nullif(current_setting('hasura.user', true), '')::jsonb;
        actor := case
            when sesion ->> 'x-hasura-role' = 'user'
            then nullif(sesion ->> 'x-hasura-user-id', '')::uuid
            else null
        end;
    exception when others then
        actor := null;
    end;

    if actor is not null then
        new.origen_estado := 'usuario';
        new.estado_asignado_por := actor;
        new.estado_asignado_at := now();
    elsif tg_op = 'INSERT' then
        new.origen_estado := 'agente';
        new.estado_asignado_por := null;
        new.estado_asignado_at := coalesce(new.estado_asignado_at, now());
    end if;

    if new.estado_correo = 'cotizacion_o_ficha_tecnica_aceptada_final' then
        if actor is null then
            raise exception 'Solo el especialista puede aceptar una cotización o ficha técnica como final';
        end if;
        if new.fuera_plazo then
            raise exception 'No se puede aceptar como final una respuesta recibida fuera del plazo';
        end if;
        if exists (
            select 1
            from public.aclaraciones_proveedor a
            where a.solicitud_id = new.solicitud_id
              and a.proveedor_id = new.proveedor_id
              and a.estado = 'abierta'
        ) then
            raise exception 'No se puede aceptar como final mientras existan aclaraciones abiertas';
        end if;
        if not exists (
            select 1
            from public.solicitud_proveedores sp
            where sp.solicitud_id = new.solicitud_id
              and sp.proveedor_id = new.proveedor_id
              and sp.considerado
        ) then
            raise exception 'No se puede aceptar como final la respuesta de un proveedor excluido';
        end if;
        if not exists (
            select 1
            from public.documentos d
            where d.correo_id = new.id
              and d.tipo in ('cotizacion_proveedor', 'ficha_tecnica_proveedor')
              and d.documento_estado = 'vigente'
        ) then
            raise exception 'No se puede aceptar como final sin una cotización o ficha técnica recuperada por E3';
        end if;
    end if;

    return new;
end;
$$;

create trigger correos_proveedor_validar_estado_insertar
before insert on public.correos_proveedor
for each row execute function public.validar_estado_correo_proveedor();

create trigger correos_proveedor_validar_estado_actualizar
before update of estado_correo on public.correos_proveedor
for each row execute function public.validar_estado_correo_proveedor();

create or replace function public.auditar_estado_correo_proveedor()
returns trigger
language plpgsql
as $$
begin
    -- Confirmar la propuesta de n8n con el mismo estado también es una
    -- decisión del especialista y debe conservarse en el historial.
    if tg_op = 'INSERT'
       or old.estado_correo is distinct from new.estado_correo
       or old.origen_estado is distinct from new.origen_estado
       or old.estado_asignado_por is distinct from new.estado_asignado_por then
        insert into public.historial_estados_correo (
            correo_id, solicitud_id, proveedor_id,
            estado_anterior, estado_nuevo, origen, cambiado_por, created_at
        ) values (
            new.id, new.solicitud_id, new.proveedor_id,
            case when tg_op = 'INSERT' then null else old.estado_correo end,
            new.estado_correo, new.origen_estado, new.estado_asignado_por,
            new.estado_asignado_at
        );
    end if;
    return new;
end;
$$;

create trigger correos_proveedor_auditar_estado_insertar
after insert on public.correos_proveedor
for each row execute function public.auditar_estado_correo_proveedor();

create trigger correos_proveedor_auditar_estado_actualizar
after update of estado_correo on public.correos_proveedor
for each row execute function public.auditar_estado_correo_proveedor();

create or replace function public.sincronizar_participacion_desde_correos()
returns trigger
language plpgsql
as $$
declare
    solicitud uuid;
    proveedor uuid;
    tiene_final boolean;
    tiene_documento boolean;
    tiene_respuesta boolean;
    ultimo_correo timestamptz;
    origen text;
    proveedor_considerado boolean;
begin
    if tg_op = 'DELETE' then
        solicitud := old.solicitud_id;
        proveedor := old.proveedor_id;
    else
        solicitud := new.solicitud_id;
        proveedor := new.proveedor_id;
    end if;

    select considerado into proveedor_considerado
    from public.solicitud_proveedores
    where solicitud_id = solicitud and proveedor_id = proveedor;

    -- Los correos tardíos y las respuestas de un proveedor ya excluido quedan
    -- visibles en su historial, pero no lo reincorporan al seguimiento.
    if proveedor_considerado is false then
        if tg_op = 'DELETE' then return old; end if;
        return new;
    end if;

    select
        coalesce(bool_or(estado_correo = 'cotizacion_o_ficha_tecnica_aceptada_final')
            filter (where not fuera_plazo), false),
        coalesce(bool_or(estado_correo = 'cotizacion_o_ficha_tecnica_recibida')
            filter (where not fuera_plazo), false),
        count(*) filter (where not fuera_plazo) > 0,
        max(recibido_at) filter (where not fuera_plazo),
        case when bool_or(origen_estado = 'usuario') filter (where not fuera_plazo)
            then 'usuario' else 'agente' end
    into tiene_final, tiene_documento, tiene_respuesta, ultimo_correo, origen
    from public.correos_proveedor
    where solicitud_id = solicitud
      and proveedor_id = proveedor;

    if tiene_final then
        update public.solicitud_proveedores
        set estado = 'respondio',
            estado_respuesta = 'envio_cotizacion',
            detalle_respuesta = 'cotizacion_definitiva',
            ultimo_correo_at = ultimo_correo,
            origen_clasificacion = origen
        where solicitud_id = solicitud and proveedor_id = proveedor;
    elsif tiene_documento then
        update public.solicitud_proveedores
        set estado = 'respondio',
            estado_respuesta = 'envio_cotizacion_con_aclaracion',
            detalle_respuesta = 'aclaraciones_pendientes',
            ultimo_correo_at = ultimo_correo,
            origen_clasificacion = origen
        where solicitud_id = solicitud and proveedor_id = proveedor;
    elsif tiene_respuesta then
        update public.solicitud_proveedores
        set estado = 'respondio',
            estado_respuesta = 'no_envio_cotizacion',
            detalle_respuesta = 'confirmo_recepcion',
            ultimo_correo_at = ultimo_correo,
            origen_clasificacion = origen
        where solicitud_id = solicitud and proveedor_id = proveedor;
    else
        update public.solicitud_proveedores
        set estado_respuesta = 'no_envio_cotizacion',
            detalle_respuesta = 'sin_respuesta',
            ultimo_correo_at = null,
            origen_clasificacion = 'sistema'
        where solicitud_id = solicitud and proveedor_id = proveedor;
    end if;

    if tg_op = 'DELETE' then return old; end if;
    return new;
end;
$$;

create trigger correos_proveedor_sincronizar_insertar
after insert on public.correos_proveedor
for each row execute function public.sincronizar_participacion_desde_correos();

create trigger correos_proveedor_sincronizar_actualizar
after update of estado_correo on public.correos_proveedor
for each row execute function public.sincronizar_participacion_desde_correos();

create trigger correos_proveedor_sincronizar_eliminar
after delete on public.correos_proveedor
for each row execute function public.sincronizar_participacion_desde_correos();

-- Recalcula el resumen actual de cada proveedor con los correos migrados.
update public.correos_proveedor
set estado_correo = estado_correo;

insert into public.historial_estados_correo (
    correo_id, solicitud_id, proveedor_id,
    estado_anterior, estado_nuevo, origen, cambiado_por, created_at
)
select id, solicitud_id, proveedor_id, null, estado_correo, origen_estado,
       estado_asignado_por, estado_asignado_at
from public.correos_proveedor;

commit;
