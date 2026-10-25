# Registro de decisiones

Aquí se anotan las decisiones del equipo que cambian la arquitectura o las reglas
del proyecto. Cada una tiene fecha, quién la tomó y por qué.

## 2026-10-25: base de datos y servicios en Nhost

**Decisión:** la base de datos, la autenticación, el almacenamiento de archivos y la
API GraphQL se alojan en **Nhost** (PostgreSQL + Auth + Storage + Hasura).

**Quién:** Dante Rojas, con el equipo.

**Por qué:** el trabajo de E1 (Rodrigo) ya está construido sobre Nhost, con
migraciones, permisos y el flujo de envío de solicitudes en n8n.

**Qué cambia:**
- Las migraciones SQL viven solo en `db/migraciones/`, en orden numerado.
- Los archivos de cotizaciones se guardan en Nhost Storage, no en Supabase Storage.
- n8n se conecta a la API de Nhost.
- Los permisos se aplican con `scripts/configurar_nhost.py`.

**Qué no cambia:** las reglas de negocio (procesos, estados, versiones, alcance)
siguen igual que en `docs/CONTEXTO_COSTFLOW.md`.

**Pendiente:** `docs/CONTEXTO_COSTFLOW.md` es el documento original del MVP y
todavía menciona Supabase. No se edita, porque es la referencia acordada con el
especialista. Si cambia la arquitectura de forma más profunda, se revisa en un
nuevo registro.
