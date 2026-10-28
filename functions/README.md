# Función interna de E3 en Nhost

`e3-operar.ts` permite que n8n invoque la función SQL `public.e3_operar` por
HTTPS. Los datos permanecen en el PostgreSQL de Nhost y n8n ya no necesita una
credencial de conexión directa a la base.

## Configuración en Nhost

1. Despliega `functions/e3-operar.ts` en el mismo proyecto Nhost de CostFlow.
2. Registra `E3_INTERNAL_KEY` con el mismo valor que ya utiliza el servicio E3
   (archivo local privado `.env.e3`). No generes otro valor si la instalación existe.
3. Usa exactamente el mismo valor en una credencial **Header Auth** de n8n:

   - cabecera: `X-Costflow-Internal-Key`;
   - valor: el secreto `E3_INTERNAL_KEY`.

Nhost proporciona a la función `NHOST_GRAPHQL_URL` y `NHOST_ADMIN_SECRET` (se
utiliza primero `NHOST_HASURA_URL` para llamar a la API administrativa). GraphQL
público termina en `/v1`; esa dirección no sirve directamente para `/v2/query`.
La función resuelve también el dominio público GraphQL de Nhost cuando solo está
disponible esa variable. No copies el secreto administrativo al frontend.

Esta Function forma parte del backend de Nhost. No crea una base externa y no
expone PostgreSQL: recibe una operación permitida, llama internamente a Hasura y
devuelve únicamente la respuesta de `public.e3_operar`.

La URL esperada es:

```text
https://SUBDOMINIO.functions.REGION.nhost.run/v1/e3-operar
```

## Contrato interno

Petición:

```json
{
  "operacion": "eventos",
  "datos": {}
}
```

Respuesta:

```json
{
  "respuesta": {
    "eventos": []
  }
}
```

La función acepta únicamente las operaciones declaradas por E3, comprueba el
secreto mediante comparación segura y utiliza el endpoint administrativo de
Hasura desde el backend. Nunca expone una consulta SQL arbitraria.

## Comprobación antes de cambiar los flujos

La consulta autorizada `configuracion` debe devolver `respuesta.modelo`, usando
la clave interna existente. Recibir `401` sin clave comprueba únicamente la
protección: no demuestra acceso a la base. El instalador local exige la consulta
autorizada correcta antes de reemplazar o publicar flujos; si falla, conserva la
instalación que ya funcionaba. No habilita recepción ni Gemini automáticamente.

Pruebas del handler (Node.js 24, sin paquetes adicionales ni claves reales):

```text
node --experimental-strip-types --test tests/etapa3/nhost_function.test.mjs
```
