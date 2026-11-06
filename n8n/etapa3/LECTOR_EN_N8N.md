# E3 dentro de n8n (en construcción): el lector sin servicio aparte

Objetivo: que el lector de cotizaciones corra **solo con nodos de n8n**, para poder usar n8n Cloud sin alojar `app/etapa3`.
Hoy esto es la **primera etapa**: el núcleo del lector en JavaScript, ya comprobado contra Python. Los flujos E3.1 a E3.5 todavía
llaman al servicio; reescribirlos es la segunda etapa (ver abajo).

## Qué hay (etapa 1)
`lector_core.js` es JavaScript puro, sin librerías externas (sirve en un nodo de código de n8n Cloud). Equivale a `app/etapa3`:

| Pieza | Equivalente en Python | Comprobación |
|---|---|---|
| Huellas SHA-256 y SHA-1, UUID estables (`uuid5`) y JSON al estilo de Python | `documents.stable_id`, `json.dumps` | Mismos identificadores que Python |
| Fragmentos de texto (400 caracteres, solape de 60) | `documents._fragment` | Igual que Python |
| Lectura de Excel `.xlsx` (valores, fórmulas, resultado guardado, formatos, fechas, hojas ocultas) y CSV | `documents.extract` | Igual que Python sobre libros de prueba |
| Tandas de contexto | `rag.context_batches` | Igual que Python |
| Validación independiente: cada cita debe existir literalmente en su fragmento, los importes coinciden con su texto original, la aritmética se verifica sin rellenar | `contract.combine`, `number`, `detect_*` | 18 casos (9 de rechazo) y 36 de cifras/detección, iguales a Python |
| Petición a Claude y lectura de su respuesta | `contract.request` / `parse_response` + la traducción de n8n | Pruebas propias |
| PDF: texto por página que entrega el nodo «Extract From File» | (allí: PyMuPDF + OCR) | Pruebas propias |

## Lo que cambia respecto al servicio (decisiones)
- **Sin OCR.** n8n Cloud no puede correr Tesseract. Una página sin texto (escaneada) **no se descarta en silencio**: queda una
  observación de severidad alta que pide revisar el original. Si ninguna página tiene texto, el documento se rechaza con un aviso
  claro. Las imágenes sueltas (`.png`, `.jpg`…) y los `.xls` antiguos no se leen en esta versión.
- **Sin embeddings ni búsqueda semántica (RAG).** Se envían **todos** los fragmentos a Claude, por tandas de 24 000 caracteres.
  Es lo que el servicio ya hacía con los Excel; en fichas técnicas cortas el efecto es pequeño, y en documentos largos sube el costo.
- Las fórmulas compartidas de Excel (`<f t="shared" .../>` sin texto) se leen con su resultado guardado pero sin el texto de la fórmula.

## Etapa 2 (pendiente): reescribir los flujos
Sustituir cada llamada al servicio por nodos de n8n que usen este núcleo y hablen directo con la Function `e3-operar` y Storage:

| Hoy (servicio) | Después (n8n) |
|---|---|
| `/receive` | Gmail → código (huella, deduplicación) → Storage (subida con el id estable) → `registrar_documentos` |
| `/read` | `iniciar_lectura` → `version` → `configuracion` → descargar documentos → leer (PDF con «Extract From File», Excel con «Compression» + código, CSV) → `guardar_fuentes` → Claude por tandas → `combine` → `guardar_resultado` / `fallo` |
| `/notify`, `/recover` | Function `notificar` / `recuperar` |
| `/action` | Verificar la sesión con Nhost Auth → `decision` o descarga del documento |

Para probarlos sin tocar tu Nhost real conviene un Nhost de pruebas (o un simulador de la Function `e3-operar`): la lectura cambia
estados de versiones.
