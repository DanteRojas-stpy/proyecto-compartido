# Flujo de E5: cuadro comparativo

`e5-1.json` se genera con `python n8n/etapa5/generar.py` y no contiene claves ni credenciales.

## Qué hace
Cada minuto revisa la cola. Cuando el especialista pulsa «Generar cuadro», el flujo:

1. toma el cuadro pendiente (`tomar_e5`) y pide su entrada a Nhost (`entrada_e5`): la última homologación (E4),
   el tipo de cambio que el especialista autorizó (si lo indicó) y la plantilla cargada en la solicitud;
2. descarga la plantilla desde Storage y la envía con la homologación al servicio `costflow-cuadro` (`/e5/generar`);
3. el servicio **no usa modelo**: escribe en una copia de la plantilla los datos de E4 (que son los de E3), conserva
   fórmulas, formatos y comentarios, y pide a Excel que recalcule al abrir;
4. sube el `.xlsx` a Storage y lo registra en Nhost (`guardar_e5`) como `validado` o `borrador`, con la validación.
   Un fallo llama a `fallo_e5`: reintenta hasta tres veces; un cuadro imposible de armar (por ejemplo, varias
   partidas) cierra de inmediato con un aviso.

## Límites de esta versión
- La plantilla tiene una sola fila de partida: si la homologación trae varias, el cuadro se rechaza con un mensaje claro.
- Las columnas en S/ de ofertas en dólares dependen del tipo de cambio que indique el especialista; sin él quedan vacías
  y el cuadro sale como borrador. Nunca se inventa.
- Es «validado» solo si la homologación no tiene pendientes que bloqueen y todas las comprobaciones cuadran.

## Preparación
1. En Nhost: ejecuta `db/etapa4/018_tipo_cambio_cuadro.sql` (requiere la 017). La Function `e4-operar` no cambia.
2. Levanta el servicio: `docker compose -f compose.etapa5.yml up -d --build` (red `costflow_e3`, clave `E3_INTERNAL_KEY`).
3. En n8n importa `e5-1.json`, reemplaza `SUBDOMINIO` y `REGION` y asigna `CREDENCIAL_E4:internal` →
   `CostFlow E3 - Acceso interno` y `CREDENCIAL_E4:storage` → `CostFlow E3 - Nhost Storage`.
4. Publica el flujo solo cuando la 018 esté aplicada.
