# Acuerdo para el frontend, E3 y E4

La segunda parte no es un notificador: **registra la decisión del especialista**.
La identificación se obtiene de la sesión Nhost y el acceso se comprueba en el servidor.
El cuerpo no debe enviar una identidad confiable ni una clave administrativa.

## Consultas de pantalla

Pendiente publicar estas vistas con `scripts/configurar_etapa3_nhost.py` y verificar
el acceso con el JWT del usuario. Todas las consultas se hacen con rol `user`.

Lista de versiones de una solicitud y proveedor:

```graphql
query VersionesE3($solicitud: uuid!, $proveedor: uuid!) {
  e3_bandeja_versiones(
    where: {solicitud_id: {_eq: $solicitud}, proveedor_id: {_eq: $proveedor}}
    order_by: {numero_version: desc}
  ) {
    version_id correo_id numero_version es_final recibido_at estado_correo
    estado_procesamiento intentos legado error_visible documentos
  }
}
```

La lista incluye pendientes y errores, no solo lecturas completadas. `legado=true`
identifica registros conservados de la implementación anterior; no significa que
ya se hayan validado con el nuevo contrato. La fecha del correo y el número de
versión deben mostrarse separados. Ordenar por número no selecciona la final.
Para un legado pendiente se puede ofrecer «Preparar con las nuevas reglas»,
usando la URL de reintentos después de confirmar el correo en E2. Es una autorización
explícita, nunca una relectura automática por cambiar la final. Se reutiliza la
versión y sus documentos existentes y se conserva la lectura antigua en sus tablas.

Detalle de una lectura terminada:

```graphql
query DetalleE3($version: uuid!) {
  e3_versiones_estructuradas(where: {version_id: {_eq: $version}}) {
    version_id correo_id solicitud_id proveedor_id numero_version es_final
    estado_procesamiento resultado
  }
}
```

`resultado` contiene documentos, valores comerciales, ítems, especificaciones,
evidencias, observaciones y decisiones actualizadas. Las observaciones conservan
su estado y motivo de descarte; no se eliminan de la historia.

## Peticiones a n8n

URL local de decisiones: `http://localhost:5678/webhook/costflow-e3-especialista`.
URL local de reintentos: `http://localhost:5678/webhook/costflow-e3-reintentar`.

Cabeceras:

```text
Authorization: Bearer <accessToken de la sesión Nhost>
Content-Type: application/json
```

Ejemplo con el cliente Nhost que ya utiliza el frontend:

```javascript
const sesion = nhost.getUserSession();
if (!sesion?.accessToken) throw new Error("Inicia sesión nuevamente.");
const peticion = {
  accion: "aceptar_version",
  version_id: versionSeleccionada,
  accion_id: crypto.randomUUID()
};
// Conservar peticion.accion_id si se reenvía por un corte de conexión.
const respuesta = await fetch(URL_DECISIONES, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${sesion.accessToken}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify(peticion)
});
const resultado = await respuesta.json();
if (!respuesta.ok || !resultado.ok) throw new Error(resultado.mensaje);
// Mostrar resultado.mensaje y recargar consultas y notificaciones.
```

Acciones aceptadas:

| Acción | Datos necesarios | Efecto |
|---|---|---|
| `aceptar_version` | `version_id` | Cambia la final del mismo proveedor/solicitud de forma atómica; permite una versión anterior |
| `descartar_observacion` | `observacion_id`, `motivo` | Conserva la observación y registra quién la descartó |
| `solicitar_aclaracion` | `version_id`, `motivo`, `medio` | Registra una gestión; no envía correo |
| `reintentar` | `version_id`, por la URL de reintentos | Autoriza un nuevo ciclo para una lectura con error, conservando el historial |
| `ver_documento` | `documento_id` | Descarga el original después de comprobar sesión y acceso |

`accion_id` es opcional para compatibilidad con el documento, pero se recomienda
en cada decisión para reenviar exactamente la misma petición sin duplicar acciones.
No reutilizarlo para otra decisión. `solicitud_id` y `proveedor_id` son opcionales:
si se envían, deben coincidir con la versión; el servidor no confía en ellos.

