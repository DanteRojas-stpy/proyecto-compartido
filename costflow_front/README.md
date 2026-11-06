# CostFlow 🏗️🦉

> **Plataforma web para constructoras y contratistas que compara cotizaciones de obra y alerta cuáles priorizar.**

Desarrollada con **HTML5 semántico, CSS3 moderno y Vanilla JavaScript** (sin dependencias ni frameworks externos, excepto tipografía Google Fonts).

---

## ⚡ ¿Cómo Ejecutar el Proyecto?

### Método 1: Doble Clic Directo (Recomendado)
1. Navega en el Explorador de Windows a:
   ```
   C:\Users\Lenovo\OneDrive\Documentos\costflow
   ```
2. Haz doble clic en el archivo **`index.html`**.
3. Se abrirá instantáneamente en tu navegador predeterminado (Google Chrome, Microsoft Edge, Firefox, Safari).

### Método 2: Servidor Local
Si cuentas con Node.js en PowerShell:
```powershell
cd "C:\Users\Lenovo\OneDrive\Documentos\costflow"
npx serve
```

---

## 🧭 Arquitectura y Navegación SPA por Hash

La aplicación funciona como una Single Page Application (SPA) pura sin recargas de página:

* **`#/inicio`**: Página de inicio completa.
* **`#/compara/edificaciones/obras-provisionales-preliminares`**: Vista interna para Obras provisionales.
* **`#/compara/edificaciones/salud-seguridad`**: Vista interna para Salud y seguridad.
* **`#/compara/edificaciones/estructuras`**: Vista interna para Estructuras.
* **`#/compara/edificaciones/arquitectura`**: Vista interna para Arquitectura.
* **`#/compara/edificaciones/instalaciones-sanitarias`**: Vista interna para Instalaciones sanitarias.
* **`#/compara/edificaciones/instalaciones-electricas-mecanicas`**: Vista interna para Instalaciones eléctricas y mecánicas.
* **`#/compara/edificaciones/otros`**: Vista interna para Otros.
* **`#/vigila`**: Vista interna para Vigila con área de carga *"Cuadro de procura"*.

---

## 🏗️ Estructura del Proyecto

```text
costflow/
├── index.html              # Estructura semántica de la página de inicio y vistas internas
├── css/
│   └── styles.css          # Variables CSS (:root), animaciones, responsive y microinteracciones
├── js/
│   ├── data.js             # Arreglo extensible de categorías, configuración de Vigila y contacto
│   └── main.js             # Enrutador por hash, componente de carga reutilizable y modal
├── assets/
│   ├── logo-costflow.png   # Logotipo oficial (ubicado en el header)
│   └── mascota-buho.png    # Mascota 'El Búho' (ubicada en el cierre de la página)
└── README.md               # Documentación completa del proyecto
```

---

## 🎨 Paleta de Colores y Tokens CSS

* **Azul marino profundo (`#0B2F63`)**: Títulos, textos fuertes y franja sólida inferior.
* **Azul real (`#1B5FC1`)**: Botones secundarios, acentos y degradados.
* **Cian / Turquesa (`#12B5D6` y `#5ED3EC`)**: Palabra "CostFlow", flechas, detalles y estados activos.
* **Blanco (`#FFFFFF`) y Gris azulado muy claro (`#F3F7FC`)**: Fondos de sección alternados.
* **Amarillo (`#FFC21A` con hover `#FFB000`)**: Uso armónico (~10% de la interfaz) reservado para:
  * Botón principal CTA *"Comienza ahora"*.
  * Botón *"Regístrate"* en el header.
  * Línea sutil bajo *"mejor decisión"* en el hero.
  * Botón *"Comparar cotizaciones"*.
  * Insignia y halo de alerta *"Prioriza esta cotización"*.
  * **Texto sobre amarillo en azul marino `#0B2F63`**.

---

## 🧩 Componentes y Funcionalidades Destacadas

### 1. Header Fijo y Translúcido
* Translúcido con efecto de desenfoque (`backdrop-filter: blur(16px)`).
* Se reduce sutilmente al hacer scroll (de 78px a 64px).
* **Menú Compara**: Mega-menú desplegable accesible con el subtítulo principal *"Edificaciones"* y sus 7 partidas secundarias.
* **Menú Vigila**: Enlace directo a la vista de vigilancia.
* **Botón Regístrate**: Abre un modal accesible con validación de correo, focus trap, guardado en `localStorage` (con comentario `// TODO: conectar un backend`) y cierre mediante tecla `Escape` o clic fuera.
* En pantallas móviles se transforma en un panel lateral con acordeón táctil.

### 2. Componente Único Reutilizable de Carga de Archivos
* Implementado una sola vez y reutilizado en las **8 vistas** (los 7 subtítulos de Edificaciones + Vigila).
* **Memoria independiente**: Los archivos subidos se almacenan por separado en el estado de cada vista (`filesInMemory`).
* Acepta drag-and-drop o selección manual de múltiples archivos.
* Soporta PDF, Excel (`.xls`, `.xlsx`), CSV, Word (`.doc`, `.docx`) e imágenes (`.png`, `.jpg`, `.jpeg`, `.webp`).
* Validación estricta de tipo y tamaño máximo (**20 MB**).
* Ícono específico por tipo de archivo, nombre, tamaño formateado y botón para eliminar.
* En las vistas de Compara, el botón amarillo **"Comparar cotizaciones"** se habilita dinámicamente únicamente cuando hay al menos 2 archivos subidos.

### 3. Página de Inicio (#/inicio)
1. **Hero a pantalla completa**:
   * Fondo de cotización realista de obra (*COTIZACIÓN DE OBRA N° 0045-2026*) construida íntegramente en HTML/CSS con partidas de construcción peruanas en Soles (S/), desenfocada, rotada y cubierta por un degradado azul marino semitransparente para máxima legibilidad.
   * Efecto parallax leve al mover el cursor y al hacer scroll.
   * Indicador animado de *"desliza hacia abajo"*.
2. **Sección 1 (Compara - Balanza interactiva)**:
   * Texto a la izquierda, ilustración en SVG plano a la derecha.
   * Estado inicial: balanza desequilibrada con 3 hojas flotando.
   * Al pasar el cursor o tocar: las 3 cotizaciones se deslizan y se transforman en un cuadro comparativo animado (Precio total, Plazo, Garantía, Score).
3. **Sección 2 (Vigila - Lupa interactiva)**:
   * Ilustración a la izquierda, texto a la derecha.
   * La lupa sigue suavemente el cursor sobre la pila de cotizaciones.
   * Al interactuar, la cotización B se ilumina con un halo amarillo y emerge la notificación: *"Prioriza esta cotización (Proveedor B · vence en 2 días · 6% menos que el promedio)"*.
4. **Cierre de la página**:
   * Mascota oficial (`assets/mascota-buho.png`) grande y centrada con animación suave de flotación y el texto *"Tu búho vigilante de cotizaciones"*.
   * Franja sólida azul marino `#0B2F63` con enlaces funcionales a LinkedIn, WhatsApp/Teléfono (`+51 000 000 000`) y correo (`contacto@costflow.com`).
