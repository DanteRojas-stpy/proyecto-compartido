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

- De qué trata: plataforma que recibe cotizaciones de proveedores para obra,
  las lee automáticamente, las homologa y llena la matriz comparativa.
- Plan completo: [docs/PLAN.md](docs/PLAN.md). Léelo antes de empezar una tarea.

### Alcance (respétalo)

- **Entrada (proceso 1):** itemizado, matriz de procura, proveedores, plantilla
  Excel de la matriz comparativa, ruta crítica y vigencias.
- **Lo hace la app:** 3 envío de solicitudes y seguimiento por correo,
  4 recepción de cotizaciones, 5 lectura automática, 6 homologación,
  7 detección de información faltante, 8 solicitud de aclaraciones,
  9 cuadro comparativo.
- **Lo decide el especialista:** 2 selección de proveedores, 10 revisión y
  11 decisión final. La app le muestra la información y registra su decisión.
- **Reglas del contexto (CONTEXTO_COSTFLOW.md):**
  - La ruta crítica tiene seguimiento y notificación más exigentes.
  - La app alerta cuando una propuesta está por vencer.
  - Cada cotización tiene versión (preliminar, corregida o final). Nunca se
    compara un documento desactualizado.
  - La IA no asume equivalencias técnicas sin evidencia o aprobación del
    especialista.
  - La IA interpreta y propone. Quien decide es el especialista.
- La matriz comparativa se llena en **la plantilla del usuario**, no en una
  nuestra. Los datos que no están en la cotización quedan vacíos: nunca se
  inventan ni se adivinan.
- **Arquitectura:** n8n orquesta los flujos (`n8n/`). La IA interpreta
  (`prompts/`, `app/lectura/`). PostgreSQL/Supabase guarda estados y trazabilidad
  (`db/`). Supabase Storage guarda los archivos. Gmail API maneja el correo.
  Excel es la entrada y la salida.
- **Módulos de `app/`:** `entradas/` (1), `correo/` (3), `recepcion/` (4),
  `lectura/` (5), `homologacion/` (6), `aclaraciones/` (7 y 8),
  `comparativo/` (9), `modelo.py` (formato común). La interfaz vive en `frontend/` (HTML y JavaScript).
- **Otras carpetas:** `n8n/` (flujos), `db/` (esquema), `prompts/` (instrucciones
  de la IA), `plantillas/` (Excel), `ejemplos/` (caso de prueba), `docs/`,
  `scripts/`, `tests/`.
