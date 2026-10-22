# Reglas de trabajo (para Codex, Antigravity y Claude Code)

Somos ingenieros civiles trabajando en este proyecto al mismo tiempo, cada uno
con su asistente de IA. Este archivo lo leen las tres IAs: Codex y Antigravity
directamente, Claude Code a través de `CLAUDE.md`. Explícanos todo en español y
en palabras simples, sin jerga de programación.

## Al empezar cada sesión

1. Si es la primera vez en esta computadora o algo falla (falta Git, Python,
   la sesión de GitHub o la carpeta `.venv`), ejecuta `scripts\unirse.cmd`.
2. Descarga lo último: `git pull origin main`
3. Pregunta en qué tarea vamos a trabajar y crea su rama (ver abajo).

## Reglas

1. **No cambies `main` directamente.** `main` es la versión aprobada.
2. Trabaja en una rama con el formato `usuario/tarea`, por ejemplo
   `dante/metrados` o `rodrigo/plantilla-excel`.
3. Al terminar, sube la rama y abre un Pull Request con `gh pr create`.
   En la descripción indica qué IA hizo el trabajo (Codex, Antigravity o Claude).
4. Nunca borres ni sobrescribas el trabajo del otro. Si necesitas tocar un
   archivo que otro está cambiando en un Pull Request abierto, avisa primero.
5. No subas contraseñas, claves de API ni el archivo `.env`.
6. No subas cotizaciones reales sin borrar nombres, RUC y contactos.

## Entorno

- Python 3.12 con entorno en `.venv`. Para usarlo:
  `.venv\Scripts\python.exe` (no instales paquetes fuera de `.venv`).
- Si agregas una librería, anótala en `requirements.txt`.
- La clave de la API va en `.env` (copia de `.env.example`).
- Pruebas: `.venv\Scripts\python.exe -m pytest`
- GitHub revisa cada Pull Request automáticamente. Si sale en rojo, corrígelo
  antes de pedir revisión.

## Sobre el proyecto

- De qué trata: plataforma que recibe cotizaciones de proveedores para una
  partida de obra, las lee automáticamente, las homologa en una plantilla Excel
  y genera el cuadro comparativo. El especialista de costos revisa y decide.
- Plan completo: [docs/PLAN.md](docs/PLAN.md). Léelo antes de empezar una tarea.
- Herramientas: Python, Streamlit, API de Claude, openpyxl.
- Carpetas: `app/` (código), `plantillas/` (Excel), `ejemplos/` (cotizaciones
  de prueba), `docs/` (documentos), `scripts/` (utilidades).
