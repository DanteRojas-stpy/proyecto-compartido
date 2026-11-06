# CostFlow — Workflow funcional y arquitectura del MVP

Versión consolidada con las reglas definidas en el documento **MVP CostFlow.docx** y las precisiones posteriores. Se mantienen las cinco etapas del MVP y la arquitectura basada en **GitHub, Supabase, PostgreSQL, n8n y Gmail**.

La generación del cuadro comparativo queda definida mediante un **script en Python**.

---

# 1. Arquitectura tecnológica

| Herramienta | Responsabilidad dentro de CostFlow |
|---|---|
| **GitHub** | Código del aplicativo, scripts, configuraciones y control de versiones. |
| **Supabase Storage** | Almacenamiento de itemizados, plantillas, PDF, Excel e imágenes de cotizaciones. |
| **PostgreSQL** | Registro de solicitudes, proveedores, estados, seguimientos, versiones y datos homologados. |
| **n8n** | Automatización de envíos, seguimientos, recepción, análisis de cotizaciones y coordinación de cuadros comparativos. |
| **Gmail** | Canal de comunicación y formalización de cotizaciones y sus versiones. |
| **Frontend** | Interfaz donde el especialista registra, supervisa, valida y consulta resultados. |
| **Script Python** | Completa la plantilla Excel del cuadro comparativo utilizando los datos homologados y conserva su estructura, fórmulas y formato. |

---

# 2. Workflow actualizado

## E1. Registro de la solicitud de cotización

El especialista carga la información inicial en el frontend:

- Excel de itemizados y metrados.
- Plantilla del cuadro comparativo.
- Matriz de comunicaciones con proveedores y correos.
- Cuadro de procura por proyecto.
- Tiempo de vigencia de la solicitud.
- Proveedores seleccionados.
- Partidas por cotizar.
- Identificación de partidas pertenecientes o no a la ruta crítica.

Se crea un espacio por cada solicitud de cotización.

La información se distribuye de la siguiente manera:

- **Supabase Storage:** archivos y plantillas.
- **PostgreSQL:** información estructurada de la solicitud y proveedores.

Un mismo proveedor puede participar en diferentes solicitudes de cotización.

### Estado inicial

Cuando se crea una solicitud de cotización, se asigna automáticamente el estado:

`Inicio`

Este estado representa el comienzo del proceso.

---

# 3. E2. Envío automatizado y seguimiento semiautomatizado

n8n consulta PostgreSQL y detecta las solicitudes que se encuentran en estado:

`Inicio`

El flujo es:

```text
PostgreSQL
    ↓
n8n verifica la solicitud
    ↓
Gmail envía el correo
    ↓
PostgreSQL registra la fecha de envío
```

El envío es ejecutado por n8n después de la autorización del especialista.

## Asunto del correo

Se utiliza la siguiente estructura:

```text
Cotización de partida – Proyecto X – Proveedor Y
```

El seguimiento de la comunicación se realiza utilizando:

- Correo del proveedor.
- Asunto.
- Contexto del hilo de correos.

---

## 3.1 Seguimiento de proveedores

El agente analiza periódicamente el estado de respuesta de cada proveedor.

### Frecuencia de seguimiento

| Condición de la partida | Frecuencia |
|---|---|
| Pertenece a la ruta crítica | Diario |
| No pertenece a la ruta crítica | Cada 3 días |

Los recordatorios no implican necesariamente el envío automático de un nuevo correo al proveedor.

El agente genera notificaciones para el especialista mediante:

- Plataforma.
- Correo electrónico al usuario.

La notificación informa el estado de respuesta de los proveedores para que el especialista decida qué acción tomar.

Las acciones pueden realizarse mediante:

- Correo.
- WhatsApp.
- Llamada.
- Otro medio de comunicación.

Por esta razón, esta etapa se considera un proceso de **seguimiento semiautomatizado**.

---

## 3.2 Estados de respuesta del proveedor

Cada proveedor puede presentar alguno de los siguientes estados:

- `Envió cotización`
- `Envió cotización con aclaración`
- `No envió cotización`

