-- Seguimiento de respuestas, coordinaciones y notificaciones en la plataforma.
-- Ejecutar una vez después de 006_estados_solicitudes.sql.

alter table public.solicitud_proveedores
    add column estado_respuesta text not null default 'no_envio_cotizacion',
    add column detalle_respuesta text not null default 'sin_respuesta',
    add column considerado boolean not null default true,
    add column numero_coordinaciones integer not null default 0,
    add column ultimo_correo_at timestamptz,
    add column proximo_seguimiento_at timestamptz,
    add column origen_clasificacion text not null default 'sistema',
    add column confianza_clasificacion numeric(4, 3),
    add column evidencia_clasificacion jsonb not null default '[]'::jsonb,
    add column updated_at timestamptz not null default now(),
    add constraint solicitud_proveedores_estado_respuesta_valido
        check (estado_respuesta in (
            'no_envio_cotizacion',
            'envio_cotizacion_con_aclaracion',
            'envio_cotizacion'
        )),
    add constraint solicitud_proveedores_detalle_respuesta_valido
        check (detalle_respuesta in (
            'sin_respuesta',
            'confirmo_recepcion',
            'consulta_previa',
            'rechazo_participar',
            'aclaraciones_pendientes',
            'cotizacion_definitiva',
            'tres_coordinaciones',
            'plazo_vencido'
        )),
    add constraint solicitud_proveedores_coordinaciones_validas
        check (numero_coordinaciones between 0 and 3),
    add constraint solicitud_proveedores_origen_valido
        check (origen_clasificacion in ('agente', 'usuario', 'sistema')),
    add constraint solicitud_proveedores_confianza_valida
        check (confianza_clasificacion is null or confianza_clasificacion between 0 and 1),
    add constraint solicitud_proveedores_exclusion_coherente
        check (considerado or estado_respuesta = 'no_envio_cotizacion');

alter table public.envios_solicitud
    add column gmail_thread_id text;

create table public.correos_proveedor (
    id uuid primary key default gen_random_uuid(),
    solicitud_id uuid not null,
    proveedor_id uuid not null,
    gmail_message_id text not null unique,
    gmail_thread_id text,
    remitente text not null,
    destinatarios text[] not null default '{}',
    asunto text not null default '',
    cuerpo_texto text not null default '',
    adjuntos jsonb not null default '[]'::jsonb,
    recibido_at timestamptz not null,
    fuera_plazo boolean not null default false,
    analisis_agente jsonb,
    created_at timestamptz not null default now(),
    constraint correos_proveedor_participacion_fk
        foreign key (solicitud_id, proveedor_id)
        references public.solicitud_proveedores (solicitud_id, proveedor_id)
        on delete cascade,
    constraint correos_proveedor_message_id_no_vacio
        check (btrim(gmail_message_id) <> ''),
    constraint correos_proveedor_remitente_no_vacio
        check (btrim(remitente) <> '')
);

create table public.aclaraciones_proveedor (
    id uuid primary key default gen_random_uuid(),
    solicitud_id uuid not null,
    proveedor_id uuid not null,
    correo_id uuid references public.correos_proveedor(id) on delete set null,
    dedupe_key text not null unique,
    descripcion text not null,
    estado text not null default 'abierta',
    resuelta_por uuid references auth.users(id) on delete set null,
    resuelta_at timestamptz,
    created_at timestamptz not null default now(),
    constraint aclaraciones_proveedor_participacion_fk
        foreign key (solicitud_id, proveedor_id)
        references public.solicitud_proveedores (solicitud_id, proveedor_id)
        on delete cascade,
    constraint aclaraciones_proveedor_descripcion_no_vacia
        check (btrim(descripcion) <> ''),
    constraint aclaraciones_proveedor_estado_valido
        check (estado in ('abierta', 'resuelta')),
    constraint aclaraciones_proveedor_resolucion_coherente
        check (
            (estado = 'abierta' and resuelta_at is null)
            or (estado = 'resuelta' and resuelta_at is not null)
        )
);

