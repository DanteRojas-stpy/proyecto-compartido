# Orden único de instalación de la base de CostFlow

Nhost debe haber creado sus servicios y `auth.users` antes de empezar. Ejecutar
los archivos completos, uno por uno, desde **Database → SQL Console**, deteniéndose
si alguno falla. No ejecutar todos los archivos mediante un orden alfabético de
carpetas. La numeración de esta lista es global y no se repite entre carpetas.

## Proyecto nuevo

| Orden | Archivo | Qué prepara | Depende de |
|---|---|---|---|
| 001 | [001_e1_registro_solicitud.sql](migraciones/001_e1_registro_solicitud.sql) | Proyectos, solicitudes, proveedores, participación, documentos, partidas y actualización de fechas | `auth.users` de Nhost |
| 002 | [002_documentos_por_proveedor.sql](migraciones/002_documentos_por_proveedor.sql) | Documentos de proveedor, número de versión y estados | 001 |
| 003 | [003_envios_solicitud.sql](migraciones/003_envios_solicitud.sql) | Registro de envíos Gmail e intentos | 001–002 |
| 004 | [004_proyectos_y_correlativos.sql](migraciones/004_proyectos_y_correlativos.sql) | Correlativos MA/SC por proyecto | 001–003 |
| 005 | [005_fechas_y_partida_critica.sql](migraciones/005_fechas_y_partida_critica.sql) | Fechas y frecuencia de seguimiento | 001–004 |
| 006 | [006_estados_solicitudes.sql](migraciones/006_estados_solicitudes.sql) | Estados de negocio y cierre de solicitudes | 001–005 |
| 007 | [007_seguimiento_proveedores.sql](migraciones/007_seguimiento_proveedores.sql) | Correos, coordinaciones, aclaraciones, historial y notificaciones | 001–006 |
| 008 | [008_revision_seguimiento_proveedores.sql](migraciones/008_revision_seguimiento_proveedores.sql) | Evidencia por correo y validación de fechas | 007 |
| 009 | [009_respuestas_con_ficha_tecnica.sql](migraciones/009_respuestas_con_ficha_tecnica.sql) | Distinción de ficha técnica y oferta económica | 007–008 |
| 010 | [010_estados_por_correo.sql](migraciones/010_estados_por_correo.sql) | Estado y actor por correo; `documentos.correo_id` e historial | 001–009 |
| 011 | [011_base_versiones_cotizacion.sql](migraciones/011_base_versiones_cotizacion.sql) | Tabla base `versiones_cotizacion`, sus restricciones e índices; origen, Gmail y vínculo de versión de documentos | 001–010 |
| 012 | [012_entidades.sql](etapa3/012_entidades.sql) | Configuración, eventos, reservas, resultados, fragmentos, evidencias, observaciones y decisiones de E3 | 011 |
| 013 | [013_procesamiento.sql](etapa3/013_procesamiento.sql) | Operaciones transaccionales `e3_operar` y recuperación | 012 |
| 014 | [014_decisiones_y_salida.sql](etapa3/014_decisiones_y_salida.sql) | Decisiones autenticadas, protección de versión final y vistas E3/E4 | 013 |
| 015 | [015_modelo_gemini_disponible.sql](etapa3/015_modelo_gemini_disponible.sql) | Histórica: dejó un modelo de Gemini como predeterminado. La 021 lo reemplaza por Claude | 012–014 |
| 016 | [016_aceptar_con_observaciones.sql](etapa3/016_aceptar_con_observaciones.sql) | Las observaciones pendientes ya no bloquean la aceptación final: E3 pide confirmación al especialista y registra cuántas quedaban | 012–015 |
| 017 | [017_homologacion_cuadro.sql](etapa4/017_homologacion_cuadro.sql) | E4 (homologación) y E5 (cuadro): cola con botón del especialista, resultados, avisos y vista de estado | 012–016 |
| 018 | [018_tipo_cambio_cuadro.sql](etapa4/018_tipo_cambio_cuadro.sql) | E5: tipo de cambio autorizado por el especialista al pedir el cuadro (columna y e4_operar ampliada) | 017 |
| 019 | [019_motivo_error_cuadro.sql](etapa4/019_motivo_error_cuadro.sql) | E5: la vista de estado muestra el motivo real del error del cuadro | 017 |
| 020 | [020_descarga_cuadro.sql](etapa4/020_descarga_cuadro.sql) | E5: comprobación de acceso para descargar el Excel del cuadro con la sesión del especialista | 017 |
| 021 | [021_lector_claude.sql](etapa3/021_lector_claude.sql) | El lector de E3 es Claude: la bandera pasa a `lector_habilitado` y el modelo predeterminado a `claude-opus-5-5` | 012–015 |

