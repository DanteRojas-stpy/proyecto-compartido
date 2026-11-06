# 🧩 Plantilla de Prompt — Desarrollo de HTML para Repositorio GitHub

> **Instrucciones de uso:**
> 1. Copia esta plantilla completa.
> 2. Reemplaza todo lo que está entre `[corchetes]` con la información de tu proyecto.
> 3. Borra las secciones que no apliquen (o escribe "No aplica").
> 4. Pega el resultado en ChatGPT (puedes adjuntar archivos de apoyo: capturas, logos, PDFs, código existente).

---

## 🔄 Opción B: si la información ya está en un chat de ChatGPT

No hace falta llenar la plantilla a mano. Abre **ese mismo chat** (donde ChatGPT ya conoce el proyecto) y pega este mensaje seguido de la plantilla completa (secciones 1 a 10):

```text
Con base en TODO lo que hemos hablado en esta conversación sobre mi proyecto,
llena la siguiente plantilla. Reglas:
- Usa solo información que aparezca en esta conversación; no inventes datos.
- Si algún campo no se mencionó, escribe "⚠️ PENDIENTE" para que yo lo complete.
- Mantén el formato Markdown y la estructura exacta de la plantilla.
- Entrega el resultado dentro de un solo bloque de código Markdown para copiarlo fácilmente.
- NO generes todavía el HTML; solo devuelve la plantilla llenada.

[PEGA AQUÍ LA PLANTILLA, desde "1. Rol que debe asumir ChatGPT" hasta el final]
```

Después:
1. Revisa la plantilla llenada y completa los campos marcados con **⚠️ PENDIENTE**.
2. Corrige cualquier dato que ChatGPT haya interpretado mal.
3. Pega la plantilla final en un **chat nuevo** (queda un contexto limpio, sin la conversación anterior) o en el mismo chat, y pide: *"Ahora desarrolla el HTML según esta especificación."*

> 💡 **Alternativa:** si el chat es muy largo o es de otra cuenta, usa *Compartir → Copiar enlace* o exporta la conversación a un archivo `.txt`/`.pdf`, adjúntala en un chat nuevo junto con la plantilla y usa el mismo mensaje cambiando "esta conversación" por "el archivo adjunto".

---

## 1. 🎭 Rol que debe asumir ChatGPT

Actúa como un **desarrollador front-end senior** experto en HTML5, CSS3 y JavaScript, con buenas prácticas de accesibilidad, diseño responsive y publicación en **GitHub Pages**. Explica tus decisiones de forma breve y entrega código listo para subir al repositorio.

---

## 2. 📌 Contexto del proyecto

| Campo | Información |
|---|---|
| **Nombre del proyecto** | [Ej. "EcoRuta MVP"] |
| **Programa / curso** | [Ej. Beca IA Talent – Módulo 8: Desarrollo MVP] |
| **Equipo / autor(es)** | [Nombres de los integrantes] |
| **Problema que resuelve** | [Describe en 2–3 líneas el problema] |
| **Solución propuesta** | [Describe en 2–3 líneas la solución / MVP] |
| **Público objetivo** | [Ej. estudiantes universitarios, pymes, docentes…] |
| **Propuesta de valor** | [¿Por qué es diferente o mejor?] |
| **Estado actual** | [Idea / prototipo / MVP en progreso / versión final] |

### Información adicional relevante
[Pega aquí cualquier texto de contexto: resumen del proyecto, hallazgos de investigación, entrevistas, métricas, enlaces a documentos, etc.]

---

## 3. 🎯 Objetivo del HTML

¿Qué tipo de página necesitas?

- [ ] Landing page de presentación del proyecto
- [ ] Prototipo navegable del MVP
- [ ] Portafolio / página del equipo
- [ ] Documentación del proyecto
- [ ] Dashboard o visualización de datos
- [ ] Otro: [especificar]

