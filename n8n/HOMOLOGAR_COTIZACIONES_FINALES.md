# E4: homologar cotizaciones finales con la plantilla compartida

Flujo: **CostFlow - E4 Homologar cotizaciones finales** (`costflowE4Homol01`).
Exportación: `flujos/e4-homologar-cotizaciones-finales.json`.

Este es el proceso de homologación. No genera el Excel, elige proveedor, cambia
estados de Nhost ni envía mensajes. Utiliza la skill `homologar-cotizaciones`
y los campos de negocio de la plantilla compartida de ascensores.

## Entrada que está en desarrollo

La solicitud debe tener participaciones con:

- `solicitud_proveedores.estado_respuesta = envio_cotizacion`.
- `detalle_respuesta = cotizacion_definitiva` y `considerado = true`.
- Una versión en `versiones_cotizacion` con `es_final = true`, `estado = vigente`
  y `origen = correo`, perteneciente a esa solicitud y proveedor.
- Ninguna versión posterior no anulada que deje en duda cuál es la final y
  ninguna aclaración abierta.
- Documentos asociados a esa versión mediante `version_id`, con su
  `storage_file_id`; itemizado en `partidas` y plantilla en `documentos`.

Recibir un correo, subir una ficha técnica, cambiar a `respondio` o tener un PDF
reciente no satisface esas condiciones. Este flujo no asigna el estado final.

Si la etapa anterior aún no entrega esa entrada, el resultado es
`estado: esperando_insumos`, con el motivo y `habilitado_para_cuadro: false`.
Un error de permisos, red o GraphQL se muestra como error; no se oculta como
ausencia de cotizaciones.

## Qué hace

1. Busca participaciones finales; se puede filtrar por solicitud.
2. Comprueba versión, aclaraciones, itemizado y plantilla de la solicitud.
3. Descarga solo los documentos de la versión final desde Nhost Storage.
   Un lector incluido en el JSON ejecuta una instancia independiente por archivo.
4. Extrae texto de PDF, XLSX, XLS y CSV. Reúne todos los archivos de cada versión;
   incorpora el cuerpo del correo final si fue registrado en Nhost.
5. El nodo **Proponer homologación con la skill** recibe las instrucciones de
   homologación y sus referencias, el itemizado, los campos que se comparan y
   el texto de la propuesta. Ollama local propone datos y correspondencias.
6. Un paso de código verifica las citas literales y que el valor figure en ellas.
   Un dato sin respaldo queda `null`; no se completa con otro proveedor.
7. Consulta Nhost otra vez para comprobar que la propuesta siga siendo final.
   Si cambió durante la lectura, no entrega un resultado definitivo antiguo.

La comparación técnica sigue siendo una propuesta: el estado de salida es
`homologacion_propuesta` y `estado_revision = requiere_revision`. Las páginas
indicadas por IA se conservan como propuestas, no como páginas verificadas.
La cita se verifica contra el texto, no garantiza por sí sola la interpretación
técnica. Los valores comparables quedan pendientes hasta resolver la relación
técnica y los criterios aplicables; este flujo no aprueba equivalencias.

## Qué toma de la plantilla

Referencia inspeccionada, sin modificar: la copia denominada
`HISTORICO_COMPARATIVO_ASCENSOR_5.2-aecode - plantilla.xlsx`, que también figura
como plantilla en Nhost. El contrato está en
`plantillas/homologacion/contratos/ascensores-plantilla-5.2.json`.

Se comparan descripción, unidad, cantidad y precios originales; moneda,
parcial/subtotal, gastos generales, utilidad, IGV y total; adelanto y garantías,
fondo de garantía, contacto, viga divisoria, plazo de envío, garantía técnica,
mantenimiento gratuito, pago por hitos, características de cabina, capacidad,
velocidad, recorrido/paradas, cuarto de máquinas, comando, consideraciones y
obras en ejecución.

No se utilizan como cotización el presupuesto meta, los ceros, los textos entre
corchetes ni el TC vacío/de relleno del Excel. Se conserva un hash de la copia
local inspeccionada, pero el flujo comprueba el nombre de la plantilla registrada,
no descarga ni verifica ese hash remoto. Si se reemplaza la plantilla conservando
el nombre, hay que revisar y regenerar el contrato antes de usar el nuevo formato.
El flujo no escribe celdas ni combina las dos skills.

## Ejecución y conexiones

