# Migraciones de la base (Nhost)

Ejecutar cada archivo **una sola vez**, en orden, desde **Database > SQL
Console** de un proyecto Nhost nuevo.

1. `001_e1_registro_solicitud.sql`: crea las tablas, validaciones e índices de la
   etapa E1. No abre las tablas a usuarios finales. Después se configuran las
   relaciones, los permisos del rol `user` y las reglas de Storage. La tabla
   `proveedores` guarda una ficha reutilizable y `solicitud_proveedores` permite
   vincularla con muchas solicitudes sin duplicarla.

2. `002_documentos_por_proveedor.sql`: distingue los documentos generales de la
   solicitud de las cotizaciones y anexos de cada proveedor, con versión y estado.

3. `003_envios_solicitud.sql`: ejecutar con **Track this** activado. Registra a
   qué proveedor se envió cada solicitud, el identificador del mensaje de Gmail,
   los intentos y los errores.

4. `004_proyectos_y_correlativos.sql`: agrega el tipo `MA` (materiales) o `SC`
   (subcontrata) y asigna el número al insertar una solicitud. El correlativo es
   independiente por proyecto y tipo. El bloqueo del proyecto evita que dos
   registros simultáneos reciban el mismo número.

5. `005_fechas_y_partida_critica.sql`: la fecha de inicio se registra en
   `created_at`; la fecha fin `fecha_limite` es obligatoria para solicitudes
   nuevas. `partida_critica` define `frecuencia_aviso_dias`: 1 si es crítica y 2
   en otro caso. Los códigos nuevos usan tres dígitos como mínimo (`MA-001`,
   `SC-001`). Los documentos anteriores se conservan, pero el formulario ya no
   pide nuevos.

6. `006_estados_solicitudes.sql`: reemplaza los estados técnicos anteriores por
   `inicio`, `cerrado` y `cerrado_sin_proveedores`. Agrega la señal técnica
   `preparada_para_envio`, registra la fecha de cierre y exige un cuadro
   comparativo vigente para el cierre manual. También habilita el tipo de
   documento `cuadro_comparativo`.

7. `007_seguimiento_proveedores.sql`: agrega los estados de respuesta por
   proveedor, correos recibidos, aclaraciones, coordinaciones, historial de
   clasificaciones y notificaciones en la plataforma. Después de tres
   coordinaciones sin cotización excluye al proveedor y conserva la evidencia.

8. `008_revision_seguimiento_proveedores.sql`: conserva el vínculo entre cada
   clasificación automática y su correo, limpia la evidencia de IA cuando el
   usuario corrige el estado y valida el plazo usando la fecha real del correo.

9. `009_respuestas_con_ficha_tecnica.sql`: distingue al proveedor que respondió
   con documentación técnica pero todavía no envió una cotización económica.

10. `010_estados_por_correo.sql`: guarda un estado independiente para cada
    correo, conserva la propuesta preliminar de n8n y las decisiones del
    especialista, añade su historial y permite vincular los documentos que E3
    recuperará con el correo de origen. Por seguridad, cualquier clasificación
    antigua de “cotización definitiva” se migra como documentación recibida; el
    especialista debe aceptarla nuevamente después de que E3 registre el
    documento del correo.

Después de las migraciones, actualiza los permisos de GraphQL con
`scripts/configurar_nhost.py` y recarga la metadata. El seguimiento empieza con
el primer envío exitoso. n8n crea una notificación persistente a las 09:00,
hora de Lima: cada día para solicitudes críticas y cada dos días calendario
para las demás. Las respuestas recibidas generan notificaciones en tiempo real
en la plataforma.

## Permisos automatizados

Desde Windows se pueden aplicar las relaciones y permisos del rol `user` sin
configurar cada celda manualmente:

```powershell
python scripts/configurar_nhost.py
```

El programa solicita la Backend URL y `HASURA_GRAPHQL_ADMIN_SECRET`. El secreto
se escribe oculto, se usa solo en memoria y no se guarda en archivos. Puede
repetirse: reemplaza los permisos de CostFlow por la versión del repositorio.

Como alternativa, en **GraphQL > Metadata** se puede importar una metadata ya
preparada. La importación reemplaza la metadata actual, así que primero hay que
descargar una copia con **Export Metadata**. El estado final debe mostrar
**Consistent**.
