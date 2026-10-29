# Interfaz del especialista

Pantallas de CostFlow en HTML, CSS y JavaScript. Se abren en el navegador.

- `index.html`: página principal de la interfaz.
- `css/`: estilos.
- `js/`: lógica de las pantallas.
- `assets/`: logos e imágenes.

Las pantallas no procesan cotizaciones: piden datos a Python y n8n, y muestran
los resultados al especialista. Un cambio de diseño no debe tocar la lógica de `app/`.

## Ejecutar E1 en esta computadora

1. Aplica en Nhost los archivos de `db/migraciones/` en el orden indicado por su
   número y configura la metadata descrita en `db/migraciones/README.md`.
2. Copia `js/config.example.js` como `js/config.local.js`.
3. Completa en `config.local.js` el subdominio y la región públicos del proyecto
   Nhost. Nunca coloques allí el secreto de administrador.
4. En Windows, ejecuta `scripts\iniciar_frontend.cmd`. En otros sistemas,
   ejecuta `python -m http.server 8000` desde `frontend/`.
5. Abre `http://localhost:8000` si el navegador no se abre automáticamente.

La cuenta usada para administrar Nhost no es una cuenta de la aplicación. En
la pantalla de CostFlow, usa **Crear cuenta** una vez o crea un usuario desde
**Nhost > Auth > Users**.

Después de ingresar, la página inicial muestra todos los proyectos de la cuenta
como tarjetas con la cantidad de solicitudes activas y críticas. Desde **Nuevo
proyecto** se conserva el formulario de registro existente. Al abrir una tarjeta
se accede al seguimiento del proyecto y a la acción **Nueva solicitud**.

El código sugerido se muestra en pantalla y PostgreSQL asigna
el definitivo al guardar, con correlativos separados por proyecto y por tipo
de cotización (`MA` para materiales y `SC` para subcontratas), ambos con tres
dígitos mínimos. La fecha de inicio se toma automáticamente al crear; el
especialista selecciona la fecha fin y si la partida es crítica. Para ello
deben estar aplicados `db/migraciones/004_proyectos_y_correlativos.sql`,
`db/migraciones/005_fechas_y_partida_critica.sql` y los permisos nuevos.
Al abrir un proyecto, el front agrupa la información en un acordeón por solicitud.
El resumen muestra fecha, criticidad y cantidades de proveedores, respuestas y
proveedores con documentos. Al expandirlo aparece el historial completo de
correos de cada proveedor, su contenido, adjuntos y estado. n8n propone si el
correo contiene cotización o ficha técnica; el especialista confirma o cambia
ese estado mediante **Guardar estado** y la decisión queda auditada en Nhost. Las
notificaciones persistentes se muestran al final del proyecto. El
especialista puede registrar una **Coordinación**, resolver aclaraciones y
cerrar una solicitud cuando ya existe
su cuadro comparativo vigente. Las notificaciones nuevas llegan mediante una
suscripción GraphQL, con actualización de respaldo cada 30 segundos.

El formulario crea una solicitud en estado `inicio`, busca cada proveedor por
RUC o correo y reutiliza su ficha si ya existe. El mismo proveedor puede quedar
vinculado con varias solicitudes, incluso de proyectos distintos. Después sube
los Excel al bucket `solicitudes` y activa `preparada_para_envio` al terminar.
El envío de correos no cambia el estado de negocio.

## Homologación (E4)

Cada solicitud muestra un bloque «Homologación (E4)» con el estado, el botón **Homologar** y, cuando hay resultado,
**Ver resultado** y **Descargar JSON**.

- El botón se habilita cuando la solicitud tiene al menos una cotización aceptada como final. Llama a la Function
  `e4-operar` con la sesión del especialista; n8n hace el trabajo y se avisa al terminar. Mientras tanto la
  tarjeta se actualiza sola.
- La lógica de pantalla (qué mostrar y qué habilitar) está en `js/e4.js`, sin acceso al DOM, y se prueba con Node
  en `tests/etapa4/front_e4.test.mjs`.
- Si la migración 017 o sus permisos no están aplicados, el bloque no aparece y el resto de la pantalla funciona igual.
