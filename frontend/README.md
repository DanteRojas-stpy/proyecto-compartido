# Interfaz del especialista

Pantallas de CostFlow en HTML, CSS y JavaScript. Se abren en el navegador.

- `index.html`: página principal de la interfaz.
- `css/`: estilos.
- `js/`: lógica de las pantallas.
- `assets/`: logos e imágenes.

Las pantallas no procesan cotizaciones: piden datos a Python y n8n, y muestran
los resultados al especialista. Un cambio de diseño no debe tocar la lógica de `app/`.

## Ejecutar E1 en esta computadora

1. Aplica `db/migraciones/001_e1_registro_solicitud.sql` al proyecto de Supabase.
2. Copia `js/config.example.js` como `js/config.local.js`.
3. Completa en `config.local.js` la URL y la clave pública de Supabase. La clave
   `service_role` y la contraseña de PostgreSQL nunca van aquí.
4. En Supabase Auth, agrega `http://localhost:8000` a las URL permitidas para el
   desarrollo local.
5. En Windows, ejecuta `scripts\iniciar_frontend.cmd`. En otros sistemas,
   ejecuta `python -m http.server 8000` desde `frontend/`.
6. Abre `http://localhost:8000` si el navegador no se abre automáticamente.

El formulario crea una solicitud en estado `borrador`, registra sus proveedores,
sube los Excel al bucket privado `solicitudes` y cambia el estado a `lista` al
terminar. Si algo falla, conserva el borrador para poder diagnosticarlo.
