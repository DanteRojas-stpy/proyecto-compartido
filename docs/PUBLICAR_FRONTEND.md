# Publicar únicamente el frontend con Netlify

Netlify entrega las pantallas HTML, CSS y JavaScript. Nhost conserva los datos y
los archivos; n8n y el servicio de E3 siguen ejecutándose donde estén
instalados. Esta publicación no ejecuta migraciones ni despliega esos servicios.

## Activación inicial (una sola vez)

1. Entrar a `https://app.netlify.com` con la cuenta del equipo.
2. **Add new site → Import an existing project → GitHub** y autorizar el acceso a
   `DanteRojas-stpy/proyecto-compartido`. Funciona con repositorios privados.
3. Elegir la rama `main`. Netlify lee `netlify.toml`, así que no hay que escribir
   comandos: ejecuta `python3 scripts/preparar_frontend_pages.py` y publica `_site`.
4. Pulsar **Deploy**. Al terminar, Netlify muestra la dirección, por ejemplo
   `https://nombre-aleatorio.netlify.app`. Se puede cambiar en **Site configuration →
   Change site name**.

## Qué publica y cómo se actualiza

`scripts/preparar_frontend_pages.py` copia solamente `frontend/index.html`,
`frontend/css/`, `frontend/js/` y `frontend/assets/` (si existe) a `_site/`.
Nunca publica la raíz del repositorio ni los Excel.

Se excluye el `config.local.js` de la computadora y se genera uno con los
identificadores públicos del proyecto `costflow-dev`: subdominio
`zgorsmkvfyytsouacrpa` y región `sa-east-1` (variables en `netlify.toml`). No
necesita secretos administrativos, contraseñas ni claves de modelos de IA.

Cada fusión en `main` actualiza el sitio. Los Pull Requests generan una vista
previa propia que Netlify muestra en el PR. El flujo de GitHub
`Comprobar frontend` solo verifica que el paquete se arma y que el JavaScript es
válido.

## Conexiones que se deben comprobar tras publicar

- **CORS de la Function:** añadir la dirección de Netlify a `CORS_ORIGINS` en las
  variables de Nhost, separada por comas y conservando los orígenes locales
  (`http://localhost:8000,http://127.0.0.1:8000,https://<sitio>.netlify.app`).
  Redesplegar la Function. Sin esto, "aceptada como final" falla desde la web
  publicada. Las vistas previas de PR tienen otra dirección y no están permitidas.
- **Nhost Auth:** si el inicio de sesión usa redirecciones, autorizar la dirección
  en **Authentication → URL Configuration**.
- Si alguna acción utiliza una dirección `localhost` de n8n, seguirá necesitando
  una dirección HTTPS accesible para usuarios de otras computadoras.

Publicar las pantallas no certifica esas conexiones. La prueba de acceso y
decisiones requiere una sesión real y datos de prueba autorizados.
