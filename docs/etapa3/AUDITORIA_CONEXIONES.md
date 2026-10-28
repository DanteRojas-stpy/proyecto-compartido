# Comprobación de conexiones de E3 — 27/10/2026

Auditoría realizada por Codex después de configurar las credenciales del equipo.
No se ejecutó el procesamiento completo ni se habilitaron las dos banderas de E3.

## Adaptación para n8n web

La instalación auditada originalmente utilizó una credencial PostgreSQL directa
en n8n. La variante portable posterior sustituye esos tres accesos por llamadas
HTTPS a `functions/e3-operar.ts`, desplegada dentro del mismo proyecto Nhost.
PostgreSQL sigue siendo la base interna de Nhost; su contraseña y el secreto
administrativo de Hasura ya no se entregan a n8n. Esta adaptación del repositorio
debe desplegarse y probarse en Nhost antes de considerarla operativa en la web.

Se integró el trabajo de Rodrigo del PR #41 en la rama del PR #39, conservando
`gemini-3.5-flash-lite`. Se corrigió la resolución de la dirección administrativa:
el dominio público GraphQL `/v1` no sirve directamente para `run_sql`.
Nueve pruebas ejecutables del handler comprobaron autenticación, operaciones
permitidas, dirección, errores y conservación del contrato de respuesta.

Al revisar el panel de `costflow-dev`, Deployments mostró «Connect your Project
to GitHub», sin repositorio conectado. La petición de comprobación a
`/v1/e3-operar` devolvió HTTP 500 «item not found»; no confirmó una función
operativa. **Los flujos locales siguen con el acceso PostgreSQL comprobado**:
no se reemplazaron por llamadas a una función que todavía no responde. El
instalador ahora comprueba `configuracion` por HTTPS antes de modificar n8n.
La adaptación queda lista para desplegar y validar; no se afirma instalada.

| Punto del equipo | Estado y evidencia |
|---|---|
| Nhost Storage | Correcto: original descargado; CSV ficticio cargado y descargado con contenido idéntico. Temporales retirados después con respuesta 204 |
| Hasura administrativo | Correcto: exportación privada de respaldo y publicación de las consultas E3/E4 con revisión concurrente y rechazo de configuración inconsistente |
| Gemini | Correcto con `gemini-3.5-flash-lite`: generación y contrato completo de E3 validados con una cotización ficticia, usando la credencial existente de n8n |
| Gmail | Correcto: consulta aislada de un correo existente con la credencial de E3.1. No se envió correo |
| Clave interna | Correcta: servicio E3 y n8n se comunicaron mediante las entradas protegidas; PostgreSQL respondió |
| Referencias entre flujos | Los seis enlaces de invocación apuntan a los identificadores de los cinco flujos instalados; todos están publicados |
| Servicio de procesamiento | Accesible dentro de Docker por `http://costflow-etapa3:8093`; no necesita exposición pública |
| URL del frontend hacia n8n | Pendiente definir una URL pública HTTPS y los orígenes permitidos; actualmente se utiliza localhost |

## Operaciones comprobadas

1. Descargar archivo real: correcto.
2. Cargar archivo ficticio: correcto después de corregir la caché.
3. Consultar Nhost: PostgreSQL y GraphQL correctos. Se publicaron once tablas/vistas
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
  la misma clave. Se aplicó la migración 004 y se conservó el procesamiento pausado.
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

## Lo que sigue sin activarse

`recepcion_habilitada=false` y `gemini_habilitado=false`.
Falta definir cómo se alojará n8n con HTTPS, probar el frontend con la sesión real
del especialista y comprobar una corrida integrada autorizada. La prueba válida de
Gemini con datos ficticios no sustituye esas comprobaciones de toda la etapa.

La URL pública y su seguridad corresponden a quien administra n8n. El encargado
del frontend debe configurarla en la aplicación y enviar el token Nhost del usuario.
No se publicó esta computadora en Internet durante la auditoría.
