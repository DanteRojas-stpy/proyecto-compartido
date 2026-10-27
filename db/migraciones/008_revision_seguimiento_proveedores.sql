-- Ajustes de trazabilidad y validación detectados durante la revisión integral.
-- Ejecutar una vez después de 007_seguimiento_proveedores.sql.

create or replace function public.validar_respuesta_proveedor()
returns trigger
language plpgsql
as $$
declare
    limite date;
    fecha_referencia date;
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

        fecha_referencia := coalesce(
            (new.ultimo_correo_at at time zone 'America/Lima')::date,
            (now() at time zone 'America/Lima')::date
        );
        if limite < fecha_referencia
           and new.estado_respuesta <> 'no_envio_cotizacion' then
            raise exception 'La respuesta llegó después de la fecha límite y no puede reincorporar al proveedor';
        end if;
    end if;

    if new.estado_respuesta in ('envio_cotizacion', 'envio_cotizacion_con_aclaracion') then
        new.considerado := true;
    end if;
    if not new.considerado then
        new.estado_respuesta := 'no_envio_cotizacion';
    end if;

    -- Una corrección manual no debe conservar la confianza o evidencia de la IA.
    -- La tercera coordinación cambia el contador y conserva su evidencia propia.
    if new.origen_clasificacion = 'usuario'
       and new.numero_coordinaciones is not distinct from old.numero_coordinaciones
       and row(old.estado_respuesta, old.detalle_respuesta, old.considerado)
           is distinct from row(new.estado_respuesta, new.detalle_respuesta, new.considerado) then
        new.confianza_clasificacion := null;
        new.evidencia_clasificacion := '[]'::jsonb;
    end if;

    return new;
end;
$$;

create or replace function public.auditar_respuesta_proveedor()
returns trigger
language plpgsql
as $$
declare
    sesion jsonb;
    actor uuid;
    correo_asociado uuid;
begin
    if row(old.estado_respuesta, old.detalle_respuesta, old.considerado)
       is distinct from row(new.estado_respuesta, new.detalle_respuesta, new.considerado) then
        begin
            sesion := nullif(current_setting('hasura.user', true), '')::jsonb;
            actor := nullif(sesion ->> 'x-hasura-user-id', '')::uuid;
        exception when others then
            actor := null;
        end;

        if new.origen_clasificacion = 'agente' and new.ultimo_correo_at is not null then
            select c.id into correo_asociado
            from public.correos_proveedor c
            where c.solicitud_id = new.solicitud_id
              and c.proveedor_id = new.proveedor_id
              and c.recibido_at = new.ultimo_correo_at
            order by c.created_at desc
            limit 1;
        end if;

        insert into public.historial_respuestas_proveedor (
            solicitud_id, proveedor_id, correo_id,
            estado_anterior, estado_nuevo,
            detalle_anterior, detalle_nuevo,
            considerado_anterior, considerado_nuevo,
            origen, confianza, evidencia, cambiado_por
        ) values (
            new.solicitud_id, new.proveedor_id, correo_asociado,
            old.estado_respuesta, new.estado_respuesta,
            old.detalle_respuesta, new.detalle_respuesta,
            old.considerado, new.considerado,
            new.origen_clasificacion,
            case when new.origen_clasificacion = 'usuario' then null else new.confianza_clasificacion end,
            case when new.origen_clasificacion = 'usuario' then '[]'::jsonb else new.evidencia_clasificacion end,
            actor
        );
    end if;
    return new;
end;
$$;
