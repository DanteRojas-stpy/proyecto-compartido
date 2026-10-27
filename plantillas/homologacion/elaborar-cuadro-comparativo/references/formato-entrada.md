# Alcance: JSON del generador histórico de referencia

Este formato corresponde al generador incluido para ensayos y adaptación.
No es la salida directa de E3 ni un sustituto de los datos homologados.
Una conversión de formato no autoriza decidir correspondencias técnicas.
Los estados, criterios, escenarios y recomendaciones se reciben ya definidos.
Los totales declarados usados aquí deben estar en la moneda de comparación;
sus originales, autorizaciones y pendientes se conservan por separado.

# Formato de entrada del script (`entrada.json`)

`scripts/generar_cuadro_referencia.py` construye el Excel completo a partir de un JSON. Este JSON es también el **contrato** para automatizar (n8n u otro): el paso de extracción produce este JSON y el script produce el Excel.

Ejemplos completos y ficticios: `assets/ejemplo_gas.json` (soles, precio global, descuento, partida solo de un postor, partida omitida) y `assets/ejemplo_ascensores.json` (US$ con tipo de cambio, criterios propios, flujo de pagos, comparativo técnico).

## Raíz

| Clave | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `proyecto.codigo` | texto | sí | Código corto del proyecto para archivo y hojas (`PROYX`). |
| `proyecto.obra` | texto | sí | Fila 2: `OBRA: <NOMBRE>`. |
| `proyecto.fecha` | `AAAA-MM-DD` | no | Fecha del cuadro (por defecto hoy). Define el prefijo AAMMDD. |
| `proyecto.revision` | entero | no | 0 → `Rev.00`. |
| `especialidad.codigo` | texto | sí | `IISS`, `IIEE`, `GAS`, `ASCENSORES`, … |
| `especialidad.nombre` | texto | sí | Para el archivo: `Inst. Sanitarias`. |
| `especialidad.titulo` | texto | sí | Fila 3: `COMPARATIVO - …`. |
| `especialidad.titulo_total` | texto | no | Texto de la fila 9 (total). |
| `moneda` | texto | no | `S/` (por defecto). |
| `tipo_cambio` | número | no | Si existe, los postores pueden cotizar `pu_usd` y se agrega TC en F5. |
| `igv` | número | no | 0.18. |
| `umbral_alto_impacto` | número | no | 10000 (en soles). |
| `base_homologacion` | id | no | Postor base (por defecto el primero). |
| `ratios` | lista | no | `{"nombre": "COSTO POR DEPARTAMENTO (S/, SIN IGV)", "divisor": 120, "obs": "…"}` → Hoja 1 y Hoja 2. |
| `ratios_extra` | lista | no | Filas de ratios con valores por postor: `{"nombre", "valores": {"A": "=…" o número}, "formato", "obs"}` (solo Hoja 2). |
| `criterios_hoja1` | lista | no | Rótulos y orden de criterios en la Hoja 1 (reemplaza la lista base). |
| `criterios_extra` | lista | no | Se agregan a la lista base si no se da `criterios_hoja1`. |
| `criterios_hoja2_extra` | lista | no | Criterios adicionales solo en la Hoja 2. |
| `postores` | lista | sí | Ver abajo. El orden es el orden de los bloques. |
| `partidas` | lista | sí | Árbol de capítulos e ítems. |
| `secciones_extra` | lista | no | `{"titulo", "texto": bool, "filas": [{"concepto", "valores": {id: valor}, "formato", "obs", "tonos": {id: tono}}]}` |
| `conclusiones` | lista de textos | no | Viñetas de LEYENDA Y NOTAS. |
| `recomendacion` | texto | no | Bloque final de la Hoja 2. |

## Postor

