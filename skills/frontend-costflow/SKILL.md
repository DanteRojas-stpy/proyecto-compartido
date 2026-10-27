---
name: frontend-costflow
description: Modernizar la interfaz de CostFlow con un dashboard de proyectos, seguimiento de solicitudes por accordions e identidad visual propia, conservando la lógica, las APIs y la autenticación existentes.
---

**Rol y/o Audiencia:**  
Eres un Senior Frontend Engineer y Product Designer especializado en SaaS B2B y software Construction Tech/AEC. Trabaja directamente sobre el repositorio existente de CostFlow.

CostFlow ya cuenta con backend, autenticación, APIs, rutas, modelos, lógica de negocio y funcionalidades operativas. Tu trabajo consiste en evolucionar únicamente el frontend, minimizando el impacto sobre todo lo ya desarrollado.

**Objetivo:**  
Moderniza la experiencia de CostFlow combinando:

- claridad tipográfica y sofisticación visual inspiradas en OpenSpace;
- dinamismo, cards, contraste y sensación de control operativo inspirados en Buildots;
- una nueva identidad propia de CostFlow orientada a procurement, costos y solicitudes de cotización AEC.

La prioridad técnica es:

**Preservar funcionamiento existente > mejorar UX > mejorar UI/branding > refactorizar.**

### Fase 1 — Analiza antes de modificar

Antes de escribir código:

1. Inspecciona la estructura actual del frontend.
2. Identifica framework, routing, componentes, hooks, servicios, estados y sistema de estilos.
3. Identifica dónde se encuentran definidos los colores y estilos globales.
4. Identifica qué componentes existentes pueden reutilizarse.
5. Identifica la vista posterior al login.
6. Identifica la vista actual de proyectos.
7. Identifica el componente actual de seguimiento de solicitudes.
8. Identifica las acciones y datos existentes de proveedores.

Antes de implementar, proporciona un resumen corto con:

- archivos que modificarás;
- componentes que reutilizarás;
- componentes nuevos estrictamente necesarios;
- cambios visuales que realizarás.

Después procede con la implementación.

## Nueva identidad CostFlow

El verde actual deja de ser el color principal del producto.

### Primary — azul

`#2B67DB`

Úsalo para:

- CTA principal;
- navegación activa;
- elementos seleccionados;
- links principales;
- focus;
- indicadores activos;
- acciones principales.

### Primary Dark

`#163B83`

Úsalo para:

- navegación de alto nivel;
- hover del primary;
- zonas de contraste;
- títulos sobre superficies oscuras.

### Success / Progress

`#40BE46`

El verde debe utilizarse para:

- proveedor respondió;
- cotización recibida;
- acción completada;
- progreso positivo;
- proyecto saludable;
- success feedback.

No lo uses como color genérico de navegación.

### Attention

`#FDD352`

Úsalo para:

- pendientes;
- deadline cercano;
- proveedor sin responder;
- elementos que requieren atención.

Utiliza texto oscuro sobre amarillo.

### Text / Charcoal

`#2A2927`

Debe ser el color principal del texto.

Evita negro puro.

### Background

`#F5F3EF`

Utiliza un off-white cálido como fondo general.

### Surfaces

`#FFFFFF`

y secundariamente:

`#F8F7F4`

### Information / Soft blue

`#D5E0F8`

Puede utilizarse para:

- selección suave;
- hover;
- badges informativos;
- información secundaria.

### Critical

`#D94A3D`

Background:

`#FCEBE8`

Utilízalo únicamente cuando exista una condición crítica real.

### Tokens

Integra estos valores en el sistema de estilos YA existente:

```css
--cf-primary: #2B67DB;
--cf-primary-dark: #163B83;
--cf-primary-soft: #D5E0F8;

--cf-success: #40BE46;
--cf-attention: #FDD352;

--cf-background: #F5F3EF;
--cf-surface: #FFFFFF;
--cf-surface-muted: #F8F7F4;

--cf-text-primary: #2A2927;
--cf-text-secondary: #66645F;
--cf-border: #DCDCDC;

--cf-critical: #D94A3D;
--cf-critical-soft: #FCEBE8;
```

Si CostFlow utiliza Tailwind, Sass, CSS Modules, styled-components, theme objects u otro sistema, adapta estos tokens al sistema existente.

No crees un sistema paralelo de estilos.

## Fase 2 — Página inicial de proyectos

Después del login, presenta todos los proyectos asociados a la cuenta.

No cambies la lógica actual de obtención de proyectos.

Utiliza los datos que ya entrega el backend.

Transforma la presentación actual en un dashboard de proyectos mediante cards.

Cada card debe mostrar, cuando el dato ya exista:

- nombre del proyecto;
- código;
- cliente;
- estado;
- cantidad de solicitudes de cotización;
- solicitudes críticas;
- fecha o actividad relevante.

La card completa debe ser clicable.

Al hacer clic:

**Proyecto → entorno actual de seguimiento de solicitudes**

Reutiliza el routing existente.

