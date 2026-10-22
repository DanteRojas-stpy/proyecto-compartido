# Instrucciones para agentes de IA (Codex, Claude Code y otros)

Este repositorio lo trabajan dos personas al mismo tiempo, cada una con su propio
agente de IA. Estas reglas aplican a todos los agentes por igual.

## Flujo de trabajo con Git

- **Nunca hagas commit ni push directo a `main`.** Todo cambio entra por Pull Request.
- Antes de empezar una tarea, actualiza desde `main`:
  `git checkout main && git pull origin main`
- Crea una rama por tarea con el formato `<persona>/<descripcion-corta>`,
  por ejemplo `dante/login-usuarios` o `companero/arreglar-estilos`.
- Haz commits pequeños y con mensajes claros en español, en modo imperativo:
  `Agrega validación al formulario de registro`.
- Antes de abrir el PR, trae los últimos cambios de `main` a tu rama y resuelve
  los conflictos que aparezcan.
- Abre el PR con `gh pr create` y describe qué cambió y cómo probarlo.
- No reescribas el historial de ramas compartidas (`push --force` prohibido
  sobre `main` o sobre la rama de la otra persona).

## Coordinación

- Las tareas se reparten con **GitHub Issues**. Trabaja solo en lo que esté
  asignado a tu persona.
- Si necesitas modificar un archivo que la otra persona está tocando en un PR
  abierto, coméntalo en ese PR antes de hacerlo.
- Mantén este archivo actualizado cuando se acuerden nuevas convenciones.

## Proyecto

<!-- Completar cuando se defina el proyecto -->
- Descripción: _por definir_
- Lenguaje / framework: _por definir_
- Cómo instalar dependencias: _por definir_
- Cómo correr el proyecto: _por definir_
- Cómo correr los tests: _por definir_

## Estilo de código

- Sigue el estilo del código que ya existe en el archivo que estás editando.
- No agregues dependencias nuevas sin mencionarlo en el PR.
- No subas secretos (contraseñas, API keys, archivos `.env`).
