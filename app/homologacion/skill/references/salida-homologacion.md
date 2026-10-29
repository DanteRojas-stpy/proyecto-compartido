# Entrega: homologacion.json

Formato documental de intercambio propuesto para esta separación de skills.
No es una migración de Nhost ni un nodo instalado en n8n. El adaptador desde
las lecturas actuales de E3 sigue siendo una tarea de integración.

La entrega incluye los campos siguientes:

| Campo | Contenido |
|---|---|
| `solicitud_id` | Identificador de la solicitud. |
| `proyecto` | Código, obra, fecha de evaluación y revisión. |
| `especialidad` | Código y nombre de la partida. |
| `estado_revision` | `listo_para_cuadro` si no hay pendientes bloqueantes; `requiere_revision` en caso contrario. No equivale a adjudicación. |
| `base` | Identificador y versión del itemizado, o base provisional expresamente identificada. |
| `moneda_comparacion` | PEN, USD o null si aún no se definió. |
| `tipo_cambio` | Valor, sentido, fecha, fuente y autorización, o null si no corresponde/no está disponible. |
| `postores` | Identificador, nombre, versión, moneda, totales y condiciones originales; estado de vigencia y archivos de respaldo. |
| `partidas` | Código de base, descripción, unidad y metrado; oferta original de cada postor y valores comparables, cuando existan. |
| `trazabilidad` | Archivo y página/sección por dato; operación y referencia utilizada para cada valor derivado. |
| `pendientes` | Proveedor/partida afectada, motivo, si bloquea comparación y decisión requerida. |
| `escenarios` | Nivelaciones o estimados con hipótesis, valores, origen y autorización, separados de lo cotizado. |
| `decisiones` | Decisiones efectivamente registradas del especialista, con su referencia. |

Los códigos de solicitud, proveedor, versión y partida deben conservarse al
transferir datos. No sustituyas identificadores con nombres de archivos.

Una oferta por partida debe diferenciar:

- **Original:** descripción, unidad, cantidad, precios, parcial, moneda e IGV
  tal como se recibieron. Texto y número interpretado se guardan por separado.
- **Relación:** partida de base, evidencia y estado de correspondencia técnica.
- **Comparable:** cantidades y precios normalizados, con operación y criterio.
- **Estado:** cotizado, incluido con evidencia, global, no cotizado o pendiente.

Un dato ausente es `null`; una inclusión no es un precio cero. Si hay pendientes,
el diagnóstico puede entregarse con `requiere_revision`, sin afirmar que ya
existe una oferta técnicamente equivalente o un cuadro final.

Este archivo contiene datos y decisiones. No define columnas, colores, hojas
ni fórmulas de Excel y no ordena ejecutar el proceso de cuadro comparativo.
