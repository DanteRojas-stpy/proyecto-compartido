# E5: elaborar el cuadro comparativo

Flujo local: **CostFlow - E5 Elaborar cuadro comparativo**, id `costflowE5Cuadro01`.
Exportación: `flujos/e5-elaborar-cuadro-comparativo.json`.
Aplica la skill `elaborar-cuadro-comparativo`; no vuelve a homologar ni usa IA
para escribir fórmulas o decidir equivalencias.

## Relación con E4

E4 entrega sus registros al nuevo nodo **Entregar a cuadro comparativo E5**,
que llama al segundo flujo una vez con el lote completo. También se puede
llamar directamente a **Recibir salida de homologación** desde la etapa de
revisión. No se activó un calendario ni se creó un webhook público.

La salida actual de E4 es una propuesta: `requiere_revision`, con correspondencias
pendientes y `comparable: null`. E5 la recibe, conserva los registros en
`datos.homologaciones` y devuelve `pendiente_validacion`. No transforma esos
indicadores en una aprobación. La etapa de revisión del especialista debe
registrar los datos comparables y las decisiones; esta entrega no implementa
su pantalla ni suplanta al especialista.

## Entrada después de la revisión

Se admite un ítem n8n por proveedor, como en E4, o un ítem con
`homologaciones: [registro1, registro2, ...]`. Se agrupa por solicitud y se
comprueba que la plantilla y la base coincidan. No se elige entre dos versiones
de un mismo proveedor ni se mezclan solicitudes. Para esta copia de la plantilla
se admiten de 1 a 7 proveedores y una partida/agrupación validada en la fila 13.
Más partidas o alternativas del mismo proveedor requieren ampliar el mapeo.

Cada registro conserva la estructura E4 y requiere:

- `estado_revision: listo_para_cuadro` y `habilitado_para_cuadro: true`.
- Ausencia de pendientes bloqueantes activos.
- Una decisión en `decisiones` con `tipo: homologacion_validada`, `version_id`,
  `aprobado_por` y `aprobado_at`. Es información entregada por la etapa de
  revisión autenticada; no constituye un mecanismo nuevo de aprobación por sí sola.
- El ítem con `correspondencia: validada_especialista` y `comparable`:

```json
{
  "partida_id": "identificador_de_la_base",
  "unidad": "und",
  "cantidad": 2,
  "precio_unitario_usd": 100,
  "precio_unitario_pen": 370,
  "parcial_pen": 740
}
```

Los números son ficticios. Si la oferta comparable es en soles, el precio USD
es `null`. La comparación usa PEN. Un precio USD requiere el tipo de cambio
autorizado de E4 (valor, sentido USD_PEN, fecha, fuente y aprobado_por). No se
obtiene un cambio de Internet ni se sustituye un faltante por 1.

Además, `totales_validados` contiene montos en soles y la tasa informada:

```json
{
  "gastos_generales_pen": 0,
  "utilidad_pen": 0,
  "igv_tasa": 0.18,
  "subtotal_sin_igv_pen": 740,
  "total_con_igv_pen": 873.20
}
```

Cero debe estar respaldado por los datos validados; no se deduce de un campo
ausente. Los campos no disponibles quedan vacíos y se informan; no se declara
validación completa sin controles suficientes. Un subtotal declarado requiere
sus componentes para contrastarlo. Las condiciones comerciales se trasladan
desde `postores[0].campos`, sin volver a interpretarlas.

El contenedor de entrada también puede indicar `revision` y `presupuesto_meta`.
La meta opcional requiere cantidad, precio unitario PEN, GG PEN y utilidad PEN.
Si no llega, el presupuesto histórico de la plantilla se limpia y DELTA muestra
**Ingresar meta**. El servicio incrementa la revisión si ya existe otra para la
misma solicitud y nunca sobrescribe una entrega.

## Qué coordina n8n

1. Agrupar y revisar la entrada; detener las propuestas no validadas.
2. Volver a consultar estados, versiones y aclaraciones de Nhost; comprobar
   también que no cambiaron la plantilla registrada ni el itemizado revisado.
