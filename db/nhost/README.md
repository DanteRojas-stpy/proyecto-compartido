# Base de datos para Nhost

Ejecutar `001_e1_registro_solicitud.sql` una sola vez desde **Database > SQL
Console** en un proyecto Nhost nuevo.

Esta migracion crea las tablas, relaciones, validaciones e indices de la etapa
E1. No abre las tablas a usuarios finales. Despues de ejecutarla se deben
configurar los permisos del rol `user` en GraphQL y las reglas de Storage desde
el panel de Nhost.

El archivo de Supabase ubicado en `db/migraciones/` se conserva como referencia
y no debe ejecutarse en Nhost.

## Permisos automatizados

Desde Windows se pueden aplicar las relaciones y permisos del rol `user` sin
configurar cada celda manualmente:

```powershell
python scripts/configurar_nhost.py
```

El programa solicita la Backend URL y `HASURA_GRAPHQL_ADMIN_SECRET`. El secreto
se escribe oculto, se usa solo en memoria y no se guarda en archivos. La
ejecucion puede repetirse: reemplaza los permisos de CostFlow por la version
definida en el repositorio.
