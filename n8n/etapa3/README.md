# Importar los cinco flujos de E3

Los archivos `e3-1.json` a `e3-5.json` no contienen claves ni credenciales.
Antes de publicarlos, completa estos pasos en orden.

## 1. Preparar Nhost

1. Aplica las tres migraciones de `db/etapa3/`.
2. Despliega `functions/e3-operar.ts` en el mismo proyecto Nhost.
3. Crea el secreto `E3_INTERNAL_KEY` en Nhost.
4. Comprueba que la Function responda en:

   ```text
   https://SUBDOMINIO.functions.REGION.nhost.run/v1/e3-operar
   ```

Una petición sin la cabecera interna debe responder `401`. Esto confirma que la
Function está publicada y protegida.

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

PostgreSQL continúa dentro de Nhost. n8n solo usa HTTPS y nunca recibe la
contraseña de la base ni el secreto administrativo de Hasura.
