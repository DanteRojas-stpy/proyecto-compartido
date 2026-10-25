# Base de datos para Nhost

Ejecutar `001_e1_registro_solicitud.sql` una sola vez desde **Database > SQL
Console** en un proyecto Nhost nuevo.

Esta migracion crea las tablas, validaciones e indices de la etapa E1. No abre
las tablas a usuarios finales. Despues de ejecutarla se deben configurar las
relaciones, los permisos del rol `user` y las reglas de Storage.

Ejecutar despues `002_documentos_por_proveedor.sql`. Esta segunda migracion
distingue los documentos generales de la solicitud de las cotizaciones y
anexos pertenecientes a cada proveedor, incluyendo version y estado.

Ejecutar despues `003_envios_solicitud.sql` con **Track this** activado. Esta
tabla registra a qué proveedor se envió cada solicitud, el identificador del
mensaje de Gmail, los intentos y los errores.

Ejecutar finalmente `004_proyectos_y_correlativos.sql` una sola vez. Agrega el
tipo `MA` (materiales) o `SC` (subcontrata) y asigna el número al insertar una
solicitud. El correlativo es independiente por proyecto y tipo: `MA-001`,
`MA-002`, o `SC-01`, `SC-02`. Los códigos existentes se conservan. El bloqueo
del proyecto evita que dos registros simultáneos reciban el mismo número.
Después, actualiza los permisos de GraphQL con `scripts/configurar_nhost.py`
y recarga la metadata para que aparezca la columna `tipo`.

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

Como alternativa, en **GraphQL > Metadata** se puede importar una metadata ya
preparada. La importacion reemplaza la metadata actual, por lo que primero se
debe descargar una copia con **Export Metadata**. El estado final debe mostrar
**Consistent**.