create table public.coordinaciones_proveedor (
    id uuid primary key default gen_random_uuid(),
    solicitud_id uuid not null,
    proveedor_id uuid not null,
    medio text not null,
    comentario text not null,
    registrado_por uuid not null references auth.users(id) on delete restrict,
    created_at timestamptz not null default now(),
    constraint coordinaciones_proveedor_participacion_fk
        foreign key (solicitud_id, proveedor_id)
        references public.solicitud_proveedores (solicitud_id, proveedor_id)
        on delete cascade,
    constraint coordinaciones_proveedor_medio_valido
        check (medio in ('correo', 'whatsapp', 'llamada')),
    constraint coordinaciones_proveedor_comentario_no_vacio
        check (btrim(comentario) <> '')
);

create table public.historial_respuestas_proveedor (
    id uuid primary key default gen_random_uuid(),
    solicitud_id uuid not null,
    proveedor_id uuid not null,
    correo_id uuid references public.correos_proveedor(id) on delete set null,
    estado_anterior text,
    estado_nuevo text not null,
    detalle_anterior text,
    detalle_nuevo text not null,
    considerado_anterior boolean,
    considerado_nuevo boolean not null,
    origen text not null,
    confianza numeric(4, 3),
    evidencia jsonb not null default '[]'::jsonb,
    cambiado_por uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default now(),
    constraint historial_respuestas_proveedor_participacion_fk
        foreign key (solicitud_id, proveedor_id)
        references public.solicitud_proveedores (solicitud_id, proveedor_id)
        on delete cascade,
    constraint historial_respuestas_proveedor_origen_valido
        check (origen in ('agente', 'usuario', 'sistema')),
    constraint historial_respuestas_proveedor_confianza_valida
        check (confianza is null or confianza between 0 and 1)
);

create table public.notificaciones (
    id uuid primary key default gen_random_uuid(),
    usuario_id uuid not null references auth.users(id) on delete cascade,
    solicitud_id uuid not null references public.solicitudes_cotizacion(id) on delete cascade,
    proveedor_id uuid,
    tipo text not null,
    titulo text not null,
    mensaje text not null,
    estado text not null default 'no_leida',
    datos jsonb not null default '{}'::jsonb,
    dedupe_key text not null unique,
    created_at timestamptz not null default now(),
    leida_at timestamptz,
    atendida_at timestamptz,
    constraint notificaciones_participacion_fk
        foreign key (solicitud_id, proveedor_id)
        references public.solicitud_proveedores (solicitud_id, proveedor_id)
        on delete cascade,
    constraint notificaciones_tipo_valido
        check (tipo in ('resumen_seguimiento', 'cambio_respuesta', 'requiere_revision', 'proveedor_excluido')),
    constraint notificaciones_estado_valido
        check (estado in ('no_leida', 'leida', 'atendida')),
    constraint notificaciones_titulo_no_vacio check (btrim(titulo) <> ''),
    constraint notificaciones_mensaje_no_vacio check (btrim(mensaje) <> ''),
    constraint notificaciones_estado_fechas_coherente check (
        (estado = 'no_leida' and leida_at is null and atendida_at is null)
        or (estado = 'leida' and leida_at is not null and atendida_at is null)
        or (estado = 'atendida' and leida_at is not null and atendida_at is not null)
    )
);

create index correos_proveedor_hilo_busqueda
    on public.correos_proveedor (gmail_thread_id, recibido_at desc);
create index envios_solicitud_hilo_busqueda
    on public.envios_solicitud (gmail_thread_id)
    where gmail_thread_id is not null;
create index correos_proveedor_participacion_busqueda
    on public.correos_proveedor (solicitud_id, proveedor_id, recibido_at desc);
create index aclaraciones_proveedor_abiertas_busqueda
    on public.aclaraciones_proveedor (solicitud_id, proveedor_id)
    where estado = 'abierta';
create index coordinaciones_proveedor_participacion_busqueda
    on public.coordinaciones_proveedor (solicitud_id, proveedor_id, created_at desc);
create index notificaciones_usuario_busqueda
    on public.notificaciones (usuario_id, created_at desc);
create index notificaciones_solicitud_busqueda
    on public.notificaciones (solicitud_id, created_at desc);

create trigger solicitud_proveedores_updated_at
before update on public.solicitud_proveedores
for each row execute function public.actualizar_updated_at();

create or replace function public.validar_respuesta_proveedor()
returns trigger
language plpgsql
as $$
declare
    limite date;
    fecha_hoy date := (now() at time zone 'America/Lima')::date;
