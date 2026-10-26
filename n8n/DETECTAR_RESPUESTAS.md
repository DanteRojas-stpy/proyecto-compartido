# Detectar respuestas de proveedores

El flujo `flujos/detectar-respuestas-proveedores.json` lee los correos nuevos
de la cuenta que envía las solicitudes. Cada minuto revisa mensajes leídos y
no leídos, sin marcar ninguno como leído ni enviar correos.

## Conexión en n8n

1. Importa el JSON. Se crea desactivado.
2. En **Leer respuestas en Gmail** y **Consultar envío original en Gmail**,
   selecciona la misma credencial **Gmail OAuth2** usada para los envíos.
   La conexión debe permitir leer mensajes. Si aún no existe, inicia la conexión
   desde n8n con la persona que administra el correo.
3. En **Buscar envíos al proveedor** y **Consultar datos de la solicitud**,
   selecciona **Header Auth** con nombre `Nhost Admin`, cabecera
   `x-hasura-admin-secret` y el secreto configurado en la credencial de n8n.
   No pegues ese secreto dentro del JSON.
4. Las direcciones HTTP apuntan al proyecto Nhost de CostFlow. Si usas otro
   proyecto, cambia la URL en ambos nodos HTTP.
5. Prueba como se indica abajo. Después publica/activa el flujo y mantén n8n
   encendido para la revisión de cada minuto.

No necesita tablas ni migraciones nuevas. Usa `envios_solicitud`,
`solicitudes_cotizacion`, `proveedores` y la relación `proyecto_asociado`,
que ya utiliza el flujo de envío. Nhost debe tenerlas disponibles en GraphQL.

## Cómo reconoce una respuesta

1. Lee el remitente real del campo From y busca los envíos registrados para
   esa dirección. No utiliza nombres de presentación ni coincidencias parciales.
2. Consulta en Gmail el mensaje de envío guardado en `envios_solicitud.mensaje_id`.
3. Compara el identificador de conversación de ese mensaje con el de la respuesta.
   Comprueba que el original sea un mensaje enviado y que la respuesta no sea
   anterior al envío, cuando las fechas están disponibles.
4. Si existe una sola coincidencia, muestra proveedor, proyecto, código de
   solicitud, partida, fecha, asunto, ambos identificadores de Gmail y enlace
   a la conversación. Los resultados quedan en las ejecuciones de n8n.

Así puede distinguir solicitudes del mismo proveedor, incluso entre proyectos
con códigos repetidos o cuando cambia el asunto dentro de la misma conversación.
El remitente es un dato del correo, no una prueba de identidad del proveedor.

Un correo de una dirección sin envíos registrados se ignora. Si el remitente es
conocido pero la conversación es diferente, hay más de una solicitud posible o
no se puede consultar el original, sale por **Revisar conversación manualmente**
con el motivo. No se le asigna una solicitud automáticamente. El envío debe estar
en estado `enviado` o `respondido` y tener su `mensaje_id` de Gmail guardado.

El correo debe responder al mensaje original. Si un proveedor cambia de
dirección o abre otra conversación, requiere revisión y actualización de sus
datos. Un fallo de Nhost detiene esa ejecución y debe revisarse/reintentarse
desde n8n; no se convierte en una detección correcta ni en una lista vacía.

## Prueba con un correo real

1. Crea una solicitud con una dirección de prueba que controles y comprueba
   que el flujo de Rodrigo haya enviado y registrado el mensaje en Nhost.
2. Desde esa dirección, responde al correo original.
3. En el disparador de Gmail, **Fetch Test Event** toma el correo más reciente
   que cumpla los filtros. Ejecuta el resto del flujo. Comprueba que salga en
   **Respuesta de proveedor detectada** con la solicitud correcta.
4. Haz otra solicitud al mismo proveedor y responde a su segundo correo.
   Comprueba que la detección conserve la diferencia entre ambas solicitudes.
5. Envía, desde esa misma dirección, un correo nuevo sin responder a la
   conversación anterior: debe pasar a revisión manual.

En funcionamiento automático se revisan mensajes nuevos desde la activación;
no se importa todo el historial. La prueba manual del disparador solo toma el
último mensaje disponible. Las ejecuciones guardadas contienen metadatos del
correo; respeta la configuración de acceso y retención de tu instalación.

## Alcance de esta primera versión

Detecta respuestas, con o sin adjuntos. No descarga archivos, no analiza el
contenido con IA, no escribe en PostgreSQL, no envía avisos y no cambia estados
de proveedores ni declara una cotización final. Es la entrada para conectar
posteriormente la recepción de adjuntos y el análisis de E3.

## Mantenimiento y pruebas

Las reglas de identificación viven en `app/correo/deteccion.js`. El generador
las incluye dentro de los nodos Code para que el JSON pueda importarse sin
instalar módulos dentro de n8n. Después de modificar las reglas, regenera:

```powershell
.venv\Scripts\python.exe scripts\generar_flujo_recepcion.py
node --test tests/test_deteccion_correo.cjs
```

Referencias oficiales: [Gmail en n8n](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.gmail/message-operations/)
y [los identificadores de mensajes y conversaciones de Gmail](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages).
