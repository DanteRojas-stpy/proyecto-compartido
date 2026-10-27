-- Distingue una respuesta con documentación técnica de una ausencia de respuesta.
-- Ejecutar una vez después de 008_revision_seguimiento_proveedores.sql.

begin;

alter table public.solicitud_proveedores
    drop constraint solicitud_proveedores_detalle_respuesta_valido,
    add constraint solicitud_proveedores_detalle_respuesta_valido
        check (detalle_respuesta in (
            'sin_respuesta',
            'confirmo_recepcion',
            'ficha_tecnica_sin_cotizacion',
            'consulta_previa',
            'rechazo_participar',
            'aclaraciones_pendientes',
            'cotizacion_definitiva',
            'tres_coordinaciones',
            'plazo_vencido'
        ));

create or replace function public.validar_respuesta_proveedor()
returns trigger
language plpgsql
as $$
declare
    limite date;
    fecha_referencia date;
    sesion jsonb;
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
            'sin_respuesta', 'confirmo_recepcion',
            'ficha_tecnica_sin_cotizacion', 'consulta_previa',
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

    -- Las correcciones hechas desde el frontend siempre quedan como decisión
    -- del usuario, aunque el navegador no pueda editar esta columna protegida.
    begin
        sesion := nullif(current_setting('hasura.user', true), '')::jsonb;
        if sesion ->> 'x-hasura-role' = 'user' then
            new.origen_clasificacion := 'usuario';
        end if;
    exception when others then
        null;
    end;

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

commit;