begin
    if not old.considerado and (
        new.considerado or new.estado_respuesta <> 'no_envio_cotizacion'
    ) then
        raise exception 'Un proveedor excluido no puede reincorporarse a la solicitud';
    end if;

    if (
        new.estado_respuesta = 'envio_cotizacion'
        and new.detalle_respuesta <> 'cotizacion_definitiva'
    ) or (
        new.estado_respuesta = 'envio_cotizacion_con_aclaracion'
        and new.detalle_respuesta <> 'aclaraciones_pendientes'
    ) or (
        new.estado_respuesta = 'no_envio_cotizacion'
        and new.detalle_respuesta not in (
            'sin_respuesta', 'confirmo_recepcion', 'consulta_previa',
            'rechazo_participar', 'tres_coordinaciones', 'plazo_vencido'
        )
    ) then
        raise exception 'El estado y el detalle de la respuesta no son coherentes';
    end if;

    if new.estado_respuesta = 'envio_cotizacion' and exists (
        select 1
        from public.aclaraciones_proveedor a
        where a.solicitud_id = new.solicitud_id
          and a.proveedor_id = new.proveedor_id
          and a.estado = 'abierta'
    ) then
        raise exception 'No se puede marcar la cotización como definitiva con aclaraciones abiertas';
    end if;

    if new.estado_respuesta <> old.estado_respuesta then
        select fecha_limite into limite
        from public.solicitudes_cotizacion
        where id = new.solicitud_id;
        if limite < fecha_hoy and new.estado_respuesta <> 'no_envio_cotizacion' then
            raise exception 'La respuesta llegó después de la fecha límite y no puede reincorporar al proveedor';
        end if;
    end if;

    if new.estado_respuesta in ('envio_cotizacion', 'envio_cotizacion_con_aclaracion') then
        new.considerado := true;
    end if;
    if not new.considerado then
        new.estado_respuesta := 'no_envio_cotizacion';
    end if;
    return new;
end;
$$;

create trigger solicitud_proveedores_validar_respuesta
before update of estado_respuesta, detalle_respuesta, considerado on public.solicitud_proveedores
for each row execute function public.validar_respuesta_proveedor();

create or replace function public.auditar_respuesta_proveedor()
returns trigger
language plpgsql
as $$
declare
    sesion jsonb;
    actor uuid;
begin
    if row(old.estado_respuesta, old.detalle_respuesta, old.considerado)
       is distinct from row(new.estado_respuesta, new.detalle_respuesta, new.considerado) then
        begin
            sesion := nullif(current_setting('hasura.user', true), '')::jsonb;
            actor := nullif(sesion ->> 'x-hasura-user-id', '')::uuid;
        exception when others then
            actor := null;
        end;

        insert into public.historial_respuestas_proveedor (
            solicitud_id, proveedor_id,
            estado_anterior, estado_nuevo,
            detalle_anterior, detalle_nuevo,
            considerado_anterior, considerado_nuevo,
            origen, confianza, evidencia, cambiado_por
        ) values (
            new.solicitud_id, new.proveedor_id,
            old.estado_respuesta, new.estado_respuesta,
            old.detalle_respuesta, new.detalle_respuesta,
            old.considerado, new.considerado,
            new.origen_clasificacion,
            case when new.origen_clasificacion = 'usuario' then null else new.confianza_clasificacion end,
            new.evidencia_clasificacion,
            actor
        );
    end if;
    return new;
end;
$$;

create trigger solicitud_proveedores_auditar_respuesta
after update on public.solicitud_proveedores
for each row execute function public.auditar_respuesta_proveedor();

create or replace function public.registrar_coordinacion_proveedor()
returns trigger
language plpgsql
as $$
declare
    total integer;
    total_anterior integer;
    sigue_considerado boolean;
    respuesta_actual text;
    propietario uuid;
    nombre_proveedor text;