El estado `Envió cotización` corresponde a la cotización definitiva que será utilizada posteriormente para la homologación.

El agente debe analizar el contexto del hilo de correos y comparar las comunicaciones anteriores para determinar la versión final.

---

# 4. E3. Recepción y procesamiento de cotizaciones

El flujo general es:

```text
Gmail
   ↓
n8n
   ↓
Identificación de solicitud y proveedor
   ↓
Análisis del mensaje y documentos
   ↓
Supabase Storage
   ↓
PostgreSQL
```

## Proceso

1. Gmail recibe la respuesta del proveedor.
2. n8n detecta el correo.
3. n8n identifica:
   - Solicitud de cotización.
   - Proveedor.
4. Analiza:
   - Contenido del mensaje.
   - Contexto del hilo.
   - Documentos adjuntos.
5. Descarga los archivos.
6. Guarda los documentos en Supabase Storage.
7. PostgreSQL registra:
   - Fecha de recepción.
   - Archivo asociado.
   - Estado de respuesta.

---

## 4.1 Formatos de cotización

Las cotizaciones pueden recibirse en:

- Excel.
- PDF.
- Imágenes.

Si el proveedor responde mediante correo pero no remite:

- PDF.
- Excel.
- Imagen o fotografía.

no se considera que haya enviado una cotización.

---

## 4.2 Formalización y versionado

Toda formalización o versionado de una cotización debe estar documentado mediante correo electrónico.

También se contempla una opción de carga manual.

Las aclaraciones y consultas pueden realizarse mediante el canal acordado entre las partes.

---

## 4.3 Identificación de la cotización definitiva

La cotización definitiva se reconoce en función de:

**la última cotización remitida por el proveedor.**

El agente debe:

1. Analizar el contexto del hilo de correos.
2. Comparar las comunicaciones anteriores.
3. Identificar la última cotización remitida.
4. Recuperar el archivo correspondiente.
5. Utilizarlo para la homologación.
6. Llevar posteriormente esa información al cuadro comparativo.

Por tanto, la versión definitiva no depende únicamente del nombre del archivo, sino del contexto de las comunicaciones.

---

# 5. E4. Homologación de propuestas

El flujo general es:

```text
Supabase Storage
      ↓
     n8n
      ↓
Extracción mediante IA o código
      ↓
Homologación
      ↓
PostgreSQL
```

n8n recupera las cotizaciones definitivas.

Posteriormente, la información se envía a un componente de extracción estructurada mediante:

- IA.
- Código.

PostgreSQL conserva:

- Valores originales.
- Valores normalizados.

---

## 5.1 Criterios de homologación

La estructura y los criterios específicos de homologación se encuentran definidos en:

**la plantilla de homologación proporcionada.**

El agente utiliza dicha plantilla como referencia para homologar las cotizaciones.

El especialista valida:

- Criterios.
- Resultados.
- Excepciones que requieran revisión.

---

# 6. E5. Elaboración del cuadro comparativo

La información homologada almacenada en PostgreSQL es utilizada para generar el cuadro comparativo.

El flujo queda definido como:

```text
PostgreSQL
     ↓
Datos homologados
     ↓
n8n
     ↓
Script Python
     ↓
Plantilla Excel
     ↓
Cuadro comparativo
     ↓
Supabase Storage
```

---

## 6.1 Función del script Python

El script es responsable de:

1. Recuperar o recibir los datos homologados.
2. Abrir la plantilla Excel del cuadro comparativo.
3. Identificar las hojas y celdas correspondientes.
4. Colocar la información homologada.
5. Mantener las fórmulas existentes.
6. Conservar la estructura y formato de la plantilla.
7. Generar una nueva versión del cuadro comparativo.
8. Entregar el archivo generado a n8n.
9. Permitir que n8n lo almacene en Supabase Storage.

La lógica puede implementarse mediante Python utilizando una librería como `openpyxl`.

Conceptualmente:

```text
Datos homologados
       ↓
generar_comparativo.py
       ↓
Plantilla original
       ↓
Inserción de datos
       ↓
Conservación de fórmulas y formato
       ↓
Cuadro comparativo final
```

