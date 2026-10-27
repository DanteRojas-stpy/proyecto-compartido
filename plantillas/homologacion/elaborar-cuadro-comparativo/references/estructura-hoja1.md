> Referencia visual del formato histórico. Aplicar solo donde coincida con la
> plantilla del usuario. Mostrar las clasificaciones, escenarios y propuestas
> ya suministrados; estas convenciones no autorizan rehacer la homologación.

# Hoja 1: formato original (cuadro histórico)

La Hoja 1 reproduce el formato de los cuadros comparativos históricos del área de costos. Es lo primero que se ve al abrir el archivo y es la hoja que se presenta. **No se rediseña**: se llena.

Principios:

- **Valores escritos.** Metrados y P.U. de cada postor se escriben como números (no vínculos a otras hojas). Así la hoja se puede copiar o enviar sola sin romperse.
- **Solo fórmulas internas:** parcial `=PU*Cant`, subtotales `=SUM(...)`, pie de totales, DELTA y variación. Se permite una fórmula aritmética que deje rastro de un recálculo (ej. `=50900/2000` cuando el P.U. impreso no coincide con el parcial).
- **Sin columna de observaciones.** Lo que haya que explicar va en un **comentario corto** de la celda (1-2 frases).
- **Breve.** No sobreexplicar. El análisis largo vive en la Hoja 2.

## Vista y configuración

| Elemento | Valor |
|---|---|
| Fuente | Arial 14 en todo el cuadro (títulos más grandes, criterios 11-12) |
| Zoom | 60 % |
| Líneas de cuadrícula | Ocultas |
| Inmovilizar paneles | `G8` (descripción y meta fijas, encabezados fijos) |
| Color de pestaña | Azul marino `002060` |

## Columnas

| Col. | Ancho | Contenido |
|---|---|---|
| A | 3.3 | margen |
| B | 107.6 | Descripción |
| C | 7.6 | Unid |
| D | 13.2 | Metrado (meta) |
| E | 17.1 | P.Unitario (S/) (meta) |
| F | 29.3 | P.Parcial (S/) (meta) `=E*D` |
| G | 4.1 | separador |
| H… | | Un bloque por postor |

Bloque por postor (desde H, contiguos, sin separador entre bloques):

| Caso | Columnas del bloque | Anchos |
|---|---|---|
| Normal (soles) | Cant. · P.Unitario (S/) · P.Parcial (S/) | 13 · 22 · 34 |
| Con descuento | + P.Unitario (S/) INC DSCTO x% · P.Parcial (S/) INC DSCTO x% | + 22 · 34 |
| En dólares | Cant. · P.Unitario (US$) · P.Unitario (S/) · P.Parcial (S/) | 13 · 20 · 22 · 34 |

- **Descuento:** la tasa se escribe en la fila 9 (fila total), en la columna "P.Unitario INC DSCTO", como número azul negrita (`0.05` con formato %). P.U. neto `=PU*(1-$tasa)`. Si un postor no da descuento pero se espera negociar, se puede mostrar el bloque con 0.00 %.
- **Dólares:** `E5 = "TC"`, `F5 = tipo de cambio` (número azul, comentario "editable"). P.U. (S/) `=PU_US$*$F$5`. Todo el pie se expresa en soles.

## Encabezado (filas 2-7)

| Fila | Contenido | Formato |
|---|---|---|
| 2 | `OBRA: <NOMBRE DE LA OBRA - ETAPA - TORRE>` | Arial 24 negrita |
| 3 | `COMPARATIVO - <SISTEMA / PARTIDA>` | Arial 20 negrita |
| 4 | `FECHA: 26 DE OCTUBRE DEL 2026` | Arial 14 negrita |
| 5 | (solo dólares) `TC` en E5, valor en F5 | |
| 6 | `PRESUPUESTO META` combinado B6:F6 · nombre de cada postor combinado sobre su bloque | Meta: relleno azul marino, letra blanca. Postores: **verde limón `CCFF33`**, letra negra negrita |
| 7 | Descripción · Unid · Metrado · P.Unitario (S/) · P.Parcial (S/) · por postor Cant. / P.Unitario / P.Parcial | Igual que fila 6; alto 35 |

En la Hoja 1 **todos los encabezados de postor van en verde limón** (los colores de estado van en la Hoja 2).

## Cuerpo

| Fila | Qué es | Relleno | Fuente |
|---|---|---|---|
| 9 | **Total de la partida** (ej. INSTALACIONES DE GAS / CD - SUPERESTRUCTURAS) `=SUM(capítulos)` | Azul tema (accent 5) tint 0.6 | negrita |
| 10 | vacía | | |
| capítulo nivel 1 | título del capítulo; subtotal `=SUM(hijos)` o `=E*D` si tiene meta propia | Azul tema tint 0.8 | negrita |
| capítulo nivel 2 | subcapítulo | Gris claro (tema fondo, tint −0.15) | negrita |
| capítulo nivel 3 | sub-subcapítulo | Tema 9 tint 0.8 | negrita |
| separadora | debajo de cada título de capítulo | | alto **6** |
| ítem | partida | blanco | normal |

Alto normal de fila: 17.4.

### Colores de texto en ítems

| Caso | Formato |
|---|---|
| Descripción de una partida que cotizan 2 o más postores (comparable) | **azul** `0070C0` |
| Descripción de partida no comparable | negro |
| Cant. / P.U. / parcial observados (metrado dudoso, P.U. recalculado, línea no sumada por el postor) | **rojo negrita** `C00000` + comentario |
| Texto en la celda Cant. ("No incluye…", "Incluido en el costo del equipo") | Arial 11; rojo negrita si es exclusión, negro si está incluido |

### Precio global de un postor (cotiza por suma alzada sin desagregar)