begin
    select numero_coordinaciones, considerado, estado_respuesta
    into total_anterior, sigue_considerado, respuesta_actual
    from public.solicitud_proveedores
    where solicitud_id = new.solicitud_id and proveedor_id = new.proveedor_id
    for update;

    if not sigue_considerado or total_anterior >= 3 then
        raise exception 'El proveedor ya no admite nuevas coordinaciones';
    end if;
    if respuesta_actual = 'envio_cotizacion' then
        raise exception 'La cotización definitiva no requiere otra coordinación';
    end if;

    update public.solicitud_proveedores
    set numero_coordinaciones = least(numero_coordinaciones + 1, 3),
        considerado = case
            when numero_coordinaciones + 1 >= 3
             and estado_respuesta = 'no_envio_cotizacion' then false
            else considerado
        end,
        detalle_respuesta = case
            when numero_coordinaciones + 1 >= 3
             and estado_respuesta = 'no_envio_cotizacion' then 'tres_coordinaciones'
            else detalle_respuesta
        end,
        origen_clasificacion = 'usuario',
        evidencia_clasificacion = jsonb_build_array(
            jsonb_build_object('coordinacion_id', new.id, 'medio', new.medio)
        )
    where solicitud_id = new.solicitud_id and proveedor_id = new.proveedor_id
    returning numero_coordinaciones into total;

    if total = 3 and exists (
        select 1
        from public.solicitud_proveedores sp
        where sp.solicitud_id = new.solicitud_id
          and sp.proveedor_id = new.proveedor_id
          and not sp.considerado
    ) then
        select s.creado_por, p.nombre
        into propietario, nombre_proveedor
        from public.solicitudes_cotizacion s
        join public.proveedores p on p.id = new.proveedor_id
        where s.id = new.solicitud_id;

        insert into public.notificaciones (
            usuario_id, solicitud_id, proveedor_id, tipo,
            titulo, mensaje, datos, dedupe_key
        ) values (
            propietario, new.solicitud_id, new.proveedor_id, 'proveedor_excluido',
            'Proveedor excluido después de tres coordinaciones',
            nombre_proveedor || ' no entregó una cotización después de tres coordinaciones.',
            jsonb_build_object('coordinaciones', total),
            'exclusion-coordinaciones:' || new.solicitud_id || ':' || new.proveedor_id
        ) on conflict (dedupe_key) do nothing;
    end if;
    return new;
end;
$$;

create trigger coordinaciones_proveedor_registrar
after insert on public.coordinaciones_proveedor
for each row execute function public.registrar_coordinacion_proveedor();

create or replace function public.resolver_aclaracion_proveedor()
returns trigger
language plpgsql
as $$
declare
    sesion jsonb;
begin
    if old.estado = 'abierta' and new.estado = 'resuelta' then
        new.resuelta_at := now();
        begin
            sesion := nullif(current_setting('hasura.user', true), '')::jsonb;
            new.resuelta_por := nullif(sesion ->> 'x-hasura-user-id', '')::uuid;
        exception when others then
            new.resuelta_por := null;
        end;
    elsif new.estado = 'abierta' then
        new.resuelta_at := null;
        new.resuelta_por := null;
    end if;
    return new;
end;
$$;

create trigger aclaraciones_proveedor_resolver
before update of estado on public.aclaraciones_proveedor
for each row execute function public.resolver_aclaracion_proveedor();

create or replace function public.actualizar_estado_notificacion()
returns trigger
language plpgsql
as $$
begin
    if new.estado = 'no_leida' then
        new.leida_at := null;
        new.atendida_at := null;
    elsif new.estado = 'leida' then
        new.leida_at := coalesce(old.leida_at, now());
        new.atendida_at := null;
    elsif new.estado = 'atendida' then
        new.leida_at := coalesce(old.leida_at, now());
        new.atendida_at := now();
    end if;
    return new;
end;
$$;

create trigger notificaciones_actualizar_estado
before update of estado on public.notificaciones
for each row execute function public.actualizar_estado_notificacion();

-- Una respuesta sin cotización ya no impide el cierre sin proveedores.
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

    if new.estado = old.estado then return new; end if;
    if old.estado <> 'inicio' then
        raise exception 'Una solicitud cerrada no puede cambiar de estado';
    end if;

    if new.estado = 'cerrado' then
        if not exists (
            select 1 from public.documentos d
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
            select 1 from public.solicitud_proveedores sp
            where sp.solicitud_id = old.id
              and sp.estado_respuesta in ('envio_cotizacion', 'envio_cotizacion_con_aclaracion')
        ) or exists (
            select 1 from public.documentos d
            where d.solicitud_id = old.id
              and d.tipo = 'cotizacion_proveedor'
              and d.documento_estado = 'vigente'
        ) then
            raise exception 'La solicitud tiene al menos un proveedor con cotización';
        end if;
    else
        raise exception 'Transición de estado no permitida: % a %', old.estado, new.estado;
    end if;

    new.cerrada_at := now();
    return new;
end;
$$;
