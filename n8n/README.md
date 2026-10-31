# n8n: flujos de orquestación

n8n coordina los pasos del proceso: envía solicitudes, revisa la bandeja de
correo, llama al modelo y guarda resultados. PostgreSQL valida las reglas de
negocio y conserva la trazabilidad.

## Qué va aquí

- `flujos/`: cada flujo exportado como archivo `.json`, con un nombre claro.
  Ejemplo: `flujos/seguimiento-correo.json`.
- Este README: qué hace cada flujo, cuándo se dispara y qué variables necesita.

## Reglas

1. **Nunca subas claves, contraseñas ni tokens.** Antes de exportar, revisa el
   `.json` y reemplaza los valores sensibles por nombres de variables de entorno.
2. Un cambio en un flujo entra por Pull Request, igual que el código.
3. Documenta cada flujo aquí: qué dispara, qué entra, qué sale.

## Flujos

| Archivo | Qué hace | Se dispara con | Estado |
|---|---|---|---|
| `flujos/envio-solicitud-cotizacion.json` | Envía solo el itemizado y metrados a cada proveedor y registra el mensaje | Evento de Nhost cuando `preparada_para_envio` cambia a `true` | Listo para configurar |
| `flujos/analizar-respuestas-proveedores.json` | Recibe Gmail, correlaciona el hilo, propone si contiene cotización o ficha técnica y crea una notificación en CostFlow | Cada correo nuevo | Listo para configurar |
| `flujos/seguimiento-diario-proveedores.json` | Consolida estados y excluye proveedores vencidos | Todos los días a las 09:00, hora de Lima | Listo para configurar |
| `flujos/actualizar-estados-solicitudes.json` | Cierra las solicitudes vencidas que no obtuvieron cotizaciones | Todos los días a las 09:15, hora de Lima | Listo para configurar |
| `flujos/comparacion-plantilla-proveedores.json` | Lee las cotizaciones extraídas y compara cada precio y cantidad contra la base de la plantilla (metrado 2, costo S/ 141.344,60). Genera un CSV y un resumen con el modelo local | Manual | Borrador, sin activar. Falta el tipo de cambio aprobado |

## Configurar el primer envío

### 1. Preparar Nhost

1. Ejecuta las migraciones hasta `db/migraciones/007_seguimiento_proveedores.sql`
   desde **Database > SQL Console**
   con **Track this** activado.
2. En n8n crea una credencial **Header Auth** llamada `Nhost Admin`:
   - Name: `x-hasura-admin-secret`
   - Value: el secreto de administrador de Nhost.
3. El secreto se guarda únicamente en la credencial de n8n. Nunca se pega en
   el flujo exportado ni se sube al repositorio.

### 2. Importar y conectar n8n

1. Importa `flujos/envio-solicitud-cotizacion.json` en n8n.
2. Crea una credencial **Header Auth** llamada `CostFlow Webhook`, con un nombre
   de cabecera como `x-costflow-secret` y un valor aleatorio largo.
3. Selecciona `Nhost Admin` en los tres nodos HTTP y `CostFlow Webhook` en el
   nodo `Evento de Nhost`.
4. Conecta la cuenta de envío en una credencial **Gmail OAuth2** y selecciónala
   en `Enviar correo por Gmail`.
5. Activa el flujo y copia la **Production URL** del nodo Webhook.

### 3. Disparar desde Nhost

En **Events**, crea un evento sobre `public.solicitudes_cotizacion`:

- Operación: `UPDATE`.
- Columna observada: `preparada_para_envio`.
- Webhook: la Production URL copiada desde n8n.
- Cabecera: el mismo nombre y valor usados en `CostFlow Webhook`.

El flujo ignora otros cambios y solo continúa cuando la señal pasa de `false` a
`true`. Antes de enviar verifica que la solicitud siga en `inicio` y que ese
proveedor no tenga un envío con estado `enviado`, por lo que una repetición del
evento no duplica el correo.

## Resultado del flujo

Por cada proveedor pendiente, n8n:

1. Consulta la solicitud, proyecto, proveedor y documentos en Nhost.
2. Descarga el itemizado y metrados.
3. Envía un correo con ese único archivo adjunto mediante Gmail.
4. Registra el identificador de Gmail en `envios_solicitud`.
5. Cambia al proveedor a `invitado`. La solicitud permanece en `inicio`.

## Configurar el cierre por vencimiento