- En la **fila del capítulo**, el postor lleva su cantidad y P.U. global (ej. `120 dpto × 900.00`, `1 glb × 18,000.00`), parcial `=PU*Cant`, comentario corto ("Postor A: 120 und × S/ 900.00 = S/ 108,000.00").
- Sobre las filas de ítems de ese capítulo, el bloque del postor se **combina** en una sola celda con texto **rojo negrita Arial 11**, alineado arriba a la izquierda, explicando qué incluye: "Precio global por departamento (120 und × S/ 900.00): incluye tubería, válvulas y pruebas, sin desagregar."
- La misma celda combinada sirve para advertir un alcance no especificado: "No especifica gabinetes ni válvulas (verificar alcance)."

### Meta

- Si hay presupuesto meta, se escribe en D-E por ítem o por capítulo.
- Si no hay meta, la celda E del capítulo se rellena **dorado claro `FFF2CC`** con comentario: "Presupuesto meta: dato no incluido en las cotizaciones. Ingresar para calcular el DELTA."

### Comentarios (cortos)

Úsalos solo cuando ayudan a leer el número:

- Subtotal del capítulo que replica una suma errada del postor: "Suma solo gabinetes y válvulas (S/ 640.00), igual que el subtotal del postor; la línea de meter conector no está en su subtotal."
- P.U. recalculado: "El postor muestra P.U. S/ 25.40 pero su parcial es S/ 50,900.00 (50,900 / 2,000 = 25.45); se usa el parcial."
- Precio global: "1 glb × S/ 18,000.00 = S/ 18,000.00."
- GG y utilidad incluidos: "GG 10 % y utilidad 5 % sobre el costo directo, según su cotización."

## Pie de totales

Dejar 3 filas libres después del último ítem. Rótulos en D:E (combinados) alineados a la derecha, relleno azul marino, letra blanca negrita; F con el valor meta, también azul marino.

| Rótulo | Meta (F) | Postor (columna de parcial final) |
|---|---|---|
| PARCIAL (SIN IGV) | `=F9` | `=J9` |
| GASTOS GENERALES | 0 | `=J53*0.10` si el postor los suma aparte, si no 0 |
| UTILIDADES | 0 | `=J53*0.05` si el postor la suma aparte, si no 0 |
| SUBTOTAL (SIN IGV) | `=SUM(F53:F55)` | `=SUM(J53:J55)` |
| IGV (18%) | `=+F56*0.18` | `=+J56*0.18` |
| TOTAL INC. IGV | `=+F56+F57` | `=+J56+J57` |

- **TOTAL INC. IGV más bajo en azul negrita, más alto en rojo negrita**; los intermedios en negro.
- Si el detalle de un postor no suma su total declarado, se agrega antes del pie una fila **AJUSTE A PRECIO DECLARADO** con la diferencia (rojo negrita + comentario) y se suma en la fila total.

## Filas de comparación (verde limón)

Inmediatamente debajo del pie, con rótulo combinado B:F (azul marino, letra blanca, alineado a la derecha) y el valor combinado sobre el bloque de cada postor (relleno verde limón, negrita, centrado):

| Rótulo | Fórmula |
|---|---|
| DELTA | `=IF($F$58=0,"Ingresar meta",$F$58-J58)` |
| VARIACIÓN vs. OFERTA MÁS BAJA | `=J58/MIN($J$58,$M$58,$P$58)-1` (formato 0.0 %) |
| Ratio útil de la partida | ej. COSTO POR DEPARTAMENTO (S/, SIN IGV) `=J56/120`; COSTO POR ASCENSOR; COSTO POR PUNTO |

## Criterios comerciales y técnicos

Rótulo en la **columna F** (Arial 12, relleno gris muy claro, ajuste de texto, borde fino) y el texto de cada postor combinado sobre su bloque (borde fino).

Orden base (se agregan los propios de la partida, usar los criterios de especialidad recibidos en los datos homologados):

1. ADELANTO / TIPO DE GARANTIA
2. FRECUENCIA DE VALORIZACIONES
3. FONDO DE GARANTIA
4. CONTACTO (o CONTACTO MANO DE OBRA): "Empresa: … / Contacto: … / Correo: … / Teléfono: …" (Arial 11 negro, izquierda)
5. CONSIDERACIONES: viñetas "- …" (Arial 11, izquierda, fila alta)
6. N° DE OBRAS ACTUALES EN EJECUCION
7. VALIDEZ DE LA OFERTA
8. PLAZO DE EJECUCION
9. GARANTIA (de la instalación / del equipo)
10. Propios de la partida: REAJUSTE DE PRECIOS, VIGA DIVISORIA, PLAZO DE ENVÍO / ENTREGA, MANTENIMIENTO GRATUITO, FORMA DE PAGO, CARACTERÍSTICAS DE LAS CABINAS…

Texto de criterios: Arial 12, centrado, ajuste de texto.

| Color | Significado | Ejemplos |
|---|---|---|
| **Azul negrita** | ventaja / cumple | "Adelanto 0%", "5% devuelto a los 18 meses", "3 años" |
| **Rojo negrita** | desventaja / riesgo de costo | "Validez 10 días: venció", "No indica plazo", "Adelanto 50%", "Máximo 5% en caso se requiera" |
| **Negro negrita** | dato faltante o a confirmar | "No indica.", "Por confirmar" |
| Negro normal | informativo | "Valorizaciones quincenales; pago a 15 días" |

Alto de fila según el texto (las de CONSIDERACIONES suelen ser muy altas: ajustar para que se lea todo).

Redacción: frases cortas, sin adjetivos. Bien: "No incluye rejillas de ventilación." Mal: "Lamentablemente el postor no ha considerado dentro de su alcance las rejillas…".
