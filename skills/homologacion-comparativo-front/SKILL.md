---
name: homologacion-comparativo-front
description: Conectar el front de CostFlow con Nhost para mostrar propuestas de homologación (E4) y generar el comparativo en Python (E5), en un proyecto de pruebas y sin tocar el front de main.
---

**Rol y/o Audiencia:**
Eres un Senior Full-Stack Engineer especializado en Nhost, GraphQL y automatización con n8n. Trabajas sobre el repositorio de CostFlow y tu entrega es una rama de pruebas revisable, no un cambio en `main`.

**Contexto:**
- El front (`frontend/`) escribe y lee en Nhost con GraphQL y Storage. No llama a n8n directamente.
- Nhost avisa a n8n mediante eventos. n8n lee y escribe en Nhost.
- E4 (homologación) lee las versiones finales de Nhost, propone la homologación con el modelo local y **hoy no guarda nada**.
- E5 (comparativo) es `app/comparativo/` en Python. Hoy lee Excel locales y escribe un Excel local; no está conectado a Nhost.
- Las cotizaciones extraídas por el flujo E3 (Juan) ya están en el bucket `cotizaciones` de Nhost.
- Las reglas de negocio están en `docs/CONTEXTO_COSTFLOW.md` y `docs/PLAN.md`. Las decisiones del equipo en `docs/DECISIONES.md`.

**Objetivo:**
Dejar, en una rama nueva, la conexión mínima que permita:
1. Ver en el front las propuestas de homologación que produce E4, para revisión.
2. Pedir desde el front la generación del comparativo, y que E5 deje el Excel en el bucket `cotizaciones` con su enlace de descarga.

**Entorno permitido:**
- Usa solo un proyecto de Nhost de **pruebas**. Nunca el proyecto de trabajo ni `main`.
- Las variables del proyecto de pruebas (URL de GraphQL, URL de Storage) van en `frontend/js/config.local.js`, que ya está ignorado por git.
- Nunca escribas claves, secretos ni tokens en el código, en los flujos ni en el repositorio. Las credenciales se referencian con marcadores `REEMPLAZAR_`.

**Trabajo:**

1. Crea la rama `<usuario>/conexion-nhost-e4-e5` desde `main` actualizado.
2. Migración nueva en `db/migraciones/010_...sql`, numerada después de la última existente:
   - tabla de propuestas de homologación (por solicitud, partida y proveedor; valores originales y normalizados; estado de revisión; evidencia);
   - tabla de comparativos (solicitud, estado `pendiente`, `procesando`, `listo`, `error`, enlace al Storage, fecha);
   - permisos mínimos para el rol `user`, según lo que ya usa `scripts/configurar_nhost.py`.
   - Actualiza `db/migraciones/README.md`.
3. Front (`frontend/`): cambios **mínimos y aditivos**.
   - Una pantalla o sección "Propuestas de homologación" que lea la tabla de propuestas y permita marcar cada una como aprobada o rechazada.
   - Un botón "Generar comparativo" que inserte una fila en la tabla de comparativos con estado `pendiente`.
   - Una lista de comparativos con su estado y, si está `listo`, el enlace de descarga.
   - No cambies la autenticación ni el flujo de carga de cotizaciones que ya funciona.
4. Flujos n8n:
   - E4: que guarde cada propuesta en la tabla de propuestas, con estado `pendiente`. Nunca cambia la solicitud.
   - E5: un disparador de Nhost sobre la tabla de comparativos (estado `pendiente`) que ejecute `python -m app.comparativo`, suba el Excel al bucket `cotizaciones` y actualice la fila a `listo` con su ruta. Si falla, `error` con el motivo.
   - Las rutas locales de Python y de la plantilla se leen de variables del flujo, no están escritas en el archivo.
5. Pruebas:
   - `pytest` debe pasar.
   - `node --check frontend/js/app.js` debe pasar.
   - Añade pruebas para la lógica nueva que se pueda probar sin Nhost.
6. Entrega: Pull Request contra `main`, **sin fusionar**. La descripción debe incluir:
   - qué tablas y permisos se agregan;
   - cómo probarlo en el proyecto de pruebas, paso a paso;
   - qué archivos de Rodrigo se tocaron (idealmente ninguno).

**Límites:**
- No modifiques `main` directamente.
- No cambies los flujos de envío, de lectura de E3 ni de seguimiento: son de otras personas.
- No cambies `app/comparativo/` salvo para corregir un error encontrado en las pruebas.
- Si una decisión de negocio no está en `docs/CONTEXTO_COSTFLOW.md` (por ejemplo, el tipo de cambio o la regla de homologación), déjala pendiente y anótala en la descripción del PR. No la inventes.
- Si una migración o un permiso afecta al proyecto de trabajo, no lo apliques ahí: anótalo para revisión.
