# n8n: flujos de orquestación

n8n coordina los pasos del proceso: envía solicitudes, revisa la bandeja de correo,
llama a la app y guarda el estado. **No ejecuta la lógica de negocio**: esa vive en `app/`.

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
| `flujos/envio-solicitud-cotizacion.json` | Envía solo el itemizado y metrados a cada proveedor, registra el mensaje y cambia la solicitud a `en_proceso` | Evento de Nhost cuando `estado` cambia a `lista` | Listo para configurar |

## Configurar el primer envío

### 1. Preparar Nhost

1. Ejecuta `db/nhost/003_envios_solicitud.sql` desde **Database > SQL Console**
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
3. Selecciona `Nhost Admin` en los cinco nodos HTTP y `CostFlow Webhook` en el
   nodo `Evento de Nhost`.
4. Conecta la cuenta de envío en una credencial **Gmail OAuth2** y selecciónala
   en `Enviar correo por Gmail`.
5. Activa el flujo y copia la **Production URL** del nodo Webhook.

### 3. Disparar desde Nhost

En **Events**, crea un evento sobre `public.solicitudes_cotizacion`:

- Operación: `UPDATE`.
- Columna observada: `estado`.
- Webhook: la Production URL copiada desde n8n.
- Cabecera: el mismo nombre y valor usados en `CostFlow Webhook`.

El flujo ignora otros cambios y solo continúa cuando el estado nuevo es
`lista`. Antes de enviar verifica si ese proveedor ya tiene un envío con estado
`enviado`, por lo que una repetición del evento no duplica el correo.

## Resultado del flujo

Por cada proveedor pendiente, n8n:

1. Consulta la solicitud, proyecto, proveedor y documentos en Nhost.
2. Descarga el itemizado y metrados.
3. Envía un correo con ese único archivo adjunto mediante Gmail.
4. Registra el identificador de Gmail en `envios_solicitud`.
5. Cambia al proveedor a `invitado` y la solicitud a `en_proceso`.

La plantilla del comparativo y el cuadro de procura son insumos internos. La
generación del comparativo consolidado y la identificación de partidas críticas
corresponden a una etapa posterior; este flujo de envío aún no las realiza.
