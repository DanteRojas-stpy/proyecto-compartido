# Interfaz del especialista

Pantallas de CostFlow en HTML, CSS y JavaScript. Se abren en el navegador.

- `index.html`: página principal de la interfaz.
- `css/`: estilos.
- `js/`: lógica de las pantallas.
- `assets/`: logos e imágenes.

Las pantallas no procesan cotizaciones: piden datos a Python y n8n, y muestran
los resultados al especialista. Un cambio de diseño no debe tocar la lógica de `app/`.

## Ejecutar E1 en esta computadora

1. Aplica en Nhost los archivos de `db/nhost/` en el orden indicado por su
   número y configura la metadata descrita en `db/nhost/README.md`.
2. Copia `js/config.example.js` como `js/config.local.js`.
3. Completa en `config.local.js` el subdominio y la región públicos del proyecto
   Nhost. Nunca coloques allí el secreto de administrador.
4. En Windows, ejecuta `scripts\iniciar_frontend.cmd`. En otros sistemas,
   ejecuta `python -m http.server 8000` desde `frontend/`.
5. Abre `http://localhost:8000` si el navegador no se abre automáticamente.

La cuenta usada para administrar Nhost no es una cuenta de la aplicación. En
la pantalla de CostFlow, usa **Crear cuenta** una vez o crea un usuario desde
**Nhost > Auth > Users**.

El formulario crea una solicitud en estado `borrador`, registra sus proveedores,
sube los Excel al bucket `solicitudes` y cambia el estado a `lista` al
terminar. Si algo falla, conserva el borrador para poder diagnosticarlo.
