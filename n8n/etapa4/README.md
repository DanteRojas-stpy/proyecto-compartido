# Flujo de E4: homologación de cotizaciones finales

`e4-1.json` se genera con `python n8n/etapa4/generar.py` y no contiene claves ni credenciales.
Antes de activarlo, completa estos pasos en orden.

## Qué hace
Cada minuto revisa la cola. Cuando el especialista pulsa «Homologar» (parte 4 del plan), el flujo:

1. toma la solicitud pendiente (`tomar_e4`) y pide su entrada a Nhost (`entrada_e4`): solo las versiones
   que el especialista aceptó como final, el itemizado y los proveedores. No lee PDF ni Excel;
2. un nodo de código prepara la petición con el método de homologación y las versiones finales (**sin servicio aparte**);
3. Claude (Sonnet 5.5 por defecto) relaciona partidas y equivalencias, sin escribir importes;
4. otro nodo de código valida la respuesta contra la entrada y construye `homologacion.json`: si cita algo que no existe, se rechaza;
5. se guarda en Nhost (`guardar_e4`) y se avisa al especialista. Cualquier fallo llama a `fallo_e4`: reintenta
   hasta tres veces y después cierra con un aviso de error.

## Dónde está el código
- `homologacion_core.js`: equivalente exacto de `app/homologacion` (entrada, lectura de la respuesta y construcción), en JavaScript
  puro, sin librerías externas, para que sirva en n8n Cloud. `app/homologacion` queda como referencia y `tests/etapa4` comprueba
  con Node que dan **el mismo resultado** (incluida la huella SHA-256 y los mensajes de rechazo).
- `preparar_peticion.js` y `construir_validar.js`: el pegamento de cada nodo. `generar.py` los une con el núcleo y les inserta el
  método (`app/homologacion/skill`) y el esquema de respuesta. **El modelo se cambia en la constante `MODELO` de `generar.py`.**

## Preparación
1. En Nhost: ejecuta `db/etapa4/017_homologacion_cuadro.sql`, publica las tablas con
   `python scripts/configurar_etapa4_nhost.py` y redespliega las Functions (`functions/e4-operar.ts`).
2. No hace falta levantar ningún servicio para E4.
3. En n8n importa `e4-1.json`, reemplaza `SUBDOMINIO` y `REGION` y asigna en los nodos con aviso
   `CREDENCIAL_E4:internal` la credencial `CostFlow E3 - Acceso interno`, y en `CREDENCIAL_E4:claude` la de
   `CostFlow E3 - Claude` (Header Auth con `x-api-key`).
4. Publica el flujo solo cuando la 017 esté aplicada: si no, cada minuto fallaría contra la base.
