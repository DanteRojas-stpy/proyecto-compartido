# Comprobación de conexiones de E3 — actualización 28/10/2026

Auditoría realizada por Codex después de configurar las credenciales del equipo.
No se ejecutó el procesamiento completo ni se habilitaron las dos banderas de E3.

## Adaptación para n8n web

La instalación auditada originalmente utilizó una credencial PostgreSQL directa
en n8n. La variante portable posterior sustituye esos tres accesos por llamadas
HTTPS a `functions/e3-operar.ts`, desplegada dentro del mismo proyecto Nhost.
PostgreSQL sigue siendo la base interna de Nhost. Las operaciones de base ya no
necesitan la contraseña PostgreSQL en n8n; los nodos Storage conservan su propia
credencial. La función usa la credencial administrativa proporcionada por Nhost.

Se integró el trabajo de Rodrigo del PR #41 en la rama del PR #39, conservando
`gemini-3.5-flash-lite`. Se corrigió la resolución de la dirección administrativa:
el dominio público GraphQL `/v1` no sirve directamente para `run_sql`.
Nueve pruebas ejecutables del handler comprobaron autenticación, operaciones
permitidas, dirección, errores y conservación del contrato de respuesta.

El equipo conectó el repositorio y desplegó la rama `juan-daniel/e3-reglas-y-flujos`
con directorio base `./`. Nhost conservó la configuración existente al no encontrar
`nhost/nhost.toml`; no hizo falta reemplazarla para publicar la función.
Se creó el secret `E3_INTERNAL_KEY` y su variable de entorno del mismo nombre,
referenciada mediante `{{ secrets.E3_INTERNAL_KEY }}`. Tras volver a desplegar,
se sincronizó la misma clave en el archivo privado `.env.e3`, la credencial interna
de n8n y el servicio local.

La petición directa sin clave devuelve 401 y la consulta autorizada `configuracion`
devuelve 200. Se instalaron los cinco flujos conservando Gmail, Gemini y Storage.
Los tres nodos de base de E3.1/E3.5 ya apuntan a la función HTTPS, sin nodos Postgres.
El instalador comprueba esa consulta antes de modificar n8n.

La primera comprobación a través de n8n detectó HTTP 500: dos llaves contiguas
dentro del cuerpo JSON cerraban anticipadamente la expresión. Una prueba aislada
reprodujo `ExpressionError: invalid syntax`; separar los cierres corrigió la
petición. Se regeneraron los JSON y se añadió una prueba de regresión.
Después, tanto la entrada interna de n8n como la cadena **servicio E3 → n8n →
función Nhost → base** devolvieron la configuración correcta con HTTP 200.
Se comprobó `gemini-3.5-flash-lite`, con ambas banderas todavía en `false`.
Una nueva llamada pequeña a Gemini por el flujo publicado devolvió HTTP 200 y
JSON válido, usando exclusivamente texto ficticio. La entrada del especialista
rechazó una petición sin sesión con HTTP 401. La suite completa local terminó
con 57 pruebas aprobadas y una omitida por falta de OCR en Windows.

| Punto del equipo | Estado y evidencia |
|---|---|
| Nhost Storage | Correcto: original descargado; CSV ficticio cargado y descargado con contenido idéntico. Temporales retirados después con respuesta 204 |
| Hasura administrativo | Correcto: exportación privada de respaldo y publicación de las consultas E3/E4 con revisión concurrente y rechazo de configuración inconsistente |
| Gemini | Correcto con `gemini-3.5-flash-lite`: generación y contrato completo de E3 validados con una cotización ficticia, usando la credencial existente de n8n |
| Gmail | Correcto: consulta aislada de un correo existente con la credencial de E3.1. No se envió correo |
| Clave interna y función HTTPS | Correctas: sin clave, función 401 y entrada n8n 403; con clave, ambas devuelven configuración con HTTP 200; también se comprobó desde el servicio E3 |
| Referencias entre flujos | Los seis enlaces de invocación apuntan a los identificadores de los cinco flujos instalados; todos están publicados |
| Servicio de procesamiento | Accesible dentro de Docker por `http://costflow-etapa3:8093`; no necesita exposición pública |
| URL del frontend hacia n8n | Pendiente definir una URL pública HTTPS y los orígenes permitidos; actualmente se utiliza localhost |

## Operaciones comprobadas

