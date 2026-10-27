# Comprobar el cuadro antes de entregarlo

Verifica que la salida use la plantilla prevista y la solicitud, partida y
versiones correctas. Contrasta los valores contra los datos recibidos; no basta
con que el Excel abra sin errores.

- Recalcula las fórmulas con un motor de Excel compatible y busca errores.
- Comprueba cada total con su base, moneda y tratamiento de impuestos. Separa
  el monto declarado de ajustes identificados y de escenarios de nivelación.
- Comprueba fórmulas, formato y estructura de la plantilla después de escribir.
- Revisa visualmente encabezados, saltos, legibilidad, unidades, monedas y notas.
- Conserva vacíos los datos ausentes y muestra los pendientes. No sustituyas un
  dato ausente por cero. La recomendación, si se muestra, es la propuesta recibida.
- Registra qué se comprobó, qué falló y qué no pudo comprobarse. No marques
  como validado un archivo que solo fue generado o abierto.

## Alcance del validador histórico incluido

`scripts/validar_cuadro_referencia.py` recalcula con LibreOffice, busca errores,
revisa que la primera hoja no enlace otras hojas y compara subtotales del
formato histórico; usa el total declarado si se proporcionó en el JSON.

Sus búsquedas dependen de las filas, encabezados y bloques de ese formato. No
es un validador universal para cualquier plantilla. La comprobación de la
segunda hoja debe reforzarse: el código actual permite que su subtotal falte.
Tampoco exige un total declarado cuando el JSON no lo trae, valida equivalencia
técnica ni verifica todos los datos de entrada. Un resultado VALIDADO del
script solo describe sus comprobaciones, no resuelve estas limitaciones.

Para otra plantilla se necesita un mapeo y controles de sus rangos. La ausencia
de Python, `openpyxl` o `soffice` deja la generación/validación pendiente de
entorno; no se debe ocultar ese resultado ni afirmar que la comprobación ocurrió.
