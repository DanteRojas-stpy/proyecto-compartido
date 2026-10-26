---
name: seguimiento-proveedores
description: Aplicar las reglas de seguimiento por correo, clasificación de respuestas, coordinaciones y notificaciones de proveedores en CostFlow.
---

# Seguimiento de proveedores

Usar esta Skill para recibir y clasificar correos de proveedores, programar
recordatorios, registrar coordinaciones o mostrar notificaciones de una
solicitud de cotización.

## Estados de respuesta

| Estado | Valor | Uso |
|---|---|---|
| No envió cotización | `no_envio_cotizacion` | No entregó una oferta válida. El detalle distingue falta de respuesta, confirmación, consulta, rechazo o exclusión. |
| Envió cotización con aclaración | `envio_cotizacion_con_aclaracion` | Hay una oferta, pero mantiene aclaraciones abiertas. Cuenta como proveedor obtenido. |
| Envió cotización | `envio_cotizacion` | Es la versión definitiva y no tiene aclaraciones abiertas. |

## Reglas

1. Iniciar el calendario con el primer envío exitoso al proveedor.
2. Generar notificaciones a las 09:00, hora de Lima, cada día calendario si la
   partida es crítica y cada dos días calendario en los demás casos.
3. Mostrar esas notificaciones únicamente en CostFlow. Una respuesta nueva se
   notifica en tiempo real.
4. Correlacionar por `thread_id` de Gmail. Como respaldo, utilizar correo,
   empresa, asunto normalizado, código y contexto de la solicitud.
5. Procesar cada `message_id` una sola vez para no duplicar estados,
   aclaraciones o notificaciones.
6. Usar IA solo para interpretar el correo y comparar su contexto con el
   historial. n8n controla fechas y PostgreSQL valida y conserva los estados.
7. Marcar una cotización como definitiva únicamente con evidencia y sin
   aclaraciones abiertas. Con confianza menor de 0.8, solicitar revisión del
   usuario y no cambiar el estado automáticamente.
8. Permitir que el usuario corrija una clasificación y conservar la original en
   el historial de auditoría.
9. El botón **Coordinación** registra medio, fecha, usuario y comentario. El
   envío automático inicial no cuenta. Después de tres coordinaciones sin
   cotización, excluir al proveedor.
10. Excluir al proveedor al cumplir tres coordinaciones sin cotización o al
    vencer la fecha límite, lo que ocurra primero. No enviarle más recordatorios.
11. Guardar correos tardíos como evidencia, sin notificar, reincorporar al
    proveedor ni cambiar su estado.
