# Reglas de trabajo (para Codex y Claude Code)

Somos dos ingenieros civiles trabajando en este proyecto al mismo tiempo,
cada uno con su asistente de IA. Explícanos todo en español y en palabras
simples, sin jerga de programación.

## Reglas

1. **No cambies `main` directamente.** `main` es la versión aprobada.
2. Antes de empezar, descarga lo último: `git pull origin main`
3. Trabaja en una copia propia (rama) con el nombre `persona/tarea`,
   por ejemplo `dante/metrados`.
4. Al terminar, súbela y abre un Pull Request para que el otro lo revise.
5. Nunca borres ni sobrescribas el trabajo del otro.
6. No subas contraseñas ni datos privados.

## Sobre el proyecto

- De qué trata: plataforma que recibe cotizaciones de proveedores para una
  partida de obra, las lee automáticamente, las homologa en una plantilla Excel
  y genera el cuadro comparativo. El especialista de costos revisa y decide.
- Plan completo: [docs/PLAN.md](docs/PLAN.md). Léelo antes de empezar una tarea.
- Herramientas: Python, Streamlit, API de Claude, openpyxl.
- Las cotizaciones de ejemplo pueden tener datos sensibles: no las subas sin
  borrar nombres, RUC y contactos.