1. Importa `flujos/actualizar-estados-solicitudes.json`.
2. Selecciona `Nhost Admin` en sus dos nodos HTTP.
3. Confirma que el workflow use la zona horaria `America/Lima` y actívalo.

Cada día consulta las solicitudes cuya fecha fin ya pasó. Cuando ningún
proveedor tiene `envio_cotizacion` o `envio_cotizacion_con_aclaracion` y tampoco
existe una cotización vigente, cambia el estado a `cerrado_sin_proveedores`.
PostgreSQL vuelve a validar la regla antes de aceptar el cambio.

## Configurar el seguimiento

1. Ejecuta `scripts/configurar_nhost.py` después de las migraciones 007, 008,
   009 y 010 para crear relaciones y permisos.
2. Importa `flujos/seguimiento-diario-proveedores.json` y selecciona la
   credencial `Nhost Admin` en sus dos nodos HTTP. Configura la zona horaria del
   workflow como `America/Lima` y publícalo.
3. Importa `flujos/analizar-respuestas-proveedores.json`. Selecciona `Nhost
   Admin` en los dos nodos HTTP, la cuenta Gmail que recibe las respuestas en
   `Correo nuevo en Gmail` y `Recuperar correos recientes`, y una credencial
   propia de Google Gemini en `Modelo Gemini`.
4. Publica ambos workflows. La credencial de IA debe reemplazar el marcador
   `Gemini CostFlow`; el archivo exportado no contiene ninguna clave. El flujo
   usa una cadena LLM simple porque la clasificación no necesita memoria ni
   herramientas.

El flujo diario cuenta desde el primer envío exitoso de cada proveedor. Crea una notificación a
las 09:00 cada día para partidas críticas y cada dos días calendario para las
demás. También excluye a quien llega a tres coordinaciones sin cotización o
vence el plazo. El cierre automático se ejecuta quince minutos después.

El flujo de Gmail procesa cada mensaje por separado. Además del disparador en
tiempo real, hace un barrido cada hora de los últimos 30 días de conversaciones
con “Cotización” en el asunto para recuperar respuestas que llegaron cuando el
workflow estaba apagado. Deduplica por
`message_id`, por lo que el barrido no repite clasificaciones ni alertas.
Correlaciona primero por `thread_id` y usa correo, empresa, asunto, código y
contexto como respaldo. Para cada correo propone únicamente **Respuesta sin
nueva cotización ni ficha técnica** o **Cotización o ficha técnica recibida**.
La IA nunca propone la aceptación final. El especialista revisa todos los
correos en CostFlow, confirma o cambia su estado y Nhost conserva el historial.
Los mensajes antiguos permanecen como registros independientes y no se
sobrescriben entre sí.

Los correos con cotización o ficha técnica quedan disponibles para que E3
recupere y verifique la información. Los correos posteriores a la fecha límite
quedan registrados, pero no generan notificaciones ni reincorporan al
proveedor. Todas las notificaciones se muestran en CostFlow; este proceso no
envía un resumen por correo al usuario.

### Recuperar respuestas omitidas

Después de reemplazar una versión anterior del flujo:

1. Ejecuta las migraciones 008, 009 y 010 que todavía no estén aplicadas.
2. Vuelve a seleccionar las credenciales de Nhost, Gmail y Gemini y publica el
   workflow.
3. Ejecuta una vez `Revisión horaria de correos` o espera al siguiente cambio
   de hora.
4. Comprueba que cada proveedor que respondió muestre todos sus correos, una
   notificación individual y un estado preliminar por correo.

Los correos ya clasificados con la versión anterior se revisan una sola vez.
Las notificaciones conservan su identificador y actualizan su texto, de modo
que esta recuperación no crea duplicados.

Los nodos HTTP usan el endpoint directo de Hasura (`/v1/graphql`). Es necesario
cuando Nhost no acepta el secreto administrativo a través del gateway público.
Los adjuntos se conservan en Gmail y el flujo registra su nombre, tipo y tamaño;
la descarga permanente y lectura del contenido pertenecen a la etapa de
recepción documental.

La versión del flujo en este repositorio ya omite la antigua vigencia en días
del mensaje. Después de aplicar la migración 005, actualiza el flujo publicado
en n8n y publica una nueva versión para que el correo use solo la fecha fin.

La plantilla del comparativo y el cuadro de procura son insumos internos. La
generación del comparativo consolidado y la identificación de partidas críticas
corresponden a una etapa posterior; este flujo de envío aún no las realiza.
