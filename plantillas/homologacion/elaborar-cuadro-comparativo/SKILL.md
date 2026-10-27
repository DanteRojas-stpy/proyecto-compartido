---
name: elaborar-cuadro-comparativo
description: Elabora y valida el cuadro comparativo de obra en la plantilla Excel del usuario a partir de datos ya homologados. Úsala para preparar el archivo de comparación; no interpreta equivalencias técnicas ni rehace la homologación.
---

# Elaborar el cuadro comparativo

Resuelve únicamente el proceso 9 de CostFlow. Recibes los datos homologados y
las decisiones registradas. La entrega es el Excel y su resultado de validación.
No invoques otra skill ni vuelvas a decidir correspondencias técnicas.

## Entradas y recursos

- Datos homologados, sus originales, referencias y pendientes según
  [entrada y plantilla](references/entrada-y-plantilla.md).
- Plantilla Excel del usuario y ubicación de sus campos. Si falta el mapeo,
  inspecciona la plantilla antes de escribir; no inventes coordenadas.
- Presupuesto meta cuando exista y datos del proyecto para identificar la revisión.

Para presentar el formato histórico, consulta
[hoja principal](references/estructura-hoja1.md) y
[análisis y leyenda](references/estructura-hoja2-y-leyenda.md). La plantilla del
usuario prevalece: esas referencias no autorizan rediseñarla, borrar fórmulas o
agregar hojas si no corresponden al formato solicitado.

## Trabajo

1. Verifica solicitud, partida y versiones; identifica pendientes bloqueantes.
   Si se solicita un borrador con pendientes, márcalo como tal y conserva vacíos
   los datos no comparables. No lo presentes como cuadro final validado.
2. Trabaja sobre una copia con nueva revisión de la plantilla del usuario.
   Traslada los valores homologados sin recalcular equivalencias, cambiar el
   tipo de cambio autorizado ni completar datos ausentes.
3. Mantén visibles las referencias, diferencias y escenarios ya suministrados.
   El precio del proveedor y el escenario nivelado permanecen identificados.
4. Recalcula y aplica los controles de
   [validación del archivo](references/validacion.md). Entrega el Excel y los
   resultados reales de las comprobaciones.

## Scripts y ejemplos de referencia

`scripts/generar_cuadro_referencia.py` y `scripts/validar_cuadro_referencia.py`
son copias del generador histórico y su validador. El primero crea un libro
nuevo: **no llena la plantilla arbitraria del usuario**. Se incluyen para
pruebas del formato histórico y como material para adaptar la generación;
no son la implementación final del proceso 9.

El [formato del generador de referencia](references/formato-entrada.md)
explica su JSON. Los casos de `assets/ejemplo_gas.json` y
`assets/ejemplo_ascensores.json` son ficticios; no sustituyen datos del proyecto.
`assets/ejemplo_salida_gas.xlsx` muestra el formato histórico. Leer o generar
estos ejemplos no resuelve la homologación del caso real.

## Límites

- No elijas el postor ni generes una recomendación técnica nueva. Presenta las
  observaciones y propuestas recibidas con su estado de revisión.
- No derives datos faltantes de otra oferta para llenar la oferta original.
- No utilices un cambio ficticio o predeterminado para completar uno ausente.
- No declares VALIDADO si faltó recalcular, no se pudieron verificar totales o
  persisten pendientes que bloquean la comparación final.
- La entrega local no autoriza envío de correos ni publicación del archivo.

## Uso independiente en n8n

Un paso separado recibe los datos homologados y la plantilla, llama al servicio
de Excel y registra archivo y validación. Debe cargar solo esta skill y los
recursos que necesite. n8n no lee automáticamente los archivos enlazados ni
ejecuta Python por el hecho de incluir estas instrucciones. La instalación del
servicio y la adaptación a la plantilla siguen siendo trabajos de integración.
