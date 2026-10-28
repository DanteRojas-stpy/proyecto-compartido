# Importar los cinco flujos de E3

Los archivos `e3-1.json` a `e3-5.json` no contienen claves ni credenciales.
Antes de publicarlos, completa estos pasos en orden.

## 1. Preparar Nhost

1. Sigue [el orden único de migraciones](../../db/ORDEN_MIGRACIONES.md): base
   001–010, compatibilidad 011 y E3 012–015. No repitas las ya aplicadas; los
   antiguos nombres 001–004 de E3 corresponden a 012–015 con el mismo SQL.
2. Despliega `functions/e3-operar.ts` en el mismo proyecto Nhost.
3. Registra en **Settings → Secrets** el mismo `E3_INTERNAL_KEY` de la instalación
   existente. En **Environment Variables**, añade `E3_INTERNAL_KEY` con valor
   `{{ secrets.E3_INTERNAL_KEY }}`. Guarda y vuelve a desplegar la función.
4. Comprueba que la Function responda en:

   ```text
   https://SUBDOMINIO.functions.REGION.nhost.run/v1/e3-operar
   ```

Una petición sin la cabecera interna debe responder `401`. Esto confirma que la
Function está publicada y protegida.
Después comprueba `configuracion` con la clave interna: debe devolver
`respuesta.modelo`. Esta segunda comprobación es obligatoria antes de sustituir
los flujos locales; el instalador se detiene sin modificarlos si falla.

## 2. Preparar n8n

Crea una credencial **Header Auth**:

- nombre sugerido: `CostFlow E3 - Acceso interno`;
- cabecera: `X-Costflow-Internal-Key`;
- valor: exactamente el mismo `E3_INTERNAL_KEY` registrado en Nhost.

Importa los cinco JSON y, en todos los nodos con el aviso
`CREDENCIAL_E3:internal`, selecciona esa credencial. Reemplaza `SUBDOMINIO` y
`REGION` en los tres nodos que llaman a `e3-operar`.

Asigna además las credenciales existentes de Gmail, Gemini y Nhost Storage en
los nodos que muestran sus respectivos avisos.

Los cuerpos de las tres peticiones a Nhost separan las llaves de cierre del
objeto y de la expresión. No unas esos cierres: el evaluador de n8n puede leer
el primer `}}` como fin anticipado y devolver `invalid syntax`/HTTP 500.

## 2.1 Lector con Claude (opcional)

El nodo `¿Modelo de Claude?` de `e3-2.json` mira el modelo configurado en
`e3_configuracion.modelo`. Si empieza con `claude-`, la lectura va a la API de
mensajes de Claude; con cualquier otro valor (por ejemplo `gemini-3.5-flash-lite`)
sigue por Gemini. El servicio de `app/etapa3` no cambia: n8n traduce la
petición y la respuesta, y el validador de E3 revisa el resultado igual que antes.

Para usarlo:

1. Crea una credencial **Header Auth** en n8n con nombre `CostFlow E3 - Claude`,
   cabecera `x-api-key` y como valor la clave de la API de Anthropic
   (`sk-ant-...`). Nunca la pegues en un JSON, en el chat ni en Git.
2. En `e3-2.json`, en el nodo `Claude Messages` (aviso `CREDENCIAL_E3:claude`),
   selecciona esa credencial.
3. Cambia el modelo en la consola SQL de Nhost, con ese identificador exacto y
   sin sufijos de fecha:

   ```sql
   UPDATE public.e3_configuracion SET modelo = 'claude-opus-5-5' WHERE id;
   ```

   Alternativas: `claude-sonnet-5-5` (más barato) o `claude-haiku-5-5` (el más
   económico, con menos precisión al citar). Para volver a Gemini, usa
   `gemini-3.5-flash-lite` o el modelo de Gemini que prefieras.
4. Reintenta una versión desde la aplicación y comprueba el resultado.

El nodo no envía `temperature` ni `tool_choice`, que los modelos 5.x rechazan, y
pide la salida como JSON dentro del texto. Si la respuesta no cumple el esquema,
el validador de E3 la rechaza y la versión usa su reintento normal.

## 3. Procesamiento OCR/RAG

Los nodos que llaman a `http://costflow-etapa3:8093` necesitan el servicio de
`app/etapa3` en la misma red Docker. Si n8n está alojado fuera de esa red, publica
ese servicio en un backend HTTPS y cambia dichas URLs. No publiques el servicio
sin `E3_INTERNAL_KEY`.

## 4. Prueba mínima

1. Mantén `recepcion_habilitada=false` y `gemini_habilitado=false`.
2. Ejecuta `Tomar eventos pendientes`: debe responder
   `configuracion_pendiente` o una lista vacía, sin solicitar PostgreSQL.
3. Prueba Storage con un archivo temporal.
4. Prueba Gemini con un contenido pequeño.
5. Habilita las banderas únicamente después de superar estas comprobaciones.

PostgreSQL continúa dentro de Nhost. Las operaciones de base pasan por HTTPS y
no necesitan la contraseña de PostgreSQL en n8n. Los nodos Storage conservan su
credencial actual; el secreto administrativo nunca llega al frontend.
