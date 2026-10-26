---
name: estado-solicitudes-cotizacion
description: Aplicar y verificar los estados de negocio de una solicitud de cotización en CostFlow, incluidos el cierre manual con cuadro comparativo y el cierre automático por vencimiento sin proveedores.
---

# Estado de solicitudes de cotización

Usar esta Skill al crear, consultar, cerrar o automatizar el vencimiento de una
solicitud de cotización.

## Estados permitidos

| Estado visible | Valor almacenado | Regla |
|---|---|---|
| Inicio | `inicio` | Se asigna al crear la solicitud y se mantiene durante el envío, seguimiento y recepción de ofertas. |
| Cerrado | `cerrado` | El usuario lo selecciona cuando existe un documento vigente de tipo `cuadro_comparativo`. |
| Cerrado sin proveedores | `cerrado_sin_proveedores` | Se asigna automáticamente después de la fecha fin cuando no existe respuesta ni cotización vigente de ningún proveedor. |

Los estados de cierre son finales. No reabrir ni cambiar una solicitud después
del cierre.

## Reglas de aplicación

1. Crear toda solicitud en `inicio`.
2. Mantener `preparada_para_envio` como señal técnica independiente. Enviar
   correos no cambia el estado de negocio.
3. Antes del cierre manual, comprobar que haya un documento vigente con tipo
   `cuadro_comparativo` para la solicitud.
4. Ejecutar a diario el control de vencimiento con la fecha de Lima. La fecha
   fin debe ser anterior al día de ejecución.
5. Considerar que se consiguió un proveedor cuando existe al menos uno de estos
   registros para la solicitud:
   - un vínculo en `solicitud_proveedores` con estado `respondio`;
   - un documento vigente de tipo `cotizacion_proveedor`.
6. Si no se consiguió ningún proveedor, cambiar el estado a
   `cerrado_sin_proveedores`.

PostgreSQL valida estas transiciones. Si una operación incumple las reglas,
mostrar el mensaje recibido y conservar el estado anterior.