3. Descargar la plantilla registrada en la solicitud.
4. Enviar plantilla y datos al servicio local autenticado.
5. Recibir archivo e informe; descargar el Excel al binario `cuadro` del nodo
   **Entregar cuadro y validación**.

La exportación del repositorio no contiene contraseñas. En la instalación local,
los dos nodos HTTP de Nhost usan la conexión existente y los tres nodos del
servicio usan **CostFlow Excel local**. El token se guarda fuera del repositorio.
No se enviaron correos ni se añadió subida automática del cuadro a Nhost.

## Qué hace el servicio de Excel

- `app/comparativo/plantilla.py` valida el contrato y prepara el mapa de celdas.
- `calcular_formulas.mjs` usa el motor de hojas de cálculo para recalcular las
  fórmulas del cuadro y proporcionar los valores calculados.
- El llenado modifica solo las celdas previstas en una copia OOXML. No reexporta
  el libro completo, porque la prueba de compatibilidad mostró pérdida de VML,
  comentarios, extensiones y ajustes de impresión al hacerlo.
- Se preservan estilos, combinaciones, anchos, alturas, hojas de respaldo,
  comentarios y extensiones. Se invalida únicamente la cadena de cálculo, que
  Excel reconstruye, y se activa recálculo al abrir.
- Cantidad, PU, TC, parciales, GG, utilidad, IGV y totales se escriben como números
  o fórmulas. Los controles numéricos distinguen un cero real de una celda vacía.
- Los totales calculados se contrastan con los validados (tolerancia S/ 0.02).
- Los valores anteriores de proveedores y los textos de ejemplo no se reutilizan.

Se comprueba el hash de la plantilla compartida contra el contrato inspeccionado.
Otra copia, aun con el mismo nombre, requiere revisar su mapeo antes de generar.
No es un rellenador universal para cualquier plantilla.

## Observación preexistente de la plantilla

`PLANTILLA!AP9` contiene `=AL9+#REF!`, fuera del cuadro principal. Se conserva y
se informa en `referencias_invalidas_preexistentes`. Por eso la salida de esta
plantilla es `generado_con_observaciones`, con cálculos del cuadro contrastados
y formato preservado, pero `validacion_global: false`. No se presenta como
un libro completamente libre de errores ni se repara esa celda sin encargo.

## Servicio local y archivos

`scripts/iniciar_generador_comparativo.ps1` arranca el servicio oculto en el
puerto 18775. Usa el Python del entorno del proyecto y el runtime Node con
`@oai/artifact-tool` disponible en este equipo; admite rutas explícitas para
otra instalación. No instala dependencias globales ni requiere LibreOffice.

```powershell
.\scripts\iniciar_generador_comparativo.ps1
# Después de actualizar su código:
.\scripts\iniciar_generador_comparativo.ps1 -Restart
```

La conexión de n8n es `http://host.docker.internal:18775`. El servicio exige
la cabecera local configurada en su credencial para generar y descargar. No
acepta rutas del disco enviadas por el cliente: recibe la plantilla en base64.

Los archivos están en `%LOCALAPPDATA%\CostFlow\comparativos\salidas\<job_id>`:
plantilla de entrada, Excel resultante, `datos_validados.json` y `validacion.json`.
El token y el PID del servicio están en la carpeta superior. No subirlos a Git.
El servicio permanece iniciado en esta sesión; tras reiniciar Windows hay que
arrancarlo con el script. No se creó una tarea programada del sistema.

## Verificación realizada

- La salida de E4 se entregó a E5 mediante Execute Workflow en n8n y terminó
  pendiente, sin aprobar ni generar a partir de la propuesta sin revisar.
- El recorrido positivo en n8n recibió dos proveedores ficticios validados,
  consultó una fuente de prueba aislada y obtuvo el Excel del servicio real.
- Sus totales fueron S/ 873.20 y S/ 944.00. Se verificaron los valores guardados,
  fórmulas, ocho hojas y preservación de las partes ajenas al llenado.
- También se cambió el TC y se comprobó un importe cero real, sin reutilizar
  cachés ni convertir datos ausentes en cero. Se revisaron visualmente el cuadro
  y las condiciones. No se usaron ofertas reales para las pruebas.

El llenado no necesita Ollama: es un proceso determinista separado de E4.
