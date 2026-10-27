> Referencia visual del formato histórico. Aplicar solo donde coincida con la
> plantilla del usuario. Mostrar las clasificaciones, escenarios y propuestas
> ya suministrados; estas convenciones no autorizan rehacer la homologación.

# Hoja 2 (desglose), LEYENDA Y NOTAS y hojas de cotización

## Hoja 2: cuadro desglosado para decidir

Misma lógica de filas que la Hoja 1, pero con **todo el análisis**: homologación partida por partida, colores de la leyenda, columna de observaciones, ratios, nivelación, criterios ampliados y recomendación. Aquí sí se permiten vínculos a las hojas de cotización (trazabilidad: cada número se puede seguir hasta su origen).

### Vista y columnas

- Arial 12 (títulos 18 y 14), zoom 80 %, sin cuadrícula, inmovilizar en `G8`.
- B 66 · C 8 · D 11 · E 12 · F 15 · G 1.6 (separador) · bloques de postor (Cant. 11, P.U. 15, Parcial 18; descuento y US$ igual que en la Hoja 1) · separador 1.6 · **OBSERVACIONES / MOTIVO DEL RESALTADO** (ancho 80, combinada filas 6-7, azul marino, letra blanca).

### Encabezado de cada postor = su estado

| Estado | Relleno | Letra |
|---|---|---|
| Recomendado | verde intenso `00B050` | blanca negrita |
| Menor precio (si no es el recomendado) | verde limón `CCFF33` | negra negrita |
| En negociación / observado | amarillo `FFFF00` | negra negrita |
| Más caro / sobre meta | naranja `FFC000` | roja `C00000` negrita |
| Versión anterior de una oferta | negro | amarilla |

### Filas del cuerpo

| Fila | Relleno |
|---|---|
| 9 Total de la partida | negro, letra naranja `FFC000` negrita |
| Capítulo nivel 1 | `9DC3E6` |
| Subcapítulo nivel 2 | `DEEBF7` |
| Nivel 3 | `F2F2F2` |
| Precio global de un postor | fila propia al inicio del capítulo, **gris `F2F2F2` negrita**: "<CAPÍTULO> - PRECIO GLOBAL POSTOR A" con su Cant. y P.U. global |
| Ítem | según su clase (abajo) |

Si hay descuentos, la tasa va en la fila 9 (número azul editable) y los P.U. netos se calculan con ella: se puede simular una negociación cambiando ese número.

### Clase de cada ítem (relleno de la descripción) y su motivo en OBSERVACIONES

| Clase | Formato de la descripción | Cuándo | Texto típico en OBSERVACIONES |
|---|---|---|---|
| Normal | sin relleno | todos la cotizan | (solo notas de metrado/P.U.) |
| Omitida | **celeste `CCFFFF`** | está en la base y algún postor no la cotiza ni la declara incluida | "CELESTE: partida no cotizada por Postor C (se valoriza en la NIVELACIÓN)." |
| Fuera de base, 1 postor | **roja sobre dorado claro `FFF2CC`** | no está en la base y solo un postor la cotiza | "ROJO/DORADO: partida cotizada SOLO por Postor C. Confirmar si se requiere." |
| Fuera de base, varios | **azul sobre dorado claro** | no está en la base pero la cotizan varios | "AZUL/DORADO: alcance real que la base no consideró." |
| Alto impacto | **amarillo claro `FFFFCC`** | diferencia entre postores mayor al umbral (S/ 10,000 por defecto) | "AMARILLO CLARO: ALTO IMPACTO, diferencia de S/ 12,440 entre Postor B y Postor C." |
| Alerta crítica | **roja negrita sobre amarillo `FFFF00`** | total que no cuadra, duplicado, unidades distintas (m3 vs ml), metrado sin precio, texto que contradice el cuadro | "ROJO SOBRE AMARILLO: ALERTA. El postor cotiza 3 gabinetes pero su texto dice que no incluye gabinetes. Aclarar." |
| Referencial | **gris negrita** | partida opcional que no se suma | "GRIS: referencial, no se suma." |

Marcas en números (independientes de la clase):

| Marca | Regla | Texto |
|---|---|---|
| **Cantidad en azul** | metrado del postor difiere más de 2 % del de la base | "AZUL (cant. Postor C): metrado 2,300.00 vs base 2,000.00 (+15%)." |
| **P.U. rojo negrita** | P.U. neto ≥ 30 % sobre el menor P.U. de los postores | "ROJO NEGRITA (P.U. Postor C): S/ 140.00 vs S/ 105.00 (+33%)." |
| Celda **"INCL."** | el postor declara que está incluida en otra partida | "Postor C: incluido en su partida de gabinetes." |
| Celda amarilla **"INCL.?"** | se asume incluida pero no está claro | "Inclusión no confirmada: revisar el alcance antes de contabilizarla." |
| **Número azul** | dato editable (GG %, utilidad %, descuento %, TC, estimados) | |

Cada fila resaltada **debe** tener su motivo en OBSERVACIONES. Varias marcas en una fila se escriben en líneas separadas, la más importante primero. Para partidas incluidas en el global de otro postor: "Postor A no la detalla: incluida en su precio global del capítulo."

### Pie y comparación

