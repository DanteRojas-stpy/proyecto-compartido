# Función interna de E3 en Nhost

`e3-operar.ts` permite que n8n invoque la función SQL `public.e3_operar` por
HTTPS. Los datos permanecen en el PostgreSQL de Nhost y n8n ya no necesita una
credencial de conexión directa a la base.

## Configuración en Nhost

1. Despliega `functions/e3-operar.ts` en el mismo proyecto Nhost de CostFlow.
2. En **Settings → Secrets**, registra `E3_INTERNAL_KEY` con el mismo valor que
   utiliza el servicio E3 (archivo local privado `.env.e3`). No generes otro valor
   si la instalación existe. Copia solo el valor, sin `E3_INTERNAL_KEY=`.
3. En **Settings → Environment Variables**, crea una variable con nombre
   `E3_INTERNAL_KEY` y valor `{{ secrets.E3_INTERNAL_KEY }}`. Crear únicamente el
   secret no lo hace accesible mediante `process.env.E3_INTERNAL_KEY`.
4. Guarda y vuelve a desplegar la función para aplicar la configuración.
5. Usa exactamente la misma clave real en una credencial **Header Auth** de n8n:

   - cabecera: `X-Costflow-Internal-Key`;
   - valor: el secreto `E3_INTERNAL_KEY`.

En la instalación del equipo se comprobó el despliegue desde la rama
`juan-daniel/e3-reglas-y-flujos`, con directorio base `./`. El despliegue de la
función conservó la configuración del proyecto aunque no hubiera `nhost/nhost.toml`.
No es necesario reemplazar la configuración compartida para publicar esta función.

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

## e4-operar: homologación (E4) y cuadro comparativo (E5)

Función hermana de `e3-operar`. Usa los mismos secretos (`E3_INTERNAL_KEY`, la credencial administrativa) y
la misma variable `CORS_ORIGINS`; no hay nada nuevo que configurar en Nhost salvo desplegarla.

- `solicitar_e4` y `solicitar_e5`: las llama el front con la sesión del especialista. La identidad sale de
  Nhost Auth y nunca del cuerpo de la petición.
- `tomar_*`, `entrada_*`, `guardar_*` y `fallo_*`: las usan n8n y los servicios con la cabecera
  `x-costflow-internal-key`. El especialista no puede ejecutarlas.

Antes de usarla, ejecuta la migración `db/etapa4/017_homologacion_cuadro.sql` y publica las tablas para el
front con `python scripts/configurar_etapa4_nhost.py --url <hasura> --respaldo respaldo.json`.
