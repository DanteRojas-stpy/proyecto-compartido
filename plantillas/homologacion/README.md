# Plantilla de homologación

Plantilla Excel para el proceso 6 (homologación de cotizaciones finales). La usa
el flujo E4, que lee las versiones finales y propone la homologación con
evidencia. El especialista la revisa y decide.

## Archivo

- `plantilla_homologacion.xlsx`: hojas `Instrucciones`, `Parametros`, `Partidas`,
  `Homologacion`, `Resumen` y `Listas` (oculta, con las opciones de los desplegables).

## Cómo se construyó

Se tomó el patrón común de los comparativos históricos de la empresa (ya no incluidos en el repositorio): por cada
partida, el metrado, el precio por proveedor en dólares o soles, el tipo de cambio
y el parcial. La plantilla lo ordena en formato largo (una fila por partida y
proveedor), porque así el flujo puede leerla y guardarla en la base.

La plantilla de ascensores (`HISTORICO_COMPARATIVO_ASCENSOR_5.2`) define los
campos de negocio que espera E4. Los históricos no incluyen plazo, garantía ni
validez como filas: esos datos se registran desde la cotización original.

## Reglas

1. **No se publican precios reales.** La plantilla viene vacía. Los comparativos
   históricos quedan fuera del repositorio.
2. Las columnas con fórmula (`calc.`) no se escriben a mano.
3. La IA propone equivalencias; el especialista las aprueba.
4. Un cambio de estructura entra por Pull Request, porque el flujo depende de
   estos nombres de columna.