En n8n local abre `http://localhost:5678/workflow/costflowE4Homol01` y ejecuta
**Revisar cotizaciones finales**. La importación local ya usa las referencias a
las conexiones de Nhost y Ollama existentes; el JSON del repositorio no contiene
credenciales. Para otra instalación:

- Seleccionar Header Auth de Nhost en los tres nodos GraphQL y también en el
  nodo HTTP del lector incluido en **Leer cada archivo final / Workflow JSON**.
- Seleccionar Ollama en **Ollama local - homologación**. Con Docker en Windows,
  la URL comprobada es `http://host.docker.internal:11434`.
- El modelo es `qwen3:8b`, sin razonamiento adicional y con `numGpu: 0`, para
  evitar el fallo CUDA ya observado en este equipo.

El segundo inicio, **Desde otro flujo**, admite:

```json
{
  "solicitud_id": "00000001-1111-4111-8111-111111111111",
  "tipo_cambio": null
}
```

El UUID es ficticio. Sin `solicitud_id`, se consultan las participaciones finales
disponibles. Si se necesita un cambio autorizado, se entrega como objeto con
`valor` positivo, `sentido: USD_PEN`, `fecha` en formato AAAA-MM-DD, `fuente` y
`aprobado_por`. No se obtiene automáticamente de Internet ni de un ejemplo.
Se conserva para la normalización posterior a la revisión técnica; el nodo IA
extrae importes originales, no realiza conversiones de moneda.

El flujo queda sin publicación automática. Se puede llamar como subflujo cuando
la etapa de identificación final esté lista; no se activó una programación.

## Salida y límites

**Entregar homologación para revisión** devuelve una estructura por proveedor
con solicitud/versión, base, importes y textos originales, campos encontrados,
documentos de respaldo, citas, correspondencias propuestas y pendientes.
Los datos se ven en la ejecución de n8n; esta entrega no añade tablas ni escribe
el resultado en PostgreSQL/Storage. Su registro y aprobación pueden conectarse
después a la etapa de revisión de la plataforma.

Los PDF escaneados sin texto e imágenes requieren OCR/revisión y quedan
pendientes. Si falta un archivo, ninguno se homologa como propuesta completa.
El límite de entrada del modelo es 24 000 caracteres de datos; si se supera,
se solicita lectura por secciones, sin recortar silenciosamente la propuesta.
Se procesan como máximo 200 participaciones por ejecución, 100 versiones,
200 documentos y 1 000 partidas por consulta; se detiene si se supera el lote.
La lectura de Excel depende de la extracción de celdas del nodo de n8n: no es
una revisión visual de imágenes, objetos ni todas las hojas del libro. Hay que
comprobar la cobertura antes de dar por completa una propuesta de varias hojas.

## Fuentes y regeneración

- Reglas verificables: `app/homologacion/finales.js`.
- Generador: `scripts/generar_flujo_homologacion.py`.
- Skill utilizada: `plantillas/homologacion/homologar-cotizaciones/SKILL.md`.
- Contrato de campos: `plantillas/homologacion/contratos/ascensores-plantilla-5.2.json`.

Ejecuta `scripts/generar_flujo_homologacion.py` con el Python del entorno del
proyecto después de cambiar la skill, reglas o contrato. La exportación incluye
esas instrucciones para que el agente las reciba sin acceso al disco de Windows.
No reimportes ciegamente sobre ediciones de otra persona: exporta primero el
flujo local y conserva sus conexiones.

## Comprobaciones de esta entrega (27/10/2026)

La ejecución local contra Nhost terminó en `esperando_insumos`: en esa consulta
todavía no había versiones finales. También se verificó la consulta detallada
contra el esquema real sin modificar registros.

El recorrido positivo se ejecutó con una fuente aislada y dos PDF ficticios,
utilizando extracción real de texto y Ollama local. Reunió ambos archivos y
entregó una propuesta con 25 campos previstos, 9 encontrados, 12 citas y un
ítem. Los demás datos y la correspondencia técnica quedaron pendientes para
revisión. No se subieron documentos de prueba a Nhost ni se enviaron mensajes.
La llamada de IA de esta prueba tardó aproximadamente 11 minutos por CPU; no
es una garantía de tiempo para otras propuestas.

Las pruebas automáticas incluyen ocho casos de versiones/estados, integridad
de adjuntos, números ambiguos, citas y cambio de estado durante la lectura.
Las 16 pruebas Python del repositorio y la revisión de GitHub aprobaron.
