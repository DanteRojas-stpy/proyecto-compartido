# Base de datos (PostgreSQL / Nhost)

Aquí vive la forma de los datos guardados: tablas, estados y trazabilidad.

- `migraciones/`: cambios del esquema en orden numerado, por ejemplo
  `001_proveedores.sql`, `002_cotizaciones.sql`.

## Reglas

1. **Nunca cambies una tabla a mano en Nhost.** Todo cambio entra como un
   archivo SQL nuevo y numerado en `nhost/`, por Pull Request.
2. Las migraciones ya aplicadas no se editan: se agrega una nueva que corrige.
3. Los archivos de cotizaciones (PDF, Excel) **no van aquí**: viven en Nhost
   Storage. Aquí solo se guardan las referencias y los datos extraídos.
4. Cada cotización guarda su **versión** (preliminar, corregida o final) y su
   **estado**, para no comparar documentos desactualizados.

## Migraciones disponibles

- `migraciones/001_e1_registro_solicitud.sql`: crea proyectos, solicitudes,
  proveedores reutilizables, documentos y partidas. También crea el bucket
  privado `solicitudes` y las políticas que limitan cada registro y archivo a
  su usuario responsable.
- `nhost/001_e1_registro_solicitud.sql`: variante para Nhost. Crea el modelo
  relacional; los permisos GraphQL y Storage se configuran después en Nhost.
- `nhost/002_documentos_por_proveedor.sql`: vincula las cotizaciones y anexos
  con un proveedor concreto dentro de una solicitud y conserva sus versiones.
- `nhost/003_envios_solicitud.sql`: registra el envío de la solicitud a cada
  proveedor para evitar duplicados y permitir el seguimiento por correo.