Medios: `correo`, `llamada`, `whatsapp`, `reunion`, `otro`.
En una aclaración puede añadirse `observacion_ids: ["uuid", ...]` para indicar cuáles
se gestionaron. Pasan a `aclaracion_solicitada`, pero siguen bloqueando la aceptación
si requieren aclaración: registrar el pedido no equivale a resolverlo.

Descargar un documento devuelve `ok`, `nombre`, `mime_type` y `contenido_base64`.
El frontend puede convertir el contenido en un `Blob` para abrirlo o descargarlo.
Nunca recibe la cabecera administrativa utilizada por n8n para Storage.

Códigos de respuesta: 200 resultado registrado o repetido; 400 petición incompleta;
401 sesión inválida; 403 sin acceso; 404 entidad inexistente/no accesible; 409 una
regla impide la operación; 503 servicio temporalmente no disponible. Mostrar el
mensaje real, sin anunciar éxito solo porque n8n ejecutó un nodo.

## Cambios que debe integrar el encargado del frontend

1. Mostrar la bandeja y el detalle por versión, con identificación de la final vigente.
2. Conservar los estados del correo de E2 y el estado técnico de E3 como datos separados.
3. Retirar la asignación directa de «aceptada final» de Guardar corrección. Esa opción
   ahora utiliza E3.4; las otras correcciones de E2 y la coordinación se mantienen.
4. Antes de aceptar, mostrar esta confirmación:

   > Al aceptar esta versión como final, la versión final anterior volverá al estado
   > “Cotización o ficha técnica recibida”. Su información y su historial se conservarán.

5. Habilitar aceptación solo para `completado` o `completado_con_observaciones` y sin
   observaciones abiertas con `requiere_aclaracion=true`. Comprobar **todas**, incluso
   las bajas ocultas. El servidor vuelve a validar la misma condición.
6. Mostrar observaciones altas en rojo y medias en ámbar; ocultar bajas inicialmente
   y ofrecer «Ver advertencias menores». Mostrar motivo, evidencia y ubicación.
7. Incorporar descarte con motivo y registro de aclaración con motivo y medio.
8. Bloquear los botones mientras se procesa una petición y conservar `accion_id`
   si se necesita reintentar por una conexión interrumpida.
9. Recargar detalle, final vigente, correos y notificaciones al recibir éxito.
10. En `notificaciones`, utilizar `datos.color` y `datos.version_id`. Agregar «Ver versión»
    y «Ver archivo». La ruta lógica `/versiones/<uuid>` necesita resolución en el frontend;
    no debe abrirse como una página estática inexistente. Puede usarse `#version=<uuid>`.
11. Conservar Marcar como leída y Marcar como atendida. Atender un aviso no acepta
    una versión ni descarta una observación.
12. Para `error_procesamiento`, mostrar el reintento manual y un mensaje comprensible.
    Los diagnósticos internos quedan en la auditoría del servidor.

Los avisos E3 nuevos son `version_lista_revision` (azul), `version_con_observaciones`
(ámbar), `nueva_version_disponible` (azul/ámbar) y `error_procesamiento` (rojo).
Se conserva el historial de avisos de E2. El uso correcto de OCR no genera advertencia.

Actualmente las llamadas admiten los orígenes locales `http://127.0.0.1:8001` y
`http://localhost:8001`. Para un frontend publicado, el equipo debe configurar su
origen HTTPS en E3.4/E3.5 y una URL HTTPS accesible de n8n. `localhost` en la
computadora del compañero apunta a la computadora del compañero, no a la de Juan Daniel.

## Contrato con E4

```graphql
query FinalesParaHomologar($solicitud: uuid!) {
  e3_finales_e4(where: {solicitud_id: {_eq: $solicitud}}) {
    proveedor_id version_id correo_id numero_version resultado
  }
}
```

Esta vista solo entrega finales con lectura nueva terminada. Si un proveedor no
tiene final procesada, no aparece. E4 consume `resultado` y no vuelve a extraer PDF
ni Excel. Si existen finales históricas inconsistentes, la vista selecciona la del
correo final más reciente; un registro en `e3_inconsistencias` conserva la incidencia.
La base no exige que la final seleccionada por el usuario sea la versión más nueva.

**Pendiente de validación:** la consulta real por GraphQL y las pantallas integradas
necesitan la credencial administrativa correcta y el trabajo del encargado del frontend.