**Acción principal que debe realizar el usuario en la página:** [Ej. registrarse, ver el demo, descargar, contactar al equipo]

---

## 4. 🗂️ Estructura y secciones

Lista las secciones en el orden en que deben aparecer:

1. **Header / navegación:** [logo, menú con enlaces a…]
2. **Hero:** [título principal, subtítulo, botón de llamada a la acción]
3. **Problema:** [contenido]
4. **Solución / cómo funciona:** [contenido, pasos, ícono por paso]
5. **Características / beneficios:** [lista]
6. **Demo / capturas:** [imágenes o video]
7. **Equipo:** [nombres, roles, fotos, LinkedIn]
8. **Contacto / CTA final:** [formulario, correo, redes]
9. **Footer:** [créditos, año, enlace al repositorio]

---

## 5. 🎨 Diseño e identidad visual

| Elemento | Especificación |
|---|---|
| **Estilo general** | [Ej. moderno, minimalista, corporativo, juvenil, tecnológico] |
| **Colores principales** | [Ej. #1E3A8A (primario), #F59E0B (acento), #F9FAFB (fondo)] |
| **Tipografía** | [Ej. Inter / Poppins desde Google Fonts] |
| **Logo** | [Adjunto / no hay / usar texto] |
| **Modo oscuro** | [Sí / No] |
| **Referencias visuales** | [URLs de páginas que te gusten] |

---

## 6. ⚙️ Requisitos técnicos

- **Tecnologías:** [Solo HTML + CSS + JS puro / Tailwind CSS / Bootstrap / otro]
- **Estructura de archivos:** [Un solo `index.html` / separar en `index.html`, `css/styles.css`, `js/main.js`, `assets/`]
- **Responsive:** Debe funcionar en móvil, tablet y escritorio.
- **Accesibilidad:** Etiquetas semánticas, `alt` en imágenes, contraste adecuado.
- **SEO básico:** `title`, `meta description`, Open Graph.
- **Interactividad:** [Ej. menú hamburguesa, scroll suave, animaciones, validación de formulario, modo oscuro]
- **Sin backend:** El sitio debe ser estático para publicarse en GitHub Pages.
- **Librerías externas permitidas:** [Sí, vía CDN / No]

---

## 7. 📁 Repositorio de GitHub

| Campo | Información |
|---|---|
| **URL del repositorio** | [https://github.com/usuario/repositorio] |
| **Rama principal** | [main] |
| **Publicación** | [GitHub Pages: Sí / No] |
| **Archivos existentes** | [Lista o pega el código actual si ya existe] |

---

## 8. 📦 Entregables que necesito

Por favor entrega:

1. El **código completo** de cada archivo, en bloques separados e indicando la ruta (ej. `css/styles.css`).
2. La **estructura de carpetas** del proyecto en formato árbol.
3. Un archivo **`README.md`** con: descripción, tecnologías, cómo ejecutarlo localmente, enlace al sitio y créditos del equipo.
4. Los **pasos para subirlo a GitHub** y activar **GitHub Pages**.
5. [Opcional] Sugerencias de mejora para una siguiente versión.

---

## 9. 🚫 Restricciones y consideraciones

- [Ej. No usar imágenes con derechos de autor; usar placeholders o Unsplash]
- [Ej. Todo el contenido en español]
- [Ej. Fecha de entrega: dd/mm/aaaa]
- [Ej. El código debe estar comentado para que el equipo lo entienda]

---

## 10. ✅ Criterios de éxito

La página estará lista cuando:

- [ ] Se vea correctamente en móvil y escritorio.
- [ ] Comunique claramente el problema, la solución y el valor del proyecto.
- [ ] Esté publicada y funcionando en GitHub Pages.
- [ ] [Otro criterio propio del equipo]

---

> 💬 **Antes de escribir el código**, si falta información importante, hazme hasta 5 preguntas puntuales. Si todo está claro, procede directamente con los entregables.