1. Descargar archivo real: correcto.
2. Cargar archivo ficticio: correcto después de corregir la caché.
3. Consultar Nhost: función HTTPS y GraphQL correctos. Se publicaron once tablas/vistas
   de lectura E3, sin habilitar escrituras directas del frontend en esas tablas.
4. Llamar a Gemini: correcto tras cambiar a `gemini-3.5-flash-lite`. Un ítem y
   evidencias válidas; cantidades, precios y total coinciden con la muestra ficticia.
5. OCR: prueba local con imagen, correcta.
6. RAG: siete criterios consultados, vectores de 384 dimensiones, correcto.
7. Guardar JSON: comprobado en los trece grupos SQL dentro de una transacción revertida.
8. Registrar notificación: comprobado junto con su deduplicación en la misma prueba
   SQL revertida. No se dejaron notificaciones ficticias en la bandeja del equipo.

Los permisos de lectura de GraphQL se comprobaron con el rol `user`: propietario
con tres versiones visibles y cuenta ajena sin versiones. Se utilizó una sesión
administrativa para comprobar esos filtros; una sesión JWT real desde la interfaz
continúa pendiente, al igual que la visualización y las decisiones en pantalla.

## Correcciones realizadas

- El modelo anterior, `gemini-3.8-flash`, devolvía 503. El catálogo y la prueba de
  generación identificaron `gemini-3.5-flash-lite` como alternativa disponible con
  la misma clave. Se aplicó la migración que hoy es `015_modelo_gemini_disponible.sql` (antes 004) y se conservó el procesamiento pausado.
  La llamada pasó por el nodo publicado «Gemini JSON fijo» de E3.2; su salida
  superó el esquema y las comprobaciones de datos/evidencias de E3 con una oferta
  ficticia. No se enviaron originales del equipo a Google.
- En una segunda prueba la moneda no estaba cubierta por la cita seleccionada.
  E3 rechazó esa respuesta. Se precisaron las instrucciones para exigir citas
  que cubran todos los originales y se repitió la prueba con la configuración
  real: lectura completada, 2 unidades, precio 100, parcial 200, total 236 USD.
  Se mantuvo la validación estricta y se añadió una prueba contra citas incompletas.
- E3.5 comprobaba un archivo aún inexistente antes de cargarlo. El servidor intermedio
  guardaba ese 404 y lo devolvía después de la carga. Se confirmó `HIT` en la respuesta
  errónea y 200 al evitar la caché. HEAD y GET ahora evitan reutilizar esa respuesta.
  Se conservaron las credenciales que el usuario había configurado.
- La instalación de Hasura rechazaba el lote de instrucciones propuesto. La preparación
  ahora conserva la configuración completa, modifica solo los objetos de E3 y aplica
  el resultado de forma atómica mediante `replace_metadata` versión 2. El control
  `resource_version` impide sustituir una revisión modificada por otra persona.
- Se respaldó privadamente la configuración previa. No se guardaron claves ni
  cotizaciones reales en el repositorio.

## Instalación reproducible desde cero

Se agregó `db/migraciones/011_base_versiones_cotizacion.sql` a partir del catálogo
real de Nhost, sin copiar cotizaciones ni datos personales. Crea la tabla base y
los campos de origen, Gmail y versión que faltaban en las migraciones de documentos.
Las cuatro migraciones anteriores de E3 se renombraron a 012–015 conservando su
SQL; no se deben repetir en el proyecto existente por ese cambio de nombre.
El orden único y las dependencias están en `db/ORDEN_MIGRACIONES.md`.

Se verificaron las 15 migraciones sobre PostgreSQL 18 vacío y los trece grupos de
operaciones SQL de E3. Repetir la base 011 conserva documentos, versiones y reglas.
También se comprobó que sea inocua sobre `costflow-dev` en una transacción revertida,
comparando estructura y huellas de los datos sin exportarlos.
Esta prueba de instalación no es la corrida integrada con Gmail, Gemini y JWT real.

## Lo que sigue sin activarse

`recepcion_habilitada=false` y `gemini_habilitado=false`.
Falta definir cómo se alojará n8n con HTTPS, probar el frontend con la sesión real
del especialista y comprobar una corrida integrada autorizada. La prueba válida de
Gemini con datos ficticios no sustituye esas comprobaciones de toda la etapa.

La URL pública y su seguridad corresponden a quien administra n8n. El encargado
del frontend debe configurarla en la aplicación y enviar el token Nhost del usuario.
No se publicó esta computadora en Internet durante la auditoría.
