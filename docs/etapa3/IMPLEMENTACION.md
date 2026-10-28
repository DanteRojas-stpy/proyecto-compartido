# Etapa 3 según las reglas del 27/10/2026

Implementación realizada por **Codex**, en `juan-daniel/e3-reglas-y-flujos`.
La especificación recibida se conserva en [REGLAS.md](REGLAS.md).

## Estado real de la instalación

Se aplicaron las cuatro migraciones en la base Nhost del equipo y se importaron/publicaron
los cinco flujos en el n8n local de Juan Daniel. Los flujos anteriores de E3 están
desactivados y archivados, con respaldo privado previo. Las cotizaciones, lecturas,
PDF, Excel históricos y decisiones anteriores se conservan; no se eliminaron datos
para forzar relecturas. La función anterior de aceptación devuelve que fue reemplazada.

**La instalación todavía no está lista para una corrida completa de producción.**

- El código del PR #41 de Rodrigo se integró con la corrección de Gemini del #39.
  La Function está desplegada en Nhost desde `juan-daniel/e3-reglas-y-flujos`.
  Se sincronizó la clave interna y se comprobó `configuracion` con HTTP 200 tanto
  directamente como por la cadena servicio E3 → n8n → Function → Nhost.
  Los tres accesos de base de E3.1/E3.5 ya utilizan HTTPS; se conservaron las demás
  credenciales y los cinco flujos publicados. El instalador verifica la Function
  antes de sustituir los flujos y se detiene si falla.
- Las credenciales de Gemini, Gmail y Nhost ya están configuradas en la instalación
  original. La variante portable elimina la credencial PostgreSQL de n8n y usa la
  Function protegida `functions/e3-operar.ts` por HTTPS.
- Storage permite descargar originales y cargar un archivo temporal. Se corrigió
  una respuesta 404 guardada en caché que impedía descargar inmediatamente archivos nuevos.
- Hasura ya permite administrar la configuración. Las consultas y permisos de E3/E4
  se publicaron y sus consultas GraphQL respondieron sin errores.
- Gemini ya respondió con `gemini-3.5-flash-lite` usando la misma credencial de n8n.
  Se validó el contrato completo de E3 con una cotización ficticia: un ítem,
  evidencias literales, cantidades y precios correctos. El modelo anterior devolvía 503.
  No se enviaron cotizaciones reales a Google durante estas pruebas.
- Se conservan `recepcion_habilitada=false` y `gemini_habilitado=false`. Los eventos se
  conservan pendientes hasta superar las pruebas restantes.
- Falta una dirección pública HTTPS de n8n para el frontend del equipo; el servicio
  de procesamiento sigue privado. También falta probar una decisión con JWT real del especialista.
- El frontend del compañero requiere integrar las vistas y acciones descritas en
  [CONTRATO_FRONTEND.md](CONTRATO_FRONTEND.md). No se sustituyó su interfaz existente.

Falta validar la corrida integrada de una cotización autorizada y las decisiones
desde la interfaz real antes de habilitar producción. El detalle de conexiones está en
[AUDITORIA_CONEXIONES.md](AUDITORIA_CONEXIONES.md).

## Los cinco flujos

| Flujo | Entrada | Trabajo | Salida |
|---|---|---|---|
| E3.1 | Evento persistido al confirmar un correo en E2 | Una versión por correo, descarga exacta de adjuntos, huella SHA-256, deduplicación y originales en `cotizaciones` | Versión pendiente de lectura |
| E3.2 | Versión registrada o recuperación autorizada | Extracción completa, OCR, búsqueda por criterios, Gemini, comprobaciones y guardado transaccional | JSON, evidencia y observaciones en Nhost |
| E3.3 | Lectura terminada o error definitivo | Aviso único con versión, color y acceso al documento | Notificación del frontend; nunca Gmail |
| E3.4 | Petición del frontend con sesión Nhost | Aceptar cualquier versión procesada elegida, descartar con motivo o registrar aclaración | Decisión auditada; ningún envío de correo |
| E3.5 | Revisión cada minuto o reintento autorizado | Recuperar ejecuciones vencidas y pasos pendientes, volver al punto seguro | Lectura o error definitivo visible |

La activación de E3.1 utiliza una **cola de eventos en PostgreSQL de Nhost**. El evento se
crea en la misma transacción en la que E2 confirma el correo; n8n la consume cada
minuto mediante la Function HTTPS `e3-operar`; n8n no abre una conexión directa a
PostgreSQL ni necesita su contraseña. No necesita buscar todos los Gmail.
La búsqueda general y la detección preliminar siguen perteneciendo a E2.

El usuario confirma expresamente cada correo documental. Correos sin documentos o
clasificados solo por el agente no generan versiones. La llegada de otra versión
no sustituye una final. Desactivar la final anterior no crea un nuevo evento de lectura.

## Decisiones técnicas

