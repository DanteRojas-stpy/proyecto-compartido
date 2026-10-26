# Base de datos (PostgreSQL en Nhost)

Aquí vive la forma de los datos guardados: tablas, estados y trazabilidad.

Las solicitudes usan tres estados de negocio: `inicio`, `cerrado` y
`cerrado_sin_proveedores`. La preparación del correo se registra aparte mediante
`preparada_para_envio`; por ello el envío no modifica el estado de la solicitud.
La base de datos es **Nhost** (decisión registrada en `docs/DECISIONES.md`).

- `migraciones/`: cambios del esquema en orden numerado. Las instrucciones
  para ejecutarlas están en [migraciones/README.md](migraciones/README.md).

## Reglas

1. **Nunca cambies una tabla a mano en Nhost.** Todo cambio entra como un
   archivo SQL nuevo y numerado en `migraciones/`, por Pull Request.
2. Las migraciones ya aplicadas no se editan: se agrega una nueva que corrige.
3. Los archivos de cotizaciones (PDF, Excel) **no van aquí**: viven en Nhost
   Storage. Aquí solo se guardan las referencias y los datos extraídos.
4. Cada cotización guarda su **versión** (preliminar, corregida o final) y su
   **estado**, para no comparar documentos desactualizados.
5. Un proveedor se registra una sola vez por usuario y puede participar en
   múltiples solicitudes, incluso de proyectos distintos. La tabla
   `solicitud_proveedores` conserva cada vínculo y su estado independiente.

## Migraciones disponibles

- `001_e1_registro_solicitud.sql`: crea proyectos, solicitudes, proveedores,
  documentos y partidas.
- `002_documentos_por_proveedor.sql`: vincula cotizaciones y anexos con un
  proveedor dentro de una solicitud, con versión y estado.
- `003_envios_solicitud.sql`: registra el envío a cada proveedor para evitar
  duplicados y permitir el seguimiento.
- `004_proyectos_y_correlativos.sql`: códigos `MA` y `SC` por proyecto.
- `005_fechas_y_partida_critica.sql`: fecha límite y frecuencia de avisos según
  la ruta crítica.
- `006_estados_solicitudes.sql`: estados de la solicitud y cierre validado.
- `007_seguimiento_proveedores.sql`: respuestas, correos, aclaraciones,
  coordinaciones, auditoría y notificaciones persistentes.
- `008_revision_seguimiento_proveedores.sql`: corrige la trazabilidad entre
  correos y clasificaciones y la validación de respuestas recibidas a tiempo.
