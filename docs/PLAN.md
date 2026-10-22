# Plan: plataforma de cotizaciones para obra

## 1. Qué problema resolvemos

El especialista de costos recibe cotizaciones de varios proveedores para una
partida. Llegan en formatos distintos (PDF, Excel, Word, fotos), con unidades,
monedas e IGV distintos. Pasarlas a mano a un cuadro comparativo toma horas y
genera errores.

**La plataforma lee las cotizaciones, las ordena en una plantilla única y arma
el cuadro comparativo.** El especialista sigue decidiendo.

## 2. Qué hace la plataforma y qué hace el especialista

| # | Paso | Quién |
|---|------|-------|
| 1 | Ingresar partida a cotizar y metrado referencial | Especialista (en la plataforma) |
| 2 | Buscar proveedores (base de proveedores) | Especialista |
| 3 | Contactar proveedores | Especialista |
| 4 | Recibir cotizaciones | **Plataforma** |
| 5 | Leer automáticamente los documentos | **Plataforma** |
| 6 | Homologar propuestas en la plantilla Excel | **Plataforma** |
| 7 | Detectar información faltante | Especialista (la plataforma marca celdas vacías) |
| 8 | Pedir aclaraciones al proveedor | Especialista |
| 9 | Generar el cuadro comparativo | **Plataforma** |
| 10 | Revisar | Especialista de costos |
| 11 | Decisión final | Especialista / gerencia |

La plataforma automatiza el tramo **4 → 5 → 6 → 9**. Lo demás queda en manos del
especialista, con ayudas simples (por ejemplo, guardar su lista de proveedores).

## 3. Cómo funciona (vista del usuario)

1. Crea una **solicitud**: partida (ej. "Concreto f'c=210 kg/cm²"), unidad (m³),
   metrado referencial (ej. 350 m³), moneda de comparación.
2. **Sube las cotizaciones** que recibió (arrastrar y soltar PDF, Excel, Word o foto).
3. La plataforma **lee cada documento** y extrae: proveedor, RUC, ítems,
   unidad, cantidad, precio unitario, moneda, IGV incluido o no, flete,
   plazo de entrega, validez de la oferta, forma de pago, garantía.
4. Muestra una **tabla de revisión**: cada dato con el lugar del documento de
   donde salió. Las celdas vacías o dudosas salen en amarillo. El especialista
   corrige lo que haga falta.
5. **Homologa**: convierte todo a la misma unidad, moneda (tipo de cambio que
   indique el especialista), con o sin IGV (18 %), y calcula el total sobre el
   **metrado referencial**, para comparar en igualdad de condiciones.
6. Descarga el **Excel**: hoja de propuestas homologadas y hoja de cuadro
   comparativo (mejor precio resaltado, diferencias en %, observaciones).

## 4. Tecnología (simple al inicio)

| Pieza | Herramienta | Por qué |
|-------|-------------|---------|
| Lenguaje | Python | Fácil de leer, muy bueno con Excel y datos |
| Pantallas (MVP) | Streamlit | Una web funcional sin saber diseño web |
| Lectura de documentos | API de Claude (lee PDF e imágenes y devuelve datos ordenados) | Entiende cotizaciones en cualquier formato |
| Excel | openpyxl, sobre **nuestra plantilla** | Respeta el formato que usan las constructoras |
| Datos | SQLite al inicio → Supabase (base de datos + login + archivos) al crecer | Gratis para empezar |
| Publicación | Streamlit Community Cloud o Railway | Sin servidores propios |

Más adelante, cuando haya clientes, se puede rehacer la interfaz en una web
más profesional. El "motor" (lectura + homologación) se reutiliza.

## 5. Fases

### Fase 0 — Preparación (1 semana)
- Diseñar la **plantilla Excel** del cuadro comparativo (la que usarían en obra).
- Juntar **20–30 cotizaciones reales**, con datos sensibles borrados, de 3–4
  partidas (concreto, acero, agregados, encofrado). Son el material de prueba.
- Para cada una, llenar a mano el resultado correcto: sirve para medir si la
  plataforma acierta.

### Fase 1 — MVP (3–4 semanas)
- Crear solicitud (partida + metrado).
- Subir cotizaciones → lectura automática → tabla de revisión editable.
- Homologación (unidad, moneda, IGV, metrado referencial).
- Descargar Excel con propuestas homologadas y cuadro comparativo.
- **Meta:** acertar ≥ 90 % de los datos en las cotizaciones de prueba, y armar un
  cuadro en < 30 min (hoy toma varias horas).

### Fase 2 — Uso real (4 semanas)
- Varias partidas por solicitud y varios proyectos.
- **Base de proveedores** del especialista (registro manual: rubro, contacto,
  historial).
- Historial de precios por partida (sirve para detectar precios fuera de rango).
- Login de usuarios.
- **Piloto** con 1–2 constructoras conocidas.

### Fase 3 — Ayudas al especialista
- Recepción por **correo**: un buzón donde se reenvían cotizaciones y entran solas.
- Botón "redactar aclaración": la plataforma propone el correo con lo que falta;
  el especialista lo revisa y lo envía él.
- Lista de proveedores sugeridos según la partida (decide el especialista).

### Fase 4 — Startup
- Varias empresas en la misma plataforma, cada una con sus datos separados.
- Plan de pago (por usuario o por cuadro generado).
- Seguridad y confidencialidad de precios (clave para que las constructoras confíen).

## 6. Cómo nos dividimos el trabajo (en paralelo)

Primero acordamos **el formato de los datos** que pasa de una parte a la otra
(archivo `app/modelo.py`). Después cada uno trabaja en su parte sin chocar:

| Dante (Claude Code) | Compañero (Codex) |
|---------------------|-------------------|
| `app/lectura/` — leer documentos y extraer datos | `app/homologacion/` — convertir unidades, moneda, IGV, metrado |
| Pruebas con las cotizaciones de ejemplo | `app/excel/` — llenar la plantilla y el cuadro comparativo |
| `app/pantallas/` — interfaz Streamlit (después) | Plantilla Excel en `plantillas/` |

Cada parte va en su propia rama y entra a `main` por Pull Request.

## 7. Estructura del repositorio

```
proyecto-compartido/
├── docs/PLAN.md            ← este documento
├── plantillas/             ← plantilla Excel del cuadro comparativo
├── ejemplos/               ← cotizaciones de prueba (sin datos sensibles)
└── app/
    ├── modelo.py           ← formato común de los datos
    ├── lectura/            ← lee PDF/Excel/Word/fotos
    ├── homologacion/       ← iguala unidades, moneda, IGV, metrado
    ├── excel/              ← genera el Excel final
    └── pantallas/          ← interfaz web (Streamlit)
```

## 8. Riesgos y cómo cuidarlos

| Riesgo | Cómo lo manejamos |
|--------|-------------------|
| La IA lee mal un precio | Siempre hay revisión humana y se muestra de dónde salió cada dato |
| Cotizaciones escaneadas o fotos borrosas | Marcar "baja confianza" y pedir revisión |
| Unidades raras (bolsas, viajes, glb) | Tabla de conversiones editable por el especialista |
| Confidencialidad de precios | Datos separados por empresa; no usar cotizaciones reales sin permiso |
| Costo de la IA | Céntimos por cotización; se mide desde la Fase 1 |

## 9. Próximos pasos inmediatos

1. Invitar al compañero al repositorio.
2. Diseñar juntos la plantilla Excel del cuadro comparativo (Fase 0).
3. Reunir las primeras 10 cotizaciones de ejemplo.
4. Crear `app/modelo.py` con el formato común de datos.
5. Cada uno empieza su parte (sección 6).