| Fila | Contenido |
|---|---|
| COSTO DIRECTO (SIN IGV) | `=fila 9` |
| GASTOS GENERALES | tasa azul editable en la columna P.U. × costo directo |
| UTILIDAD | ídem |
| SUBTOTAL (SIN IGV) | suma. OBSERVACIONES: "Debe cuadrar con cada cotización (sin IGV): Postor A S/ …" |
| IGV (18%) / TOTAL INC. IGV | |
| DELTA (PRESUPUESTO META - POSTOR, INC. IGV) | `"Falta ppto. meta"` si no hay meta |
| DIFERENCIA vs. MENOR OFERTA (INC. IGV) | en soles |
| VARIACIÓN % vs. MENOR OFERTA | |

Las tres filas de comparación van en verde limón, combinadas sobre cada bloque.

### Secciones de análisis (rótulo azul marino con el nombre corto de cada postor)

1. **ANÁLISIS DE PRECIOS UNITARIOS Y RATIOS (SIN IGV):** ratios de la partida (por dpto, por punto, por ml, por ascensor, por parada, por kg), subtotal de cada capítulo, metrados totales clave ("Metrado total de cobre: 180 ml vs 40 ml") y P.U. promedio por ml. Comentar en OBSERVACIONES lo que el ratio revela (subdimensionado, copiado de otro proyecto, incluye accesorios…).
2. **NIVELACIÓN POR ALCANCE (SIN IGV):**
   - `(+) Partidas no cotizadas (celestes y rojo/dorado), al menor precio de los otros postores` = suma de `MIN(parcial de los otros)` de cada partida que el postor no cotiza ni declara incluida.
   - PRECIO NIVELADO (SIN IGV) = subtotal + adicional.
   - PRECIO NIVELADO INC. IGV y VARIACIÓN % NIVELADA vs. MENOR.
   - Estimados editables (número azul) cuando ningún postor cotiza algo que alguno no incluye (dinteles, columnas, meses de mantenimiento faltantes).
3. **Secciones propias de la partida** (opcionales): FLUJO DE PAGOS POR HITO (% o US$ por hito y "% pagado antes de que el equipo llegue a obra"), COMPARATIVO TÉCNICO (marca, capacidad, velocidad, cabina, tracción, puertas, seguridad), etc.
4. **CRITERIOS COMERCIALES Y TÉCNICOS:** EMPRESA / RUC / CONTACTO · FECHA / N° / VERSIÓN · MODALIDAD / ALCANCE · GG / UTILIDAD / DESCUENTO · todos los criterios de la Hoja 1 · los propios de la partida · CONSIDERACIONES Y EXCLUSIONES (texto completo). Mismo código de color de texto que la Hoja 1; Arial 10, alineado arriba a la izquierda. En OBSERVACIONES de la fila de título: "Color del texto: AZUL negrita = ventaja / cumple · ROJO negrita = desventaja / riesgo de costo · NEGRO negrita = dato faltante o a confirmar · negro normal = informativo".
5. **RECOMENDACIÓN:** rótulo azul marino; texto combinado desde el primer postor hasta OBSERVACIONES, negrita. Formato: "1° POSTOR B (VERDE INTENSO, RECOMENDADO): S/ … sin IGV, x % sobre/bajo …; razones (metrado, garantía, condiciones). Negociar … Confirmar … 2° POSTOR A como alternativa si …".

## LEYENDA Y NOTAS (tercera hoja, corta)

1. **CÓDIGO DE COLORES:** tabla de tres columnas (Formato con la muestra pintada · Dónde se aplica · Qué significa / qué hacer). Una fila por color de la leyenda de arriba, incluidos los colores de texto de criterios.
2. **RESULTADO (vinculado al cuadro desglosado):** Precio ofertado sin IGV, Precio nivelado por alcance sin IGV, Variación % nivelada vs. menor, con fórmulas a la Hoja 2.
3. **CONCLUSIONES DEL INGENIERO DE COSTOS:** 4 a 7 viñetas cortas: quién es el menor y por cuánto, qué cambia al nivelar, hallazgos de P.U. y metrados, inconsistencias, riesgos comerciales, recomendación y pendientes (meta, confirmaciones).

## Hojas de cotización (una por postor)

- Nombre = nombre corto del postor (máx. 31 caracteres). Si se transcribe de PDF: `POSTOR A (transcrito)`.
- **Excel del postor:** copiar la hoja tal cual (valores, formatos, combinaciones, anchos). No modificar sus números.
- **PDF:** transcribir: título con razón social y N° de cotización; datos (RUC, fecha, atención, referencia); tabla Ítem · Descripción · Und · Metrado · P.U. · Parcial · **Control E×F−G** (debe dar 0; si no, es una inconsistencia del postor); SUBTOTAL (suma de partidas), TOTAL DECLARADO, DIFERENCIA; y al final sus consideraciones y condiciones comerciales textuales.
- Si un postor envía varios archivos (resumen, torre, sótano, metrado por niveles), una hoja por archivo con sufijo: `POSTOR C - RESUMEN`, `POSTOR C - TORRE`.
- La Hoja 2 puede vincular Cant. y P.U. a estas hojas: `Cant ='POSTOR B'!E15`, `P.U. =IFERROR('POSTOR B'!G15/Cant,0)` (el P.U. se deriva del parcial para cuadrar con el total del postor). Partidas que el postor separa y la base agrupa: sumar sus filas (`='POSTOR B'!E27+'POSTOR B'!E29`).
