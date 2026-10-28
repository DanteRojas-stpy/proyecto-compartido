# Publicar únicamente el frontend

GitHub Pages entrega las pantallas HTML, CSS y JavaScript. Nhost conserva los
datos y los archivos; n8n y el servicio de E3 siguen ejecutándose donde estén
instalados. Esta publicación no ejecuta migraciones ni despliega esos servicios.

## Activación inicial por el dueño del repositorio

1. El repositorio es privado. Comprobar que la cuenta o plan permite GitHub Pages
   para repositorios privados. No es necesario hacer público el repositorio.
2. En GitHub, abrir **Settings → Pages → Build and deployment → Source** y elegir
   **GitHub Actions**. Requiere permiso de administrador o mantenedor.
3. Fusionar el Pull Request de publicación del frontend en `main` cuando sus
   comprobaciones estén correctas.
4. En **Actions → Publicar frontend**, esperar a que termine la publicación. Si
   Pages se habilitó después de la fusión, elegir **Run workflow** sobre `main`.
5. Copiar la dirección mostrada por GitHub Pages. Abrirla y comprobar el acceso
   con una cuenta de la aplicación. La contraseña se introduce solamente en la web.

La dirección esperada, si GitHub no aplica una dirección diferente al proyecto,
es `https://danterojas-stpy.github.io/proyecto-compartido/`.

El sitio puede ser público aunque el repositorio sea privado. La pantalla de
acceso no sustituye los permisos de Nhost: cada consulta conserva el rol `user`
y los permisos existentes. No se publican cotizaciones ni datos de usuarios
en el paquete estático.

## Qué publica y cómo se actualiza

El flujo `.github/workflows/publicar-frontend.yml` prepara solamente
`frontend/index.html`, `frontend/css/`, `frontend/js/` y `frontend/assets/`
(si existe). Nunca publica la raíz completa del repositorio.

Se excluye `config.local.js` de la computadora y se genera uno nuevo con los
identificadores públicos del proyecto `costflow-dev`: subdominio
`zgorsmkvfyytsouacrpa` y región `sa-east-1`. Si se usa otro proyecto, configurar
las variables de GitHub Actions `NHOST_SUBDOMAIN` y `NHOST_REGION`.
No necesita secretos administrativos, contraseñas ni claves de Gemini.

Cada fusión en `main` que cambie el frontend o su publicación actualiza el sitio.
Los Pull Requests solo comprueban el paquete; no publican versiones de prueba.
También se puede ejecutar manualmente desde Actions, siempre sobre `main`.

## Conexiones que se deben comprobar

- Inicio de sesión y consultas de Nhost desde la dirección HTTPS publicada.
- Si Nhost solicita verificar el correo o usa redirecciones de autenticación,
  autorizar esa dirección en su configuración de autenticación.
- La aceptación final llama a `e3-operar` con la sesión del especialista.
  Comprobar que el origen HTTPS está permitido en `CORS_ORIGINS` de la función.
  Mantener los orígenes locales que el equipo todavía necesite.
- Si alguna acción utiliza una dirección `localhost` de n8n, seguirá necesitando
  una dirección HTTPS accesible para usuarios de otras computadoras.

Habilitar Pages y publicar las pantallas no certifica esas conexiones. La prueba
de acceso y decisiones requiere una sesión real y datos de prueba autorizados.
