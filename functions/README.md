# Función interna de E3 en Nhost

`e3-operar.ts` permite que n8n invoque la función SQL `public.e3_operar` por
HTTPS. Los datos permanecen en el PostgreSQL de Nhost y n8n ya no necesita una
credencial de conexión directa a la base.

## Configuración en Nhost

1. Despliega `functions/e3-operar.ts` en el mismo proyecto Nhost de CostFlow.
2. Crea un secreto `E3_INTERNAL_KEY` con un valor aleatorio largo.
3. Usa exactamente el mismo valor en una credencial **Header Auth** de n8n:

   - cabecera: `X-Costflow-Internal-Key`;
   - valor: el secreto `E3_INTERNAL_KEY`.

Nhost proporciona a la función `NHOST_GRAPHQL_URL` y `NHOST_ADMIN_SECRET` (se
mantiene compatibilidad con `NHOST_HASURA_URL`). No copies el secreto
administrativo a n8n ni al frontend.

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
