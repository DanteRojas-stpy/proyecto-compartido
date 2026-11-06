# E3 dentro de n8n: el lector sin servicio aparte

Los cinco flujos de E3 corren **solo con nodos de n8n** (sirve n8n Cloud). Ya no necesitan `app/etapa3` ni un servidor propio:
hablan directo con la Function `e3-operar` de Nhost, con Storage, con Nhost Auth y con Claude.

## Cómo está armado

| Flujo | Qué hace | Nodos clave |
|---|---|---|
| E3.1 Recepción | Toma los eventos, reserva la versión, recupera el correo exacto en Gmail, calcula huellas y quita duplicados, comprueba/sube cada original a Storage con su id estable y lo registra | `Un correo por evento` → `Reservar versión por correo` → Gmail → `Preparar documentos` → `Comprobar archivo en Storage` → `Guardar original en Storage` → `Registrar documentos` |
| E3.2 Lectura | Inicia la lectura, descarga cada documento, lo lee según su tipo, guarda los fragmentos, pide a Claude por tandas, valida y guarda el resultado | `Detectar tipo` → `Extraer texto del PDF` / `Descomprimir xlsx` / `Leer CSV` → `Reunir fuentes` → `Armar tandas` → `Claude Messages` → `Validar lectura` → `Guardar resultado` |
| E3.3 Notificaciones | Registra el aviso único (solo en el frontend) | `notificar` |
| E3.4 Decisiones | Verifica la sesión en Nhost Auth y registra la decisión o entrega el original | `Verificar sesión en Nhost` → `Registrar decisión` / `Recuperar documento` |
| E3.5 Recuperación | Reintenta lo estancado y avisa cuando se agotan los intentos; también recibe el reintento del frontend | `recuperar` → `Reintentar E3.1/E3.2` |

El código de los nodos está en `nodos/*.js`; `generar.py` lo une con `lector_core.js` y escribe `e3-1.json` … `e3-5.json`
(`python n8n/etapa3/generar.py`). `lector_core.js` equivale a `app/etapa3` y se comprueba contra Python
(`tests/etapa3/test_lector_n8n.py`, 71 casos).

## Lo que cambia respecto al servicio (decisiones)
- **Sin OCR.** n8n Cloud no puede correr Tesseract. Una página sin texto (escaneada) **no se descarta en silencio**: queda una
  observación de severidad alta que pide revisar el original. Si ninguna página tiene texto, el documento se rechaza con un aviso
  claro. Las imágenes sueltas (`.png`, `.jpg`…) y los `.xls` antiguos no se leen en esta versión.
- **Sin embeddings ni búsqueda semántica (RAG).** Se envían **todos** los fragmentos a Claude, por tandas de 24 000 caracteres
  (la mitad en cada reintento). En fichas técnicas cortas el efecto es pequeño; en documentos largos sube el costo.
- Las fórmulas compartidas de Excel (`<f t="shared" .../>` sin texto) se leen con su resultado guardado pero sin el texto de la fórmula.
- Los webhooks internos `e3-interno-datos` y `e3-interno-lector` desaparecen: nadie más llama al servicio.

## Cómo se probó
`scripts/simulador_e3.py` levanta un PostgreSQL aislado (Docker) con **todas las migraciones del repositorio** —la lógica real de
`e3_operar`— y un servidor HTTP que imita la Function `e3-operar`, Storage, Nhost Auth, Claude (respuesta fija con citas reales) y
un correo con un PDF y un Excel. `scripts/probar_e3_n8n.py` importa copias de los flujos en tu n8n local apuntadas al simulador
(sin credenciales; el nodo de Gmail se sustituye por los adjuntos del simulador) y ejecuta la cadena completa:

```bash
python scripts/simulador_e3.py --puerto 8787
python scripts/probar_e3_n8n.py --solo-importar
docker exec -e N8N_RUNNERS_BROKER_PORT=5680 n8n_local n8n execute --id=pruebaE3sim_1
```

Resultado comprobado: E3.1 → E3.2 → E3.3 deja la versión en `completado_con_observaciones` con sus fragmentos, partidas y evidencias;
E3.4 acepta la versión, entrega el original y rechaza sesión inválida y origen no autorizado; E3.5 reencola una lectura pendiente.
Los flujos **no se probaron con tu Nhost, Gmail ni la API de Claude reales**: falta esa prueba con credenciales.

`tests/etapa3/test_flujos_n8n.py` revisa sin Docker que los JSON coincidan con el generador, que ningún nodo llame a un servicio propio,
que las conexiones y las entradas de los `Merge` sean válidas, que el código de cada nodo cite solo nodos que existen y sea JavaScript válido.
