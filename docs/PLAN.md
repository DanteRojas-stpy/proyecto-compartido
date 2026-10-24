# Plan: CostFlow, agente de IA para cotizaciones de obra

Contexto completo y reglas del MVP: [CONTEXTO_COSTFLOW.md](CONTEXTO_COSTFLOW.md).
Este documento resume el plan de desarrollo.

## 1. Qué problema resolvemos

El especialista de costos pide cotizaciones a varios proveedores para cada
partida, las sigue por correo y las compara a mano. Las respuestas llegan en
formatos distintos (PDF, Excel, Word, fotos), con unidades, monedas e IGV
distintos. Armar la matriz comparativa toma horas y genera errores.

**CostFlow automatiza el trabajo repetitivo** (enviar, seguir, leer, homologar
y comparar) y **deja al especialista las decisiones técnicas**.

## 2. Alcance del MVP

| # | Proceso | Quién | En la app |
|---|---------|-------|-----------|
| 1 | Valores de entrada (metrados, plantillas, partidas, ruta crítica) | Especialista carga | Entrada |
| 2 | Selección de proveedores | Especialista decide | Registra |
| 3 | Envío de solicitudes y seguimiento por correo | Especialista autoriza | **Automatizado** |
| 4 | Recepción de cotizaciones | | **Automatizado** |
| 5 | Lectura automática de documentos | | **Automatizado (IA)** |
| 6 | Homologación de propuestas | Especialista valida | **Propone** |
| 7 | Detección de información faltante | | **Automatizado** |
| 8 | Solicitud de aclaraciones | Especialista resuelve consultas | **Automatizado** |
| 9 | Cuadro comparativo | Especialista revisa | **Automatizado** |
| 10 | Revisión del especialista | Especialista | Pantalla de revisión |
| 11 | Decisión final | Especialista | Registra la decisión |

## 3. Flujo

1. Especialista carga metrados, proveedores, partidas, ruta crítica, vigencias
   y plantilla.
2. El agente envía solicitudes y hace seguimiento por correo.
3. Analiza correos y documentos: respuestas, cotizaciones, adjuntos y consultas.
4. ¿Hay aclaraciones pendientes?
   - Sí: notifica al especialista, que resuelve. El agente sigue hasta obtener la
     cotización final.
   - No: continúa con la propuesta.
5. Homologación: contrasta cada propuesta con el metrado referencial y registra
   diferencias.
6. Cuadro comparativo: llena la plantilla Excel y vincula las cotizaciones finales.
7. Especialista valida la homologación, revisa el comparativo y decide.

## 4. Arquitectura

| Pieza | Herramienta | Función |
|-------|-------------|---------|
| Excel | openpyxl | Entrada de metrados y salida del comparativo |
| Correo | Gmail API | Enviar solicitudes y seguir respuestas |
| Orquestación | n8n | Coordina los pasos y dispara las tareas |
| IA | API de Claude | Interpreta correos y documentos, detecta consultas |
| Datos | PostgreSQL / Supabase | Estados, versiones y trazabilidad |
| Archivos | Supabase Storage | Cotizaciones y adjuntos |
| Interfaz | HTML y JavaScript (rontend/) | Pantallas para el especialista |
| Modelo de datos | pydantic (`app/modelo.py`) | Formato común entre módulos |

**Regla central:** n8n orquesta, la IA interpreta y propone, y PostgreSQL guarda
el estado. Ninguno decide por el especialista.

## 5. Fases

### Fase 0: preparación (1 semana)
- Reunir un caso real completo, sin datos sensibles: itemizado, matriz de
  procura, proveedores, plantilla y 10 a 20 cotizaciones.
- Llenar a mano la matriz comparativa correcta: sirve para medir la app.
- Guardar el caso en `ejemplos/` y la plantilla en `plantillas/`.

### Fase 1: MVP (4 a 6 semanas)
- Entradas (proceso 1) y registro de proveedores.
- Envío de solicitudes y seguimiento por correo (proceso 3).
- Recepción y lectura automática (procesos 4 y 5).
- Homologación con alertas de vigencia y versiones (proceso 6).
- Detección de faltantes y aclaraciones (procesos 7 y 8).
- Cuadro comparativo en la plantilla del usuario (proceso 9).
- **Meta:** al menos 90 % de datos correctos en el caso de prueba, y comparativo
  listo en menos de 30 minutos.

### Fase 2: uso real
- Varios proyectos y partidas a la vez.
- Historial de precios por partida.
- Login de usuarios y piloto con 1 o 2 constructoras.

### Fase 3: startup
- Varias empresas con datos separados, plan de pago y confidencialidad.

## 6. División del trabajo

Primero se acuerda el formato común de datos en `app/modelo.py`. Después:

| Módulo | Carpeta | Procesos |
|--------|---------|----------|
| Entradas | `app/entradas/` | 1 y 2 |
| Correo | `app/correo/` | 3 |
| Recepción | `app/recepcion/` | 4 |
| Lectura | `app/lectura/` | 5 |
| Homologación | `app/homologacion/` | 6 |
| Aclaraciones | `app/aclaraciones/` | 7 y 8 |
| Comparativo | `app/comparativo/` | 9 |
| Interfaz | `frontend/` | 10 y 11 |
| Flujos | `n8n/` | orquestación |
| Base de datos | `db/` | esquema |
| Instrucciones de IA | `prompts/` | prompts |

Cada persona toma uno o más módulos, trabaja en su rama y entrega por Pull
Request. Dos personas no trabajan en el mismo módulo al mismo tiempo.

## 7. Riesgos

| Riesgo | Cómo lo manejamos |
|--------|-------------------|
| La IA lee mal un precio | Tabla de corrección con referencia a la página de origen |
| Cotización desactualizada | Versiones preliminar, corregida y final |
| Propuesta a punto de vencer | Alertas de vigencia |
| Homologación sin evidencia | La IA propone, el especialista aprueba |
| Fotos o escaneos borrosos | Marcar "baja confianza" |
| Unidades raras (bolsas, viajes) | Tabla de conversiones editable |
| Confidencialidad de precios | Archivos reales solo en Supabase Storage, nunca en el repositorio |

## 8. Próximos pasos

1. Reunir el caso real de la Fase 0.
2. Definir `app/modelo.py` y el esquema de `db/`.
3. Repartir los módulos de la sección 6.
