# Base de datos (PostgreSQL / Supabase)

Aquí vive la forma de los datos guardados: tablas, estados y trazabilidad.

- `migraciones/`: cambios del esquema en orden numerado, por ejemplo
  `001_proveedores.sql`, `002_cotizaciones.sql`.

## Reglas

1. **Nunca cambies una tabla a mano en Supabase.** Todo cambio entra como un
   archivo nuevo en `migraciones/`, por Pull Request.
2. Las migraciones ya aplicadas no se editan: se agrega una nueva que corrige.
3. Los archivos de cotizaciones (PDF, Excel) **no van aquí**: viven en Supabase
   Storage. Aquí solo se guardan las referencias y los datos extraídos.
4. Cada cotización guarda su **versión** (preliminar, corregida o final) y su
   **estado**, para no comparar documentos desactualizados.