| Clave | Descripción |
|---|---|
| `id` | Identificador corto (`A`, `B`, `C`). Se usa en `precios`. |
| `corto` | Nombre corto para textos y hoja de cotización (`Postor A`). |
| `nombre` | Encabezado del bloque (razón social en mayúsculas). |
| `estado` | `recomendado`, `mejor`, `negociacion`, `caro`, `anterior`, `normal` → color del encabezado en Hoja 2. |
| `ruc`, `contacto`, `referencia_cotizacion` | Texto o `null` (se marca como faltante). `contacto` con saltos `\n`: "Empresa: …\nContacto: …\nCorreo: …". |
| `gg`, `utilidad` | Tasas que el postor suma aparte (0.10). 0 si están incluidas. |
| `descuento` | Tasa (0.05). Si la clave existe (aunque sea 0) se muestran las columnas INC DSCTO. |
| `total_declarado_sin_igv` | Total de su cotización sin IGV (después de descuento). Lo usa el validador. |
| `ajuste_declarado` | Diferencia a sumar cuando su detalle no suma el total declarado. |
| `modalidad` | `{"texto", "tono"}` para MODALIDAD / ALCANCE. |
| `criterios` | `{"<RÓTULO>": {"texto": "…", "tono": "ventaja|riesgo|faltante|info"}}`. Rótulos iguales a los de la lista de criterios. |
| `consideraciones` | Lista de frases (viñetas). |
| `cotizacion` | Hoja de cotización: transcrita (`titulo`, `encabezado` {clave: valor}, `filas` [{item, desc, und, cant, pu, parcial?}], `notas`) o copiada (`archivo_excel`, `hoja_origen`, `mapa` {col_item, col_cant, col_parcial}). Una fila sin `cant` ni `parcial` es título. |

## Partidas (árbol)

Capítulo:

```json
{"titulo": "INSTALACION DE LAS REDES INTERNAS", "und": "dpto",
 "meta": {"metrado": 120, "pu": 850},
 "bloques": {"A": {"cant": 120, "pu": 900, "texto": "Precio global por dpto…", "comentario": "120 × S/ 900.00"},
             "C": {"texto": "No especifica válvulas (verificar alcance)."}},
 "hijos": [ …capítulos… ]  ó  "items": [ …ítems… ]}
```

- `bloques.<id>` con `cant` y `pu` (o `pu_usd`) = **precio global** del postor para el capítulo. Solo `texto` = nota combinada sobre las filas (sin precio).
- `meta` en el capítulo: meta global del capítulo (`F = E*D`).

Ítem:

```json
{"desc": "Tubería PE-AL-PE 2025 empotrada en losa y muro", "und": "m",
 "meta": {"metrado": 2000, "pu": 19},
 "clase": "alerta",
 "obs": "Texto adicional para OBSERVACIONES.",
 "precios": {
   "B": {"cant": 2000, "pu": 20, "ref": "2.01"},
   "C": {"cant": 2300, "pu": 24, "ref": "02.01", "observado": true, "nota": "Metrado 15% mayor."},
   "D": {"incluido": "Incluido en su partida de salidas"},
   "E": {"cant": 2000, "pu": "=50900/2000", "excluir_subtotal": true}
 }}
```

| Clave de precio | Efecto |
|---|---|
| `cant`, `pu` | Valores escritos en Hoja 1; `pu` puede ser fórmula aritmética simple (`"=50900/2000"`). |
| `pu_usd` | En lugar de `pu` cuando hay `tipo_cambio`. |
| `ref` | Ítem (o lista de ítems) de su hoja de cotización: la Hoja 2 vincula Cant. y P.U. a esa hoja. |
| `observado` | Cant./P.U./parcial en rojo negrita en la Hoja 1. |
| `nota` | Comentario corto en el P.U. de la Hoja 1. |
| `incluido` | Texto en la celda Cant. (Hoja 1) e "INCL." en Hoja 2 ("INCL.?" amarillo si el texto lleva "?"). No se nivela. |
| `excluir_subtotal` | La línea se muestra pero no se suma en el subtotal del capítulo de ese postor (replica su suma). |

`clase` (opcional; si no se da se calcula): `normal`, `omitida`, `solo_uno`, `varios_fuera_base`, `alto_impacto`, `alerta`, `referencial`.

## Salida

- Archivo `AAMMDD_<codigo>_CC_<nombre>_RevNN.xlsx` en la carpeta indicada.
- En consola: subtotal sin IGV por postor y si cuadra con `total_declarado_sin_igv`.
- Luego correr `scripts/validar_cuadro_referencia.py` (recalcula con LibreOffice).