---

## 6.2 Papel de n8n

n8n no realiza directamente toda la manipulación compleja del Excel.

Su función es coordinar el proceso:

```text
n8n
 ↓
Obtiene información
 ↓
Ejecuta o llama al script Python
 ↓
Recibe el Excel generado
 ↓
Guarda el documento
 ↓
Actualiza PostgreSQL
```

El procesamiento específico de la plantilla queda delegado al script.

---

# 7. Estados de la solicitud de cotización

Cada solicitud tiene tres estados:

- `Inicio`
- `Cerrado`
- `Cerrado sin proveedores`

---

## 7.1 Estado Inicio

Se asigna cuando:

**se crea la solicitud de cotización.**

A partir de este estado comienza el proceso de:

- Envío.
- Seguimiento.
- Recepción.
- Procesamiento.
- Homologación.

---

## 7.2 Estado Cerrado

La solicitud cambia a:

`Cerrado`

cuando:

**se obtiene el cuadro comparativo.**

El cuadro comparativo representa la culminación del flujo de solicitud de cotización.

---

## 7.3 Estado Cerrado sin proveedores

La solicitud cambia a:

`Cerrado sin proveedores`

cuando ocurre cualquiera de las siguientes condiciones:

1. No se obtienen cotizaciones para homologación.
2. Se cumple el tiempo de vigencia de la solicitud de cotización.

---

# 8. Lógica resumida de estados

```text
Creación de solicitud
        ↓
      Inicio
        ↓
Envío + seguimiento
        ↓
Recepción de cotizaciones
        ↓
        ├── Existen cotizaciones
        │        ↓
        │   Homologación
        │        ↓
        │   Script Python
        │        ↓
        │   Cuadro comparativo
        │        ↓
        │      Cerrado
        │
        └── No existen cotizaciones
                 ↓
        Cerrado sin proveedores
```

También:

```text
Inicio
   ↓
Se cumple la vigencia
   ↓
Cerrado sin proveedores
```

---

# 9. Lógica de seguimiento

```text
Partida
   ↓
¿Pertenece a ruta crítica?
   ↓
 ┌───────────────┐
 │               │
Sí              No
 │               │
Diario       Cada 3 días
 │               │
 └───────┬───────┘
         ↓
n8n analiza respuestas
         ↓
Notifica al especialista
         ↓
Especialista decide la acción
```

---

# 10. Responsabilidades del especialista y del agente

| Actividad | Especialista | Agente IA / n8n |
|---|---|---|
| Cargar metrados y plantillas | Responsable | Validación inicial |
| Seleccionar proveedores | Responsable | Registra información |
| Definir partidas y ruta crítica | Responsable | Prioriza seguimiento |
| Enviar solicitudes | Autoriza | Ejecuta |
| Seguimiento de correos | Supervisa y toma acciones | Analiza y notifica |
| Procesar cotizaciones | Revisa excepciones | Extrae información |
| Identificar aclaraciones | Resuelve consultas | Detecta y notifica |
| Recuperar cotización definitiva | Interviene si es necesario | Identifica la última cotización |
| Homologar cotizaciones | Valida criterio | Propone |
| Elaborar cuadro comparativo | Revisa | Coordina generación |
| Completar plantilla Excel | Revisa resultado | Script Python ejecuta el llenado |
| Evaluar y seleccionar proveedor | Decide | Facilita información |

---

# 11. Relación entre las herramientas

## GitHub

Se utiliza para:

- Código del aplicativo.
- Código del script Python.
- Scripts auxiliares.
- Configuraciones.
- Control de versiones.
- Desarrollo del MVP.

Por ejemplo:

```text
costflow/
│
├── frontend/
├── backend/
├── scripts/
│   └── generar_comparativo.py
├── database/
├── n8n/
└── docs/
```

GitHub no necesita intervenir directamente cada vez que se procesa una cotización.

---

## Supabase Storage

Almacena archivos como:

- Itemizados.
- Plantillas.
- PDF.
- Excel.
- Imágenes.
- Cotizaciones recibidas.
- Cuadros comparativos generados.