| Tema | Configuración implementada |
|---|---|
| Gemini | `gemini-3.5-flash-lite`, configurable en `e3_configuracion`; temperatura 0 y esquema JSON fijo |
| OCR | Tesseract local, español e inglés; conserva página, bloque, caja y confianza |
| Búsqueda documental | FastEmbed/ONNX, `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensiones, dos hilos de CPU |
| Índice | Fragmentos y vectores guardados por documento/versión en PostgreSQL; extracción local reutilizable |
| Fragmentos | 400 caracteres, solapamiento de 60; tablas conservadas por fila y posición de celda |
| Contexto | 24 000 caracteres de texto por lote; se reduce a la mitad en cada reintento. Todos los fragmentos se recorren; no se descarta el resto de la propuesta |
| Límites | Archivo de 50 MB, 300 páginas PDF/imagen, un millón de celdas, XLSX expandido de 200 MB; superar un límite es error visible |
| Reintentos | Hasta tres intentos automáticos por ciclo autorizado, pausas de 30 y 120 segundos, revisión cada minuto |
| Nueva autorización manual | Abre un ciclo explícito después del error y conserva los intentos anteriores. Repetir la misma petición no abre otro ciclo |
| Ejecución vencida | Reserva de 15 minutos, renovada entre documentos y lotes; evita guardados de intentos vencidos |
| Retención | Originales, JSON, evidencias y decisiones sin borrado automático; caché de extracción local: 30 días; n8n no conserva cuerpos de ejecución |
| Salida | JSON independiente de una plantilla; conserva campos originales y normalizados, ítems comerciales y especificaciones extensibles para E4 |

El modelo de búsqueda no es Ollama y no utiliza la tarjeta gráfica. Se descargó y
probó localmente. Solo Gemini interpreta el contenido; su llamada real y el contrato
de salida se comprobaron con datos ficticios.
No se realizan conversiones monetarias, equivalencias técnicas ni homologación.
Las unidades se normalizan por una lista de alias conservadora, sin alterar cantidades.

Las fórmulas de Excel se leen junto con su último resultado guardado. Si el archivo
no tiene ese resultado, se conserva la fórmula y se genera una observación; no se
simula un cálculo ni se inventa el valor. Se incluyen hojas ocultas.

Referencias de configuración: [modelos de Gemini](https://ai.google.dev/gemini-api/docs/models),
[salida estructurada](https://ai.google.dev/gemini-api/docs/generate-content/structured-output),
[modelos de FastEmbed](https://qdrant.github.io/fastembed/examples/Supported_Models/).

## Instalación reproducible

1. Seguir [el orden único de migraciones](../../db/ORDEN_MIGRACIONES.md): primero
   `db/migraciones/001` a `010_estados_por_correo.sql`, después
   `011_base_versiones_cotizacion.sql`. La base 011 crea las dependencias que
   existían fuera del repositorio; no sustituye las tablas ya presentes.
2. En un proyecto nuevo, continuar en orden con `db/etapa3/012_entidades.sql`,
   `013_procesamiento.sql`, `014_decisiones_y_salida.sql` y
   `015_modelo_gemini_disponible.sql`. Esta última cambia el modelo anterior por el
   probado; conserva una elección distinta del equipo y no activa las banderas.
   Estos archivos antes se llamaban 001–004 dentro de `db/etapa3/`: el SQL se
   conserva. Si ya se aplicaron en el proyecto del equipo, no repetirlos.
3. Desplegar `functions/e3-operar.ts` en el mismo proyecto Nhost y registrar el
   secreto `E3_INTERNAL_KEY`. Añadir también la variable de entorno del mismo
   nombre, con valor `{{ secrets.E3_INTERNAL_KEY }}`, y volver a desplegar.
   La guía está en `functions/README.md`.
4. Con Docker Desktop y un contenedor llamado `n8n`, ejecutar con Python 3.12:

   ```powershell
   .venv\Scripts\python.exe scripts/configurar_etapa3_local.py --publicar --retirar-anteriores
   ```

   El instalador reutiliza referencias de las credenciales Gmail y Storage.
   Reutiliza la clave interna de `.env.e3`, excluido de Git; solo crea una si falta.
   No descifra las otras credenciales. Esa misma clave se registra como
   `E3_INTERNAL_KEY` en Nhost. Si el equipo ya dispone de una, guardarla primero
   en ese archivo local y en el secret del proyecto.
   Construye el apoyo local en `127.0.0.1:8093` y lo conecta a n8n por Docker.
   Si n8n ya estaba ejecutando trabajos, esperar a que terminen antes de reiniciarlo.
5. Revisar las credenciales como se indica abajo. No activar las dos banderas hasta
   que las comprobaciones hayan funcionado.
6. Importar los JSON de `n8n/etapa3/` en otra computadora requiere instalar también
   este servicio y las migraciones. Un JSON solo no contiene todo el sistema.

Los cinco JSON compartibles no llevan claves ni referencias personales de credenciales.
El instalador hace una copia local con las referencias existentes. El paso de retiro
solo afecta los identificadores anteriores de E3 de esta instalación; no toca E1/E2/E4/E5.

## Configuración de credenciales para otra instalación

**Operaciones Nhost.** En n8n crear una credencial Header Auth con cabecera
`X-Costflow-Internal-Key` y el mismo `E3_INTERNAL_KEY` guardado en Nhost. Asignarla
a los nodos marcados como `CREDENCIAL_E3:internal`. El secreto administrativo de
Hasura permanece en Nhost y nunca se copia a n8n ni al navegador.

**Storage.** Los nodos de archivos conservan su credencial Nhost/Storage. Comprobar
lectura y carga con un archivo de prueba antes de activar E3. No reemplazar un secreto
compartido por uno nuevo improvisado: eso afectaría otras integraciones del equipo.

Para publicar GraphQL, ejecutar el script que pide la clave sin mostrarla ni guardarla:

```powershell
.venv\Scripts\python.exe scripts/configurar_etapa3_nhost.py --url https://SUBDOMINIO.hasura.REGION.nhost.run --respaldo C:\ruta-privada\metadata-anterior.json
```

Revisar los permisos antes y después. El script conserva las demás etapas y agrega
lectura restringida a las solicitudes del usuario; no habilita escrituras directas
de las tablas E3 desde el frontend. Aplica el cambio de forma atómica con control
de revisión para evitar sobrescribir una modificación concurrente del equipo.

**Gemini.** Crear una clave del proyecto de Google AI Studio. Guardarla directamente
en una nueva credencial Header Auth de n8n: cabecera `x-goog-api-key`, valor la clave.
Asignarla al nodo «Gemini JSON fijo» de E3.2, guardar y publicar. El instalador puede
encontrarla por su nombre si contiene «Gemini». No pegar claves en el JSON del flujo.
Comprobar disponibilidad y cuota del modelo elegido en la cuenta del equipo.
La configuración vigente usa `gemini-3.5-flash-lite`; E3.2 recibe el nombre desde
Nhost, por lo que este cambio no requiere otra clave ni modificar la URL del nodo.

Después de verificar Storage y una lectura de prueba con Gemini:

```sql
UPDATE public.e3_configuracion
SET recepcion_habilitada=true, gemini_habilitado=true
WHERE id;
```

## Pruebas y límites de lo verificado

- La suite Python completa pasó: 56 pruebas y una omitida en Windows por no tener
  Tesseract en el sistema anfitrión. Tesseract se instala dentro del contenedor.
- Dentro de Docker pasaron las 29 pruebas de E3, incluida OCR, sin omisiones.
- La integración de la Function añade tres comprobaciones Python y nueve pruebas
  ejecutables con Node.js para autenticación, contrato, acceso Hasura y errores.
  Pytest también ejecuta estas últimas si encuentra Node.js 22.6 o posterior;
  en equipos sin esa versión indica la omisión. Se recomienda Node.js 24.
- La búsqueda vectorial real respondió a los siete criterios con vectores de 384 dimensiones.
- `tests/etapa3/integracion.sql` se ejecutó en la base real dentro de una transacción
  revertida: trece grupos de pruebas de negocio pasaron, sin conservar registros ficticios.
- Las entradas de n8n respondieron: petición de decisión sin sesión → 401; servicio
  interno sin su credencial → 403; consulta interna autorizada → 200; prevalidación
  del navegador para `http://127.0.0.1:8001` → 204.