La 011 reproduce la estructura base comprobada en `costflow-dev` el 28/10/2026.
La 012 añade las columnas y reglas propias de E3: entre ambas completan la tabla
actual, sin crear por adelantado funciones ni disparadores de etapas posteriores.
La 011 también elimina el índice antiguo que limitaba a un solo adjunto de cada
tipo por proveedor/versión. No borra registros ni archivos.

`lecturas_documento` y las observaciones del flujo antiguo no son dependencias
de esta implementación: E3 crea y utiliza `e3_resultados`, `e3_observaciones`
y sus demás tablas nuevas. No se recrean módulos antiguos que ya no se utilizan.

## Proyecto existente del equipo

- No volver a ejecutar las migraciones 001–010: fueron diseñadas para aplicarse
  una vez y pueden modificar estados históricos.
- La 011 usa `CREATE TABLE IF NOT EXISTS` y comprueba los objetos adicionales.
  En `costflow-dev` esos objetos ya existen: no sustituye la tabla ni sus datos.
- Las cuatro migraciones de E3 antes llamadas `001_entidades.sql`,
  `002_procesamiento.sql`, `003_decisiones_y_salida.sql` y
  `004_modelo_gemini_disponible.sql` corresponden, respectivamente, a 012–015.
  **Solo cambiaron de nombre; su SQL se conserva. Si ya se aplicaron, no se
  deben repetir por haber cambiado la numeración.**
- Antes de aplicar una migración pendiente, respaldar la base y comprobar qué
  pasos tiene instalados el proyecto. Esta lista no es un registro automático
  de migraciones aplicadas ni ejecuta cambios al fusionar un PR.

## Después del SQL

1. Configurar los permisos base con `scripts/configurar_nhost.py` y después los
   de E3/E4 con `scripts/configurar_etapa3_nhost.py`. Exportar antes la metadata;
   el segundo programa conserva los objetos ajenos y controla su revisión.
2. Desplegar la Function y configurar las conexiones siguiendo
   [functions/README.md](../functions/README.md).
3. Importar/publicar los cinco flujos según
   [n8n/etapa3/README.md](../n8n/etapa3/README.md).
4. Mantener `recepcion_habilitada=false` y `lector_habilitado=false` hasta completar
   las comprobaciones y la prueba integrada autorizada.

El enlace de GitHub del equipo publica la carpeta `functions/`. Los SQL de estas
carpetas no se convierten por eso en migraciones automáticas de Nhost.

## Verificación de este orden

Se comprobó una instalación vacía en PostgreSQL 18, sin conexión al proyecto del
equipo: 001–015, dos documentos del mismo tipo en una versión, dos repeticiones
de la base 011 sin cambiar datos ni reglas, y los trece grupos SQL de E3.
También se comprobó la 011 en `costflow-dev`, dentro de una transacción revertida:
no cambió columnas, restricciones, índices, disparadores ni datos de documentos
y versiones. Esto no sustituye una prueba completa Gmail → lectura → frontend.

Para repetir la prueba aislada desde PowerShell, con Docker Desktop abierto:

```powershell
$env:COSTFLOW_TEST_POSTGRES_IMAGE = 'postgres:18'
.venv\Scripts\python.exe -m pytest tests/etapa3/test_migraciones_desde_cero.py -q
```

La prueba crea y retira su propio contenedor, sin publicar puertos ni utilizar
claves o datos del equipo. Sin esa variable, pytest comprueba el orden y omite
explícitamente la parte que necesita PostgreSQL.