---

## PostgreSQL

Es la fuente estructurada de información.

Registra:

- Solicitudes.
- Proveedores.
- Estados.
- Fechas.
- Seguimientos.
- Cotizaciones.
- Versiones.
- Información homologada.
- Datos utilizados en los cuadros comparativos.

---

## n8n

Actúa como el principal orquestador de procesos.

Coordina:

- Consulta de solicitudes.
- Envío de correos.
- Seguimiento.
- Análisis de respuestas.
- Identificación de versiones.
- Extracción documental.
- Homologación.
- Notificaciones.
- Ejecución del script Python.
- Generación del cuadro comparativo.

---

## Gmail

Es el canal formal de comunicación con los proveedores.

Además, es fundamental para la trazabilidad debido a la regla:

> Toda formalización o versionado de una cotización debe estar documentado mediante correo electrónico.

---

## Script Python

Es responsable específicamente del procesamiento del Excel del cuadro comparativo.

No sustituye a n8n.

La relación es:

```text
n8n = coordina el proceso

Python = ejecuta la manipulación del Excel
```

---

# 12. Flujo integral de CostFlow

```text
ESPECIALISTA
     │
     │ crea solicitud
     ▼
FRONTEND COSTFLOW
     │
     ├───────────────► SUPABASE STORAGE
     │                  - itemizados
     │                  - plantillas
     │
     ▼
POSTGRESQL
     │
     │ estado = Inicio
     ▼
n8n
     │
     ├──────────────► GMAIL
     │                envío de solicitud
     │
     ▼
SEGUIMIENTO
     │
     ├─ crítica → diario
     │
     └─ no crítica → cada 3 días
     │
     ▼
RESPUESTA DEL PROVEEDOR
     │
     ▼
GMAIL
     │
     ▼
n8n
     │
     ├─ analiza correo
     ├─ analiza contexto
     ├─ identifica proveedor
     ├─ identifica solicitud
     └─ identifica última cotización
     │
     ▼
SUPABASE STORAGE
     │
     ▼
EXTRACCIÓN IA / CÓDIGO
     │
     ▼
HOMOLOGACIÓN
     │
     ▼
POSTGRESQL
     │
     │ datos originales + normalizados
     ▼
n8n
     │
     ▼
SCRIPT PYTHON
     │
     ├─ abre plantilla
     ├─ inserta datos
     ├─ conserva fórmulas
     └─ conserva formato
     │
     ▼
CUADRO COMPARATIVO
     │
     ▼
SUPABASE STORAGE
     │
     ▼
REVISIÓN DEL ESPECIALISTA
     │
     ▼
SOLICITUD = CERRADO
```

---

# 13. Flujo alternativo sin cotizaciones

Si no se obtienen cotizaciones para homologación:

```text
Solicitud
   ↓
No existen cotizaciones homologables
   ↓
Cerrado sin proveedores
```

Si se cumple la vigencia:

```text
Solicitud
   ↓
Vence el plazo de vigencia
   ↓
Cerrado sin proveedores
```

---

# 14. Resumen de responsabilidades tecnológicas

```text
GitHub
   ↓
Código y control de versiones

Supabase Storage
   ↓
Archivos

PostgreSQL
   ↓
Datos estructurados

Gmail
   ↓
Comunicación y trazabilidad documental

n8n
   ↓
Orquestación y automatización

Python
   ↓
Manipulación del Excel

Frontend
   ↓
Interacción con el especialista
```

---

# 15. Definición final del componente de cuadro comparativo

La etapa E5 queda definida de la siguiente manera:

> **n8n coordina la generación del cuadro comparativo. Un script Python procesa la plantilla Excel, incorpora los datos homologados provenientes de PostgreSQL y genera una nueva versión del archivo conservando su estructura, fórmulas y formato. El documento generado se almacena posteriormente en Supabase Storage para su revisión por el especialista.**

Con esta definición, el workflow del MVP queda cerrado conceptualmente desde la creación de la solicitud hasta la obtención del cuadro comparativo.