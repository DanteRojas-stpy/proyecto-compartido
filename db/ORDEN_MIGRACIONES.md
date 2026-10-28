# Orden de migraciones

Ejecutar en Nhost (**Database > SQL Console**), una sola vez y en este orden, en una base nueva.
En la base actual de pruebas, las que ya están aplicadas no se vuelven a ejecutar.

## 1. Base de `db/migraciones/` (en `main`)

| Paso | Archivo | Qué crea o cambia | Depende de |
|---|---|---|---|
| 1 | `001_e1_registro_solicitud.sql` | proyectos, solicitudes, proveedores, documentos, partidas | auth de Nhost |
| 2 | `002_documentos_por_proveedor.sql` | vínculo de cotizaciones y anexos con proveedor y versión | 001 |
| 3 | `003_envios_solicitud.sql` | envíos a cada proveedor | 001 |
| 4 | `004_proyectos_y_correlativos.sql` | códigos MA y SC | 001 |
| 5 | `005_fechas_y_partida_critica.sql` | fecha límite y ruta crítica | 001 |
| 6 | `006_estados_solicitudes.sql` | estados de la solicitud | 001 |
| 7 | `007_seguimiento_proveedores.sql` | respuestas, correos, aclaraciones, notificaciones | 001, 003 |
| 8 | `008_revision_seguimiento_proveedores.sql` | trazabilidad de correos | 007 |
| 9 | `009_respuestas_con_ficha_tecnica.sql` | ficha técnica sin oferta | 007 |
| 10 | `010_estados_por_correo.sql` | estados y auditoría por correo | 007 |

## 2. Base de `versiones_cotizacion` (**pendiente**)

**Problema:** las migraciones de los pasos 1 a 10 no crean la tabla `versiones_cotizacion`, pero la migración E3 `db/etapa3/001_entidades.sql` la modifica. Hoy existe en Nhost porque se creó fuera del repositorio.

**Solución prevista:** una migración `011_versiones_cotizacion.sql` con `CREATE TABLE IF NOT EXISTS` y la misma estructura que tiene la tabla en Nhost. Queda pendiente hasta confirmar esa estructura con la consulta a `information_schema`.

## 3. Migraciones de E3 (`db/etapa3/`, rama de Juan, PR #39)

Solo después del paso 2 completo.

| Paso | Archivo | Qué hace | Depende de |
|---|---|---|---|
| 12 | `db/etapa3/001_entidades.sql` | agrega columnas y restricciones a `versiones_cotizacion` | 011 |
| 13 | `db/etapa3/002_procesamiento.sql` | procesamiento y numeración de versiones | 12 |
| 14 | `db/etapa3/003_decisiones_y_salida.sql` | decisiones, vista `e3_finales_e4` | 13 |
| 15 | `db/etapa3/004_modelo_gemini_disponible.sql` | modelo de Gemini disponible | 14 |

**Nota de numeración:** los archivos de E3 usan su propia numeración (001 a 004), que choca con la de `db/migraciones/`. Al integrarlos en `main` se renumeran como 012 a 015 y se actualiza esta tabla.

## Antes de ejecutar

1. Hacer una copia de seguridad de la base.
2. Ejecutar en una base de pruebas primero.
3. No editar una migración ya aplicada: si algo falla, se agrega una nueva que corrige.