### Nuevo proyecto

Mantén el flujo existente para crear proyectos.

Incluye un CTA visible:

**+ Nuevo proyecto**

Utiliza `#2B67DB` como color principal.

No reconstruyas el formulario ni su lógica si ya existe.

## Fase 3 — Seguimiento de solicitudes

Mantén toda la lógica existente.

La presentación actual debe evolucionar hacia un sistema de accordions.

Cada **solicitud de cotización** representa un accordion independiente.

### Accordion cerrado

Debe mostrar únicamente la información necesaria para identificar rápidamente la solicitud:

- código;
- partida;
- fecha límite;
- proveedores invitados;
- respuestas recibidas;
- estado;
- criticidad.

Ejemplo conceptual:

**MA-001 · ELEVADORES**

`2 de 5 proveedores respondieron`

`Vence 29 nov`

`CRÍTICA`

Incluye chevron para indicar expansión.

### Solicitudes normales

Utiliza:

- superficie blanca;
- border neutro;
- charcoal;
- metadata secundaria.

### Solicitudes críticas

Utiliza:

- badge “CRÍTICA”;
- pequeño acento o borde coral;
- icono;
- fondo coral extremadamente suave.

No conviertas toda la card en roja.

## Fase 4 — Accordion abierto

Al hacer clic, expande el accordion y muestra la información de proveedores que actualmente aparece permanentemente en pantalla.

No elimines información.

Mantén:

- nombre del proveedor;
- correo;
- confirmación;
- estado;
- coordinaciones;
- última comunicación;
- historial de correos;
- estado de cada correo;
- observaciones;
- acciones existentes.

Mantén especialmente los controles actuales como:

- Coordinación;
- Guardar estado;
- Cerrar solicitud;

y cualquier otra acción funcional existente.

La modificación debe ser principalmente de **layout y presentación**, no de comportamiento.

## Estados de proveedores

Utiliza:

**Cotización recibida / completado**  
`#40BE46`

**Pendiente / requiere respuesta**  
`#FDD352`

**Coordinación / información**  
`#2B67DB`

**Crítico / incidencia importante**  
`#D94A3D`

**Neutral**  
charcoal + grises suaves.

Nunca dependas únicamente del color.

Combina:

color + texto + badge/icono cuando sea relevante.

## Tipografía

Toma OpenSpace como referencia conceptual de claridad y jerarquía.

Antes de instalar una nueva fuente, revisa la fuente actual.

No añadas una dependencia si no es necesaria.

Utiliza aproximadamente:

- títulos: 600–700;
- body: 400–500;
- labels: 500–600.

Prioriza:

- alta legibilidad;
- buen line-height;
- títulos claros;
- metadata visualmente secundaria;
- cifras y métricas fáciles de escanear.

## Dinamismo

Toma de Buildots la sensación de una plataforma operativa viva.

Implementa de forma moderada:

- hover de cards;
- transición al seleccionar proyecto;
- accordions animados;
- rotación del chevron;
- feedback de botones;
- badges;
- counters;
- indicadores de progreso;
- cambios suaves de superficie.

Transiciones aproximadas:

`150–250 ms`

Evita:

- parallax;
- glassmorphism;
- animaciones decorativas;
- gradients innecesarios;
- efectos propios de una landing page;
- sombras pesadas.

CostFlow es una herramienta operativa.

## Restricciones técnicas obligatorias

No reconstruyas CostFlow.

No modifiques backend salvo que sea absolutamente imprescindible.

No modifiques base de datos.

No cambies endpoints existentes.

No alteres contratos API.

No modifiques autenticación.

No cambies el sistema de permisos.

No reemplaces routing.

No sustituyas el framework actual.

No reorganices carpetas sin necesidad.

No hagas refactors masivos.

No renombres componentes, variables o servicios sin justificación funcional.

No introduzcas nuevas librerías cuando pueda resolverse con las actuales.

Prioriza reutilizar componentes existentes.

Prioriza cambios pequeños y revisables.

No inventes datos que actualmente no existan.

Si necesitas un campo como `{es_critica}` y el backend todavía no lo entrega:

1. prepara el componente para soportarlo;
2. documenta la dependencia;
3. no cambies automáticamente el backend.

## Validación después de implementar

Verifica que continúen funcionando:

- login;
- carga de proyectos;
- creación de proyecto;
- navegación entre proyectos;
- acceso al seguimiento;
- carga de solicitudes;
- información de proveedores;
- coordinación;
- correcciones;
- cierre de solicitudes;
- demás acciones existentes.

Corrige cualquier regresión provocada por los cambios del frontend.

**Formato de Respuesta:**  
Realiza cambios incrementales directamente sobre el código existente.

Mantén los diffs pequeños y fáciles de revisar.

No desarrolles una nueva aplicación paralela.

El resultado final debe sentirse como:

**CostFlow evolucionado → OpenSpace en claridad + Buildots en dinamismo + identidad propia enfocada en procurement y costos AEC.**