- Storage permitió descargar un original y cargar/descargar un CSV ficticio; los
  archivos temporales se retiraron después, sin borrar cotizaciones reales.
- Las consultas GraphQL de E3/E4 ya respondieron. Con el rol de usuario, el propietario
  pudo consultar sus versiones y una cuenta ajena no obtuvo ninguna. Esta prueba de
  permisos no sustituye la prueba pendiente con JWT real desde el frontend.
- Gemini devolvió 503 con el modelo anterior. Se sustituyó por
  `gemini-3.5-flash-lite`, que respondió por la entrada publicada de E3.2 y superó
  `parse_response` y `combine` con el esquema completo, datos originales y evidencias
  de una cotización ficticia (2 unidades × USD 100, parcial 200, total 236).
  También se reforzaron las instrucciones: las citas deben contener todos los
  originales del registro, incluida la moneda y las condiciones. Se comprobó que
  una cita incompleta sigue siendo rechazada por las validaciones independientes.
  No se enviaron correos ni se ejecutó el procesamiento completo de cotizaciones.

Los grupos SQL comprueban: correo sin documentos, una versión por correo,
repetición sin duplicados, dos archivos en la misma versión, falta de Gemini sin
consumir intentos, bloqueo por aclaración incluso de severidad baja, descarte con
motivo, selección de una versión anterior, cambio de final sin relectura, notificación
única y tres fallos con reintento manual conservando historial. También verifican
rechazo de otra cuenta, la protección del cambio final fuera de E3.4 y la restricción
existente de una sola final activa. La defensa por fecha de correo de E4 permanece
en su vista, sin retirar esa restricción para simular inconsistencias en la base compartida.

Repetir las pruebas Python tras cambios:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

La prueba SQL requiere ejecutarse completa, incluido su `ROLLBACK`. No copiar partes
sueltas para generar datos de demostración en la base compartida.
