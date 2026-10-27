# Datos homologados y plantilla del usuario

Este proceso puede recibir datos homologados de cualquier fuente autorizada.
No necesita cargar ni ejecutar una skill de homologación.

## Comprobaciones de entrada

Recibe `homologacion.json` o una estructura equivalente con solicitud, proyecto,
especialidad, base utilizada, moneda de comparación, postores y versiones,
partidas, importes originales/comparables, procedencia, decisiones, escenarios
y pendientes. `estado_revision` indica `listo_para_cuadro` o `requiere_revision`.
No infieras que una equivalencia fue aprobada porque tiene un precio normalizado.

Conserva la moneda de cada original. Los totales declarados y los totales
comparables deben indicar su moneda y tratamiento de impuestos para verificar
que no se comparen bases distintas. Una conversión debe incluir cambio, sentido,
fecha, fuente y autorización; este proceso solo la presenta según lo recibido.

Ante datos inconsistentes o pendientes bloqueantes, devuelve la observación al
flujo que llamó a este proceso. No inventes una resolución técnica. Un borrador
expresamente solicitado puede mostrar pendientes y vacíos sin declarar validación final.

## Plantilla

Usa el archivo del usuario como base del libro. Identifica hojas, campos, rangos,
fórmulas existentes y espacios de cada postor. Guarda esa correspondencia para
la generación, sin asumir que la plantilla histórica utiliza las mismas celdas.

Escribe los valores en las zonas previstas y respeta formato, fórmulas y hojas.
Genera una copia con nueva revisión; no sobrescribas una entrega anterior.
El TC en F5 y los nombres de hojas de las referencias son convenciones del
formato histórico, aplicables solo si la plantilla corresponde a ese formato.

## Generador histórico: uso limitado a referencia

Este generador consume `entrada.json`, no directamente la salida de E3 ni todo
`homologacion.json`. Una adaptación debe trasladar únicamente los datos ya
homologados al formato documentado, sin inventar precios o correspondencias.
Los campos adicionales de trazabilidad y revisión no quedan validados por el
script histórico y deben conservarse en el registro de la solicitud.

Para ensayar el caso ficticio de gas, ejecuta con el Python del entorno del
proyecto desde la carpeta de esta skill:

```text
python scripts/generar_cuadro_referencia.py assets/ejemplo_gas.json salida-prueba/
python scripts/validar_cuadro_referencia.py RUTA_EXCEL_GENERADO assets/ejemplo_gas.json
```

En Windows usa la ruta absoluta a `.venv/Scripts/python.exe` del proyecto.
Para `RUTA_EXCEL_GENERADO`, usa la ruta exacta que imprima el generador.
Requiere `openpyxl`; el validador también requiere LibreOffice (`soffice`).
El n8n local en Docker no tiene disponibles esos ejecutables actualmente.

El formato de salida ilustrativo no sustituye la plantilla del usuario. No
ejecutes esta prueba como si fuera la entrega de un caso real.
