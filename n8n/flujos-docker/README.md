# Flujos de n8n (Docker) de E3, E4 y E5

Exportación de los siete flujos que corrían en el n8n local, con la nomenclatura `CostFlow - E<etapa>.<número> <nombre>`.

| Archivo | Etapa |
|---|---|
| `CostFlow - E3.1 Recepción de correos confirmados.json` | E3 · lectura de cotizaciones |
| `CostFlow - E3.2 Lectura OCR RAG y validación.json` | E3 |
| `CostFlow - E3.3 Notificaciones solo en frontend.json` | E3 |
| `CostFlow - E3.4 Decisiones autenticadas del especialista.json` | E3 |
| `CostFlow - E3.5 Recuperación y servicios internos.json` | E3 |
| `CostFlow - E4.1 Homologación de cotizaciones finales.json` | E4 · homologación |
| `CostFlow - E5.1 Cuadro comparativo.json` | E5 · cuadro comparativo |

## Nomenclatura
`E1` = datos de entrada (registro y envío de solicitudes) · `E2` = seguimiento de proveedores · `E3` = lectura de
cotizaciones · `E4` = homologación · `E5` = cuadro comparativo. Cada flujo lleva el número de su etapa y un orden dentro
de ella (`E3.1`, `E3.2`, …).

## Qué se cambió respecto a la exportación
- Se quitaron las referencias a credenciales y los identificadores de la instancia (`instanceId`, `versionId`).
  Las marcas `CREDENCIAL_E3:*` / `CREDENCIAL_E4:*` de cada nodo se conservan para saber qué credencial asignar.
- Los flujos quedan inactivos (`active: false`).
- `E3.3` venía como «… copy» con otro identificador; se le quitó « copy» y se le puso `costflowEtapa3_3`, el
  identificador con el que lo invocan E3.1, E3.2 y E3.5.

## Importante
- `E4.1` y `E5.1` de esta carpeta son la versión del n8n local: **no** tienen el nodo «Aviso del botón» que sí traen
  `n8n/etapa4/e4-1.json` y `n8n/etapa5/e5-1.json` (más recientes). Para producción o la nube usa esos.
- Las direcciones de los servicios siguen siendo las del Docker local (`http://costflow-etapa3:8093`, etc.). Para n8n
  Cloud, ver `docs/NUBE_N8N.md` y `scripts/n8n_nube.py`.
