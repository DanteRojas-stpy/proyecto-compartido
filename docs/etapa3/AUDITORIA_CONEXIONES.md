# Comprobación de conexiones de E3 — 27/10/2026

Auditoría realizada por Codex después de configurar las credenciales del equipo.
No se ejecutó el procesamiento completo ni se habilitaron las dos banderas de E3.

| Punto del equipo | Estado y evidencia |
|---|---|
| Nhost Storage | Correcto: original descargado; CSV ficticio cargado y descargado con contenido idéntico. Temporales retirados después con respuesta 204 |
| Hasura administrativo | Correcto: exportación privada de respaldo y publicación de las consultas E3/E4 con revisión concurrente y rechazo de configuración inconsistente |
| Gemini | Clave válida para consultar modelos, incluido el configurado. Generación pequeña todavía devuelve 503 por alta demanda: pendiente obtener una lectura válida |
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
4. Llamar a Gemini: la llamada llega a Google; la generación todavía responde 503.
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
Falta obtener una respuesta válida de Gemini, definir cómo se alojará n8n con HTTPS
y probar el frontend con la sesión real del especialista. Crear una clave no prueba
por sí solo el funcionamiento de toda la etapa.

La URL pública y su seguridad corresponden a quien administra n8n. El encargado
del frontend debe configurarla en la aplicación y enviar el token Nhost del usuario.
No se publicó esta computadora en Internet durante la auditoría.
