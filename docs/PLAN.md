# Plan: plataforma de cotizaciones para obra

## 1. Qué problema resolvemos

El especialista de costos recibe cotizaciones de varios proveedores para cada
partida. Llegan en formatos distintos (PDF, Excel, Word, fotos), con unidades,
monedas e IGV distintos. Pasarlas a mano a la matriz comparativa toma horas y
genera errores.

**La plataforma recibe las cotizaciones, las lee, las homologa y llena la
matriz comparativa con el formato de la empresa.**

## 2. Alcance del desarrollo

| # | Proceso | En la app |
|---|---------|-----------|
| 1 | Asignación de valores de entrada | **Entrada (input)** |
| 2 | Búsqueda de proveedores | Fuera del alcance |
| 3 | Contacto con proveedores | Fuera del alcance |
| 4 | Recepción de cotizaciones | **Se desarrolla** |
| 5 | Lectura automática de documentos | **Se desarrolla** |
| 6 | Homologación de propuestas | **Se desarrolla** |
| 7 | Detección de información faltante | Fuera del alcance |
| 8 | Solicitud de aclaraciones | Fuera del alcance |
| 9 | Generación del cuadro comparativo | **Se desarrolla** |
| 10 | Revisión del especialista de costos | Fuera del alcance |
| 11 | Decisión final | Fuera del alcance |

**El desarrollo se concentra en 1 → 4 → 5 → 6 → 9.** Los procesos 2, 3, 7, 8, 10
y 11 no se programan: los hace el equipo de costos fuera de la plataforma.
No agregues funciones para ellos sin acordarlo antes.

## 3. Proceso 1: entrada (lo que carga el usuario)

| Entrada | Qué contiene | Formato |
|---------|--------------|---------|
| **Itemizado de partidas** | Código, descripción, unidad, metrado referencial y especificaciones de cada partida | Excel |
| **Matriz de procura** | Qué partidas se compran, en qué paquete de compra y a qué proveedores se pide cotización | Excel |
| **Proveedores para la cotización** | Razón social, RUC, contacto y partidas que cotiza cada uno | Excel (puede ir dentro de la matriz de procura) |
| **Plantilla de la matriz comparativa** | El formato Excel de la empresa donde se arma el comparativo | Excel (.xlsx) |

La plataforma **no inventa** proveedores ni partidas: trabaja solo con lo que
viene en estas entradas.

## 4. Procesos que se desarrollan

### 4. Recepción de cotizaciones
- El usuario sube los archivos (PDF, Excel, Word, imagen).
- Cada archivo se asigna a un **proveedor** y a un **paquete/partidas** de la
  matriz de procura (la plataforma lo propone, el usuario confirma).
- Se guarda el archivo original sin modificarlo.
- Más adelante: recepción desde un buzón de correo.

### 5. Lectura automática de documentos
- La IA extrae de cada cotización: ítems, descripción, unidad, cantidad,
  precio unitario, parcial, moneda, IGV incluido o no, flete, plazo de entrega,
  validez de la oferta, forma de pago, garantía.
- Cada dato guarda **de dónde salió** (archivo y página) para poder revisarlo.
- Si un dato no está en la cotización, queda vacío; no se rellena ni se adivina.

### 6. Homologación de propuestas
- Relaciona cada ítem cotizado con su partida del itemizado.
- Iguala **unidades** (tabla de conversiones editable), **moneda** (tipo de
  cambio que define el usuario) e **IGV** (18 %).
- Calcula el total de cada proveedor sobre el **metrado referencial** del
  itemizado, para comparar en igualdad de condiciones.

### 9. Generación del cuadro comparativo
- Llena la **plantilla de matriz comparativa del usuario** (no una nuestra).
- Un proveedor por columna y una partida por fila, con precios homologados,
  condiciones comerciales y totales.
- Resalta el menor precio por partida y muestra las diferencias en %.
- Entrega el Excel para descargar.

## 5. Flujo de datos

```
Entradas (1)                          Cotizaciones de proveedores
  itemizado ─┐                                   │
  matriz de procura ─┤                          (4) Recepción
  proveedores ─┤                                 │
  plantilla ──┐│                                (5) Lectura
              ││                                 │
              │└────────────────────────────→  (6) Homologación
              │                                  │
              └──────────────────────────────→  (9) Matriz comparativa (Excel)
```

## 6. Tecnología

| Pieza | Herramienta |
|-------|-------------|
| Lenguaje | Python 3.12 |
| Pantallas | Streamlit |
| Lectura de documentos | API de Claude (PDF, imágenes, texto) |
| Leer y llenar Excel | openpyxl |
| Formato común de datos | pydantic (`app/modelo.py`) |
| Datos | SQLite al inicio → Supabase al crecer |

## 7. Fases

### Fase 0 — Preparación (1 semana)
- Reunir un caso real completo (datos sensibles borrados): itemizado, matriz
  de procura, lista de proveedores, plantilla de matriz comparativa y
  10–20 cotizaciones.
- Llenar a mano la matriz comparativa correcta de ese caso: sirve para medir
  si la plataforma acierta.
- Guardarlo en `ejemplos/` y la plantilla en `plantillas/`.

### Fase 1 — MVP (3–4 semanas)
- Cargar las 4 entradas del proceso 1.
- Subir cotizaciones y asignarlas a proveedor y paquete (proceso 4).
- Lectura automática con tabla para corregir (proceso 5).
- Homologación (proceso 6).
- Matriz comparativa en la plantilla del usuario (proceso 9).
- **Meta:** ≥ 90 % de datos correctos en el caso de prueba y la matriz lista
  en < 30 min.

### Fase 2 — Uso real
- Varios proyectos y paquetes a la vez.
- Historial de precios por partida.
- Login de usuarios y piloto con 1–2 constructoras.
- Recepción desde correo.

### Fase 3 — Startup
- Varias empresas con datos separados, plan de pago, confidencialidad.

## 8. División del trabajo (en paralelo)

Primero se acuerda el formato común de datos en `app/modelo.py`. Después:

| Módulo | Carpeta | Proceso |
|--------|---------|---------|
| Entradas | `app/entradas/` | 1: leer itemizado, matriz de procura, proveedores y plantilla |
| Recepción | `app/recepcion/` | 4: subir y asignar cotizaciones |
| Lectura | `app/lectura/` | 5: extraer datos con IA |
| Homologación | `app/homologacion/` | 6: igualar unidades, moneda, IGV, metrado |
| Matriz comparativa | `app/comparativo/` | 9: llenar la plantilla Excel |
| Pantallas | `app/pantallas/` | Interfaz Streamlit |

Cada persona toma un módulo, trabaja en su rama y entrega por Pull Request.
Dos personas no trabajan en el mismo módulo al mismo tiempo.

## 9. Riesgos

| Riesgo | Cómo lo manejamos |
|--------|-------------------|
| La IA lee mal un precio | Tabla de corrección y referencia a la página de origen |
| Fotos o escaneos borrosos | Marcar "baja confianza" |
| Unidades raras (bolsas, viajes, glb) | Tabla de conversiones editable |
| Cada empresa usa otra plantilla | Se llena la plantilla del usuario, con un mapeo de celdas configurable |
| Confidencialidad de precios | No subir datos reales sin borrar nombres, RUC y contactos |

## 10. Próximos pasos

1. Reunir el caso real de la Fase 0.
2. Definir `app/modelo.py` (formato común de datos).
3. Repartir los módulos de la sección 8.
