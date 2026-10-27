---
name: seguimiento-proveedores
description: Aplicar las reglas de seguimiento por correo, clasificación de respuestas, coordinaciones y notificaciones de proveedores en CostFlow.
---

# Seguimiento de proveedores

Usar esta Skill para recibir y clasificar correos de proveedores, programar
recordatorios, registrar coordinaciones o mostrar notificaciones de una
solicitud de cotización.

## Estados de cada correo

| Estado | Valor | Uso |
|---|---|---|
| Respuesta sin nueva cotización ni ficha técnica | `respuesta_sin_nueva_cotizacion_ni_ficha_tecnica` | Confirmó recepción sin adjuntar esos documentos, realizó una consulta, rechazó participar o envió otra comunicación sin documentación nueva. |
| Cotización o ficha técnica recibida | `cotizacion_o_ficha_tecnica_recibida` | n8n detectó documentación económica o técnica. El usuario confirma o cambia el estado y E3 recupera y verifica la información. |
| Cotización o ficha técnica aceptada como final | `cotizacion_o_ficha_tecnica_aceptada_final` | El especialista acepta la información recuperada por E3 y no existen aclaraciones abiertas. n8n nunca asigna este estado. |

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
6. Usar IA solo para asociar el correo y proponer si contiene cotización o ficha
   técnica. n8n nunca acepta información como final.
7. Mostrar todos los correos en el frontend. El usuario confirma o cambia el
   estado de cada uno y PostgreSQL conserva la propuesta y cada decisión.
8. Aceptar como final únicamente por decisión del especialista, con el documento
   registrado por E3 y sin aclaraciones abiertas.
9. El botón **Coordinación** registra medio, fecha, usuario y comentario. El
   envío automático inicial no cuenta. Después de tres coordinaciones sin
   cotización, excluir al proveedor.
10. Excluir al proveedor al cumplir tres coordinaciones sin cotización o al
    vencer la fecha límite, lo que ocurra primero. No enviarle más recordatorios.
11. Guardar correos tardíos como evidencia, sin notificar, reincorporar al
    proveedor ni cambiar su estado.
