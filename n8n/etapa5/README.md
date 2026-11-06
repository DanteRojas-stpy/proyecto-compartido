# Flujo de E5: cuadro comparativo

`e5-1.json` se genera con `python n8n/etapa5/generar.py` y no contiene claves ni credenciales.

## Qué hace
Cada minuto revisa la cola. Cuando el especialista pulsa «Generar cuadro», el flujo:

1. toma el cuadro pendiente (`tomar_e5`) y pide su entrada a Nhost (`entrada_e5`): la última homologación (E4),
   el tipo de cambio que el especialista autorizó (si lo indicó) y la plantilla cargada en la solicitud;
2. descarga la plantilla desde Storage y la abre dentro de n8n: un nodo marca el `.xlsx` como zip, el nodo
   «Compression» lo descomprime y, como ese nodo entrega los archivos sin su carpeta, el nodo de código las
   recupera de la lista de rutas del zip original;
3. un nodo de código (**sin modelo y sin servicios aparte**) escribe los datos de E4 (que son los de E3) en las celdas de la
   hoja, conserva fórmulas, formatos y comentarios, y pide a Excel que recalcule al abrir. Luego el nodo «Compression»
   vuelve a empaquetar el `.xlsx`;
4. sube el `.xlsx` a Storage y lo registra en Nhost (`guardar_e5`) como `validado` o `borrador`, con la validación.
   Un fallo llama a `fallo_e5`: reintenta hasta tres veces; un cuadro imposible de armar (por ejemplo, varias
   partidas) cierra de inmediato con un aviso.

## Dónde está el código
- `cuadro_core.js`: decide qué va en cada celda y escribe el XML de la hoja. Es el equivalente exacto de `app/cuadro/llenar.py`
  (que queda como referencia). `tests/etapa5` comprueba con Node que dan **el mismo resultado**, byte a byte en el XML.
- `llenar_plantilla.js`: el pegamento del nodo «Llenar plantilla» (rutas del zip, escritura de archivos, error no reintentable).
- `marcar_zip.js`: etiqueta el `.xlsx` como zip para poder abrirlo.
- Los tres se insertan tal cual en los nodos al correr `generar.py`. No hay librerías externas, así que sirve en n8n Cloud.

## Límites de esta versión
- La plantilla tiene una fila de partida y 7 bloques de proveedor. Un proveedor que cotiza varios tipos (partidas de E4)
  ocupa un bloque por tipo: «PROVEEDOR (TIPO 1)», «PROVEEDOR (TIPO 2)». Si se necesitan más de 7 bloques, el cuadro se rechaza.
- Un bloque sin moneda identificada o sin importes en E3 queda sin precios y el cuadro sale como borrador; no se inventan.
- Las columnas en S/ de ofertas en dólares dependen del tipo de cambio que indique el especialista; sin él quedan vacías
  y el cuadro sale como borrador. Nunca se inventa.
- Es «validado» solo si la homologación no tiene pendientes que bloqueen y todas las comprobaciones cuadran.

## Preparación
1. En Nhost: ejecuta `db/etapa4/018_tipo_cambio_cuadro.sql` y `019_motivo_error_cuadro.sql` (requieren la 017). La Function `e4-operar` no cambia.
2. No hace falta levantar ningún servicio para E5.
3. En n8n importa `e5-1.json`, reemplaza `SUBDOMINIO` y `REGION` y asigna `CREDENCIAL_E4:internal` →
   `CostFlow E3 - Acceso interno` y `CREDENCIAL_E4:storage` → `CostFlow E3 - Nhost Storage`.
4. Publica el flujo solo cuando la 018 esté aplicada.
