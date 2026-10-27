# Plantilla de homologación

Esta carpeta distingue dos skills independientes:

| Proceso | Skill | Entrega |
|---|---|---|
| 6. Homologación | [homologar-cotizaciones/SKILL.md](homologar-cotizaciones/SKILL.md) | Datos comparables, procedencia y pendientes; no genera Excel. |
| 9. Cuadro comparativo | [elaborar-cuadro-comparativo/SKILL.md](elaborar-cuadro-comparativo/SKILL.md) | Excel en la plantilla del usuario y resultado de validación; no rehace la homologación. |

Cada carpeta es autocontenida. Se pueden cargar por separado y no existe una
skill que ejecute ambos procesos. Compartir los datos de salida de homologación
con el proceso de cuadro no implica cargar las dos skills en un mismo agente.

En n8n, usar un paso independiente para cada proceso. El segundo recibe los
datos homologados, las decisiones registradas y la plantilla del usuario.
Las instrucciones no conectan ni activan automáticamente los nodos de n8n.

Los archivos del paquete original que Dante proporcionó se conservan en esta
carpeta raíz como respaldo. Su `SKILL.md` combina ambos procesos y no es el
punto de entrada de las dos skills nuevas. El ZIP original tampoco cambia.

El generador histórico incluido en la skill de cuadro produce un libro nuevo
de referencia. Todavía no llena una plantilla arbitraria del usuario; la skill
lo distingue de la generación final requerida por CostFlow.
