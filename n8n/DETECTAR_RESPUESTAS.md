# Detectar respuestas y guardar PDF de proveedores

El flujo `flujos/detectar-respuestas-proveedores.json` lee los correos nuevos
de la cuenta que envía las solicitudes. Cada minuto revisa mensajes leídos y
no leídos, sin marcar ninguno como leído ni enviar correos. Al identificar la
solicitud, descarga todos los PDF adjuntos de esa respuesta y los guarda en
el bucket `cotizaciones` de Nhost Storage.

## Conexión en n8n

1. Importa el JSON. Se crea desactivado.
2. En **Leer respuestas en Gmail**, **Consultar envío original en Gmail** y
   **Descargar adjuntos de la respuesta**,
   selecciona la misma credencial **Gmail OAuth2** usada para los envíos.
   La conexión debe permitir leer mensajes. Si aún no existe, inicia la conexión
   desde n8n con la persona que administra el correo.
3. En **Buscar envíos al proveedor**, **Consultar datos de la solicitud**,
   **Comprobar PDF en Nhost Storage** y **Guardar PDF en Nhost Storage**,
   selecciona **Header Auth** con nombre `Nhost Admin`, cabecera
   `x-hasura-admin-secret` y el secreto configurado en la credencial de n8n.
   No pegues ese secreto dentro del JSON.
4. Las direcciones HTTP apuntan al proyecto Nhost de CostFlow: dos usan
   GraphQL y dos usan Storage. Si usas otro proyecto, cambia esos cuatro
   nodos. El bucket `cotizaciones` debe existir y permitir PDF del tamaño recibido.
5. Prueba como se indica abajo. Después publica/activa el flujo y mantén n8n
   encendido para la revisión de cada minuto.

No necesita tablas ni migraciones nuevas. Usa `envios_solicitud`,
`solicitudes_cotizacion`, `proveedores` y la relación `proyecto_asociado`,
que ya utiliza el flujo de envío. Nhost debe tenerlas disponibles en GraphQL.

## Guardado de los PDF

Solo se descargan los adjuntos después de identificar la solicitud y el
proveedor. Se guardan todos los PDF de esa respuesta, tanto fichas técnicas
como cotizaciones u otros PDF; se ignoran imágenes, Excel y otros formatos.
La extensión `.pdf` o el tipo `application/pdf` sirven para seleccionar los
candidatos y se comprueba la cabecera binaria PDF antes de subirlos. Esto no
reemplaza un análisis completo de integridad del documento.

Cada archivo lleva un nombre legible y metadatos de `solicitud_id`,
`proveedor_id`, `gmail_message_id`, `gmail_thread_id`, nombre original y origen
Gmail. Estas referencias se guardan en **Storage**, no se insertan todavía en
la tabla `documentos` ni se asignan versiones de cotización.
El control de cierre por vencimiento de E2 consulta las tablas de negocio:
guardar un archivo en Storage no registra por sí solo el estado `respondio`.
Hasta conectar ese registro, el especialista debe actualizarlo en su proceso
de seguimiento para que una respuesta recibida no se cuente como ausente.

El identificador del archivo se calcula de forma reproducible a partir de la
bucket, solicitud, proveedor, correo y posición del adjunto. Antes de subirlo, el flujo
consulta Storage con HEAD. Un archivo existente con tamaño, tipo y ETag válidos
sale por **PDF ya guardado anteriormente**. Uno inexistente se sube con ese
mismo identificador. Un reintento no crea otra copia del mismo adjunto; una
respuesta nueva conserva su propio archivo. Dos PDF con el mismo nombre en
un correo también permanecen separados.

Solo se muestra **PDF guardado y vinculado** cuando Storage confirma el
identificador, bucket, tamaño y carga completa. Errores de acceso, límite de
tamaño, cuota o carga interrumpen la ejecución. Si dos ejecuciones intentan
crear simultáneamente el mismo archivo, la unicidad de su ID impide otra
copia; una puede fallar y debe reintentarse desde el principio. No se reemplaza
ni se borra un archivo existente automáticamente.

Las respuestas sin PDF y los archivos que no tienen cabecera PDF quedan en
**Respuesta sin PDF o archivo rechazado** con el motivo. Los enlaces a PDF
dentro del cuerpo del correo no se descargan. Los permisos del bucket no se
cambian; la visibilidad desde el front requiere sus permisos de Storage.

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
2. Desde esa dirección, responde al correo original con dos PDF adjuntos y una
   imagen. Se deben guardar los dos PDF y omitir la imagen.
3. En el disparador de Gmail, **Fetch Test Event** toma el correo más reciente
   que cumpla los filtros. Ejecuta el resto del flujo. Comprueba que salga en
   **PDF guardado y vinculado** con la solicitud correcta. Verifica los archivos
   y sus metadatos en Nhost > Storage > cotizaciones.
4. Haz otra solicitud al mismo proveedor y responde a su segundo correo.
   Comprueba que la detección conserve la diferencia entre ambas solicitudes.
5. Envía, desde esa misma dirección, un correo nuevo sin responder a la
   conversación anterior: debe pasar a revisión manual y no subir adjuntos.
6. Repite la ejecución del mismo correo: los archivos deben salir como ya
   guardados. Prueba también una respuesta sin PDF y una con un archivo de texto
   renombrado `.pdf`: deben mostrarse sin carga o rechazadas, respectivamente.

En funcionamiento automático se revisan mensajes nuevos desde la activación;
no se importa todo el historial. La prueba manual del disparador solo toma el
último mensaje disponible. Las ejecuciones guardadas contienen metadatos del
correo; respeta la configuración de acceso y retención de tu instalación.

## Alcance

Detecta respuestas y guarda sus PDF en Storage. No analiza el contenido con IA,
no registra documentos en las tablas de negocio de PostgreSQL, no envía avisos
y no cambia estados de proveedores ni declara una cotización final. El guardado
en Storage sí genera sus propios registros internos de archivos en Nhost.

## Mantenimiento y pruebas

### Paso de datos a E3.1

Cuando ya esté instalado E3.1, la llamada `Registrar cotización (E3.1)` debe
ejecutarse una vez con todos los archivos y esperar su resultado. E3.1 acepta
todos los campos del detector. Una ejecución manual de E3.1 sin esos datos
debe mostrar un error de entrada, en lugar de terminar como correcta con cero
archivos. La ejecución del detector y la prueba manual independiente tienen
historias distintas en n8n; abrir E3.1 no recupera automáticamente resultados
de ejecuciones anteriores.

Para corregir una exportación existente conservando credenciales y otros nodos:

```powershell
.venv\Scripts\python.exe scripts\asegurar_entrada_e31.py detector detector-exportado.json detector-corregido.json
.venv\Scripts\python.exe scripts\asegurar_entrada_e31.py recepcion e31-exportado.json e31-corregido.json
```

El ajuste de E3.1 también diferencia la recepción guardada de la lectura:
si E3.2 no está publicado o configurado, conserva `version_id` y muestra
`estado_recepcion: registrado` y `estado_lectura: pendiente`, con el motivo.
La lectura con IA queda pendiente de configurar; no se crean credenciales ni
se envían avisos automáticamente durante esta corrección.

Las reglas de identificación viven en `app/correo/deteccion.js` y las de
adjuntos en `app/recepcion/adjuntos.js`. El generador las incluye dentro de los nodos Code para que el JSON pueda importarse sin
instalar módulos dentro de n8n. Después de modificar las reglas, regenera:

```powershell
.venv\Scripts\python.exe scripts\generar_flujo_recepcion.py
node --test tests/test_deteccion_correo.cjs tests/test_adjuntos_pdf.cjs
```

Referencias oficiales: [Gmail en n8n](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.gmail/message-operations/)
y [los identificadores de mensajes y conversaciones de Gmail](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages).
La carga usa [multipart de n8n](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/)
y el contrato oficial de [Nhost Storage](https://pkg.go.dev/github.com/nhost/nhost/services/storage/api#UploadFileMetadata).
