import { createClient } from "https://esm.sh/@nhost/nhost-js@4.9.0";
import { createClient as createSubscriptionClient } from "https://esm.sh/graphql-ws@5.16.2";

const ui = {
  configuracion: document.querySelector("#configuracion"),
  acceso: document.querySelector("#acceso"),
  registro: document.querySelector("#registro"),
  solicitudes: document.querySelector("#solicitudes"),
  formProyecto: document.querySelector("#form-proyecto"),
  resultadoProyecto: document.querySelector("#resultado-proyecto"),
  proyectoId: document.querySelector("#proyecto-id"),
  proyectoCodigo: document.querySelector("#proyecto-codigo"),
  proyectoNombre: document.querySelector("#proyecto-nombre"),
  tipoSolicitud: document.querySelector("#tipo-solicitud"),
  codigoSugerido: document.querySelector("#codigo-sugerido"),
  fechaInicio: document.querySelector("#fecha-inicio"),
  fechaLimite: document.querySelector("#fecha-limite"),
  estadoSolicitudes: document.querySelector("#estado-solicitudes"),
  seguimientoProveedores: document.querySelector("#seguimiento-proveedores"),
  notificaciones: document.querySelector("#notificaciones"),
  contadorNotificaciones: document.querySelector("#contador-notificaciones"),
  dialogoCoordinacion: document.querySelector("#dialogo-coordinacion"),
  formCoordinacion: document.querySelector("#form-coordinacion"),
  proveedorCoordinacion: document.querySelector("#proveedor-coordinacion"),
  cancelarCoordinacion: document.querySelector("#cancelar-coordinacion"),
  formAcceso: document.querySelector("#form-acceso"),
  crearCuenta: document.querySelector("#crear-cuenta"),
  cerrarSesion: document.querySelector("#cerrar-sesion"),
  usuarioActivo: document.querySelector("#usuario-activo"),
  formSolicitud: document.querySelector("#form-solicitud"),
  proveedores: document.querySelector("#proveedores"),
  agregarProveedor: document.querySelector("#agregar-proveedor"),
  plantillaProveedor: document.querySelector("#plantilla-proveedor"),
  resultado: document.querySelector("#resultado"),
  guardarSolicitud: document.querySelector("#guardar-solicitud"),
};

let nhost;
let proyectosDisponibles = [];
let configuracionNhost;
let clienteSuscripcion;
let detenerSuscripcion;
let intervaloNotificaciones;
const opcionesRolUsuario = { headers: { "x-hasura-role": "user" } };

const etiquetasRespuesta = {
  no_envio_cotizacion: "No envió cotización",
  envio_cotizacion_con_aclaracion: "Envió cotización con aclaración",
  envio_cotizacion: "Envió cotización",
};

const etiquetasDetalle = {
  sin_respuesta: "Sin respuesta",
  confirmo_recepcion: "Confirmó recepción",
  consulta_previa: "Realizó una consulta previa",
  rechazo_participar: "Rechazó participar",
  aclaraciones_pendientes: "Tiene aclaraciones pendientes",
  cotizacion_definitiva: "Cotización definitiva",
  tres_coordinaciones: "Excluido después de tres coordinaciones",
  plazo_vencido: "Excluido por vencimiento del plazo",
};

function mostrarResultado(mensaje, tipo = "") {
  ui.resultado.textContent = mensaje;
  ui.resultado.className = `resultado ${tipo}`;
}

function mensajeError(error) {
  const codigo = typeof error?.body?.error === "string"
    ? error.body.error
    : error?.body?.error?.message;
  const mensajesAuth = {
    "schema-validation-error": "Nhost rechazó el correo o la contraseña. Usa un correo válido y una contraseña de 8 a 50 caracteres.",
    "email-already-in-use": "Ese correo ya tiene una cuenta. Pulsa Ingresar en lugar de Crear cuenta.",
    "invalid-email-password": "El correo o la contraseña son incorrectos.",
    "user-not-found": "No existe una cuenta con ese correo. Pulsa Crear cuenta primero.",
  };
  if (mensajesAuth[codigo]) return mensajesAuth[codigo];
  const erroresGraphql = error?.body?.errors;
  if (Array.isArray(erroresGraphql)) return erroresGraphql.map((item) => item.message).join(". ");
  return error?.body?.error?.message || error?.message || "Ocurrió un error inesperado.";
}

function limpiar(valor) {
  const texto = String(valor ?? "").trim();
  return texto || null;
}

function nombreSeguro(nombre) {
  return nombre
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9._-]/g, "-")
    .replace(/-+/g, "-")
    .toLowerCase();
}

function validarExcel(archivo, tipo) {
  const extensionValida = /\.(xlsx|xls)$/i.test(archivo.name);
  if (!extensionValida) throw new Error(`El archivo ${tipo} debe ser Excel (.xlsx o .xls).`);
  if (archivo.size > 50 * 1024 * 1024) throw new Error(`El archivo ${tipo} supera 50 MB.`);
}

function mimeExcel(archivo) {
  if (archivo.type) return archivo.type;
  return archivo.name.toLowerCase().endsWith(".xls")
    ? "application/vnd.ms-excel"
    : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
}

function agregarProveedor() {
  const fragmento = ui.plantillaProveedor.content.cloneNode(true);
  const fila = fragmento.querySelector(".proveedor");
  fila.querySelector(".quitar-proveedor").addEventListener("click", () => {
    if (ui.proveedores.children.length > 1) fila.remove();
  });
  ui.proveedores.append(fragmento);
}

function leerProveedores() {
  return [...ui.proveedores.querySelectorAll(".proveedor")].map((fila) => {
    const valor = (campo) => limpiar(fila.querySelector(`[data-campo="${campo}"]`).value);
    return {
      nombre: valor("nombre"),
      ruc: valor("ruc"),
      correo: valor("correo")?.toLowerCase() ?? null,
      contacto: valor("contacto"),
      telefono: valor("telefono"),
    };
  });
}

function mostrarSesion(session) {
  const conectado = Boolean(session?.user);
  ui.acceso.classList.toggle("oculto", conectado);
  ui.registro.classList.toggle("oculto", !conectado);
  ui.solicitudes.classList.toggle("oculto", !conectado);
  ui.cerrarSesion.classList.toggle("oculto", !conectado);
  ui.usuarioActivo.textContent = conectado ? session.user.email : "";
  if (conectado) {
    cargarProyectos().catch((error) => mostrarResultado(mensajeError(error), "error"));
    iniciarNotificacionesEnTiempoReal();
  } else {
    detenerNotificacionesEnTiempoReal();
    ui.proyectoId.replaceChildren();
  }
}

async function graphql(query, variables = {}) {
  const respuesta = await nhost.graphql.request({ query, variables }, opcionesRolUsuario);
  if (respuesta.body.errors?.length) {
    throw new Error(respuesta.body.errors.map((item) => item.message).join(". "));
  }
  return respuesta.body.data;
}

async function configurarNhost() {
  try {
    const config = await import("./config.local.js");
    if (!config.NHOST_SUBDOMAIN || !config.NHOST_REGION) throw new Error("Configuración incompleta");
    configuracionNhost = config;
    nhost = createClient({ subdomain: config.NHOST_SUBDOMAIN, region: config.NHOST_REGION });
    mostrarSesion(nhost.getUserSession());
    nhost.sessionStorage.onChange((session) => mostrarSesion(session));
  } catch (_error) {
    ui.configuracion.classList.remove("oculto");
    ui.configuracion.textContent = "Falta frontend/js/config.local.js. Copia config.example.js y completa el subdominio y la región de Nhost.";
    ui.acceso.classList.add("oculto");
  }
}

async function autenticar(crear = false) {
  const email = document.querySelector("#correo-acceso").value.trim();
  const password = document.querySelector("#clave-acceso").value;
  if (password.length < 8 || password.length > 50) {
    throw new Error("La contraseña debe tener entre 8 y 50 caracteres.");
  }
  const respuesta = crear
    ? await nhost.auth.signUpEmailPassword({ email, password })
    : await nhost.auth.signInEmailPassword({ email, password });
  if (crear && !respuesta.body.session) alert("Revisa tu correo para confirmar la cuenta antes de ingresar.");
}

async function cargarProyectos(seleccionarId = ui.proyectoId.value) {
  const respuesta = await graphql(`query ProyectosDisponibles {
    proyectos(order_by: { codigo: asc }) { id codigo nombre }
  }`);
  proyectosDisponibles = respuesta.proyectos;
  ui.proyectoId.replaceChildren(new Option("Selecciona un proyecto", ""));
  for (const proyecto of respuesta.proyectos) {
    ui.proyectoId.add(new Option(`${proyecto.codigo} — ${proyecto.nombre}`, proyecto.id));
  }
  if (respuesta.proyectos.some((proyecto) => proyecto.id === seleccionarId)) ui.proyectoId.value = seleccionarId;
  ui.guardarSolicitud.disabled = !ui.proyectoId.value;
  mostrarProyectoSeleccionado();
  await actualizarCodigoSugerido();
  await cargarEstadoSolicitudes();
  await cargarSeguimientoProveedores();
  await cargarNotificaciones();
}

function mostrarProyectoSeleccionado() {
  const proyecto = proyectosDisponibles.find((item) => item.id === ui.proyectoId.value);
  ui.proyectoCodigo.value = proyecto?.codigo ?? "";
  ui.proyectoNombre.value = proyecto?.nombre ?? "";
}

function formatearFechaHora(valor) {
  if (!valor) return "Sin registro";
  return new Date(valor).toLocaleString("es-PE", {
    timeZone: "America/Lima",
    dateStyle: "short",
    timeStyle: "short",
  });
}

function abrirCoordinacion(participacion) {
  const form = ui.formCoordinacion.elements;
  form.solicitud_id.value = participacion.solicitud_id;
  form.proveedor_id.value = participacion.proveedor_id;
  form.medio.value = "correo";
  form.comentario.value = "";
  ui.proveedorCoordinacion.textContent = `${participacion.solicitud_cotizacion.codigo} — ${participacion.proveedor_asociado.nombre}`;
  ui.dialogoCoordinacion.showModal();
}

async function registrarCoordinacion(evento) {
  evento.preventDefault();
  const datos = new FormData(ui.formCoordinacion);
  try {
    await graphql(
      `mutation RegistrarCoordinacion($objeto: coordinaciones_proveedor_insert_input!) {
        insert_coordinaciones_proveedor_one(object: $objeto) { id }
      }`,
      {
        objeto: {
          solicitud_id: datos.get("solicitud_id"),
          proveedor_id: datos.get("proveedor_id"),
          medio: datos.get("medio"),
          comentario: datos.get("comentario").trim(),
        },
      },
    );
    ui.dialogoCoordinacion.close();
    mostrarResultado("Coordinación registrada correctamente.", "exito");
    await cargarSeguimientoProveedores();
    await cargarNotificaciones();
  } catch (error) {
    mostrarResultado(mensajeError(error), "error");
  }
}

async function corregirEstadoRespuesta(participacion, estado) {
  const detalle = {
    no_envio_cotizacion: "sin_respuesta",
    envio_cotizacion_con_aclaracion: "aclaraciones_pendientes",
    envio_cotizacion: "cotizacion_definitiva",
  }[estado];
  try {
    await graphql(
      `mutation CorregirEstadoProveedor(
        $solicitudId: uuid!, $proveedorId: uuid!, $estado: String!, $detalle: String!
      ) {
        update_solicitud_proveedores_by_pk(
          pk_columns: { solicitud_id: $solicitudId, proveedor_id: $proveedorId }
          _set: {
            estado_respuesta: $estado
            detalle_respuesta: $detalle
          }
        ) { solicitud_id estado_respuesta }
      }`,
      {
        solicitudId: participacion.solicitud_id,
        proveedorId: participacion.proveedor_id,
        estado,
        detalle,
      },
    );
    mostrarResultado("Clasificación corregida y registrada en el historial.", "exito");
    await cargarSeguimientoProveedores();
  } catch (error) {
    mostrarResultado(mensajeError(error), "error");
  }
}

async function resolverAclaracion(id) {
  try {
    await graphql(
      `mutation ResolverAclaracion($id: uuid!) {
        update_aclaraciones_proveedor_by_pk(
          pk_columns: { id: $id }
          _set: { estado: "resuelta" }
        ) { id estado resuelta_at }
      }`,
      { id },
    );
    mostrarResultado("Aclaración marcada como resuelta.", "exito");
    await cargarSeguimientoProveedores();
  } catch (error) {
    mostrarResultado(mensajeError(error), "error");
  }
}

async function cargarSeguimientoProveedores() {
  const proyectoId = ui.proyectoId.value;
  ui.seguimientoProveedores.replaceChildren();
  if (!proyectoId) return;
  const respuesta = await graphql(`query SeguimientoProveedores($id: uuid!) {
    solicitud_proveedores(
      where: { solicitud_cotizacion: { proyecto_id: { _eq: $id } } }
      order_by: { created_at: desc }
    ) {
      solicitud_id proveedor_id estado_respuesta detalle_respuesta considerado
      numero_coordinaciones ultimo_correo_at confianza_clasificacion
      proveedor_asociado { nombre correo }
      solicitud_cotizacion { codigo nombre estado fecha_limite }
    }
    aclaraciones_proveedor(
      where: {
        estado: { _eq: "abierta" }
        solicitud_cotizacion: { proyecto_id: { _eq: $id } }
      }
      order_by: { created_at: asc }
    ) { id solicitud_id proveedor_id descripcion created_at }
  }`, { id: proyectoId });
  if (ui.proyectoId.value !== proyectoId) return;
  const aclaracionesPorProveedor = new Map();
  for (const aclaracion of respuesta.aclaraciones_proveedor) {
    const clave = `${aclaracion.solicitud_id}:${aclaracion.proveedor_id}`;
    if (!aclaracionesPorProveedor.has(clave)) aclaracionesPorProveedor.set(clave, []);
    aclaracionesPorProveedor.get(clave).push(aclaracion);
  }

  for (const participacion of respuesta.solicitud_proveedores) {
    const tarjeta = document.createElement("article");
    tarjeta.className = `seguimiento-proveedor${participacion.considerado ? "" : " excluido"}`;
    const cabecera = document.createElement("div");
    cabecera.className = "seguimiento-cabecera";
    const identidad = document.createElement("div");
    const titulo = document.createElement("h3");
    titulo.textContent = `${participacion.solicitud_cotizacion.codigo} — ${participacion.proveedor_asociado.nombre}`;
    const correo = document.createElement("p");
    correo.className = "ayuda";
    correo.textContent = participacion.proveedor_asociado.correo || "Sin correo";
    identidad.append(titulo, correo);
    const estado = document.createElement("span");
    estado.className = `estado-respuesta${participacion.estado_respuesta === "no_envio_cotizacion" ? " pendiente" : ""}`;
    estado.textContent = etiquetasRespuesta[participacion.estado_respuesta];
    cabecera.append(identidad, estado);

    const detalle = document.createElement("p");
    detalle.textContent = `${etiquetasDetalle[participacion.detalle_respuesta]}. Coordinaciones: ${participacion.numero_coordinaciones}/3. Último correo: ${formatearFechaHora(participacion.ultimo_correo_at)}.`;
    tarjeta.append(cabecera, detalle);

    const claveParticipacion = `${participacion.solicitud_id}:${participacion.proveedor_id}`;
    const aclaraciones = aclaracionesPorProveedor.get(claveParticipacion) ?? [];
    if (aclaraciones.length) {
      const bloqueAclaraciones = document.createElement("div");
      bloqueAclaraciones.className = "aclaraciones-pendientes";
      const tituloAclaraciones = document.createElement("strong");
      tituloAclaraciones.textContent = "Aclaraciones pendientes";
      const lista = document.createElement("ul");
      for (const aclaracion of aclaraciones) {
        const item = document.createElement("li");
        const texto = document.createElement("span");
        texto.textContent = aclaracion.descripcion;
        const resolver = document.createElement("button");
        resolver.type = "button";
        resolver.className = "secundario compacto";
        resolver.textContent = "Resolver";
        resolver.addEventListener("click", () => resolverAclaracion(aclaracion.id));
        item.append(texto, resolver);
        lista.append(item);
      }
      bloqueAclaraciones.append(tituloAclaraciones, lista);
      tarjeta.append(bloqueAclaraciones);
    }

    if (participacion.considerado && participacion.solicitud_cotizacion.estado === "inicio") {
      const acciones = document.createElement("div");
      acciones.className = "seguimiento-acciones";
      if (participacion.estado_respuesta !== "envio_cotizacion") {
        const botonCoordinacion = document.createElement("button");
        botonCoordinacion.type = "button";
        botonCoordinacion.className = "secundario";
        botonCoordinacion.textContent = "Coordinación";
        botonCoordinacion.addEventListener("click", () => abrirCoordinacion(participacion));
        acciones.append(botonCoordinacion);
      }

      const etiquetaSelector = document.createElement("label");
      etiquetaSelector.textContent = "Corrección del usuario";
      const selector = document.createElement("select");
      for (const [valor, etiqueta] of Object.entries(etiquetasRespuesta)) {
        selector.add(new Option(etiqueta, valor, false, valor === participacion.estado_respuesta));
      }
      etiquetaSelector.append(selector);
      const botonCorregir = document.createElement("button");
      botonCorregir.type = "button";
      botonCorregir.className = "secundario";
      botonCorregir.textContent = "Guardar corrección";
      botonCorregir.addEventListener("click", () => corregirEstadoRespuesta(participacion, selector.value));
      acciones.append(etiquetaSelector, botonCorregir);
      tarjeta.append(acciones);
    }
    ui.seguimientoProveedores.append(tarjeta);
  }

  if (!ui.seguimientoProveedores.children.length) {
    const vacio = document.createElement("p");
    vacio.textContent = "No hay proveedores vinculados a solicitudes de este proyecto.";
    ui.seguimientoProveedores.append(vacio);
  }
}

function renderizarNotificaciones(notificaciones) {
  ui.notificaciones.replaceChildren();
  const pendientes = notificaciones.filter((item) => item.estado === "no_leida").length;
  ui.contadorNotificaciones.textContent = `${pendientes} pendiente${pendientes === 1 ? "" : "s"}`;
  for (const notificacion of notificaciones) {
    const item = document.createElement("li");
    item.className = `notificacion ${notificacion.estado.replaceAll("_", "-")}`;
    const titulo = document.createElement("h3");
    titulo.textContent = notificacion.titulo;
    const mensaje = document.createElement("p");
    mensaje.textContent = notificacion.mensaje;
    const fecha = document.createElement("time");
    fecha.dateTime = notificacion.created_at;
    fecha.textContent = formatearFechaHora(notificacion.created_at);
    const acciones = document.createElement("div");
    acciones.className = "acciones";
    if (notificacion.estado === "no_leida") {
      const leer = document.createElement("button");
      leer.type = "button";
      leer.className = "secundario";
      leer.textContent = "Marcar como leída";
      leer.addEventListener("click", () => actualizarNotificacion(notificacion.id, "leida"));
      acciones.append(leer);
    }
    if (notificacion.estado !== "atendida") {
      const atender = document.createElement("button");
      atender.type = "button";
      atender.textContent = "Marcar como atendida";
      atender.addEventListener("click", () => actualizarNotificacion(notificacion.id, "atendida"));
      acciones.append(atender);
    }
    item.append(titulo, mensaje, fecha, acciones);
    ui.notificaciones.append(item);
  }
  if (!notificaciones.length) {
    const vacio = document.createElement("li");
    vacio.textContent = "No hay notificaciones para este proyecto.";
    ui.notificaciones.append(vacio);
  }
}

async function cargarNotificaciones() {
  const proyectoId = ui.proyectoId.value;
  if (!proyectoId) {
    renderizarNotificaciones([]);
    return;
  }
  const respuesta = await graphql(`query NotificacionesProyecto($id: uuid!) {
    notificaciones(
      where: { solicitud_cotizacion: { proyecto_id: { _eq: $id } } }
      order_by: { created_at: desc }
      limit: 50
    ) { id tipo titulo mensaje estado datos created_at }
  }`, { id: proyectoId });
  if (ui.proyectoId.value === proyectoId) renderizarNotificaciones(respuesta.notificaciones);
}

async function actualizarNotificacion(id, estado) {
  try {
    await graphql(
      `mutation ActualizarNotificacion($id: uuid!, $estado: String!) {
        update_notificaciones_by_pk(pk_columns: { id: $id }, _set: { estado: $estado }) {
          id estado
        }
      }`,
      { id, estado },
    );
    await cargarNotificaciones();
  } catch (error) {
    mostrarResultado(mensajeError(error), "error");
  }
}

function detenerNotificacionesEnTiempoReal() {
  if (detenerSuscripcion) detenerSuscripcion();
  detenerSuscripcion = undefined;
  if (clienteSuscripcion) clienteSuscripcion.dispose();
  clienteSuscripcion = undefined;
  if (intervaloNotificaciones) clearInterval(intervaloNotificaciones);
  intervaloNotificaciones = undefined;
}

function iniciarNotificacionesEnTiempoReal() {
  detenerNotificacionesEnTiempoReal();
  const session = nhost?.getUserSession();
  if (!session?.accessToken || !configuracionNhost) return;
  const endpoint = `wss://${configuracionNhost.NHOST_SUBDOMAIN}.graphql.${configuracionNhost.NHOST_REGION}.nhost.run/v1`;
  clienteSuscripcion = createSubscriptionClient({
    url: endpoint,
    connectionParams: () => ({
      headers: {
        authorization: `Bearer ${nhost.getUserSession()?.accessToken}`,
        "x-hasura-role": "user",
      },
    }),
    retryAttempts: Infinity,
  });
  detenerSuscripcion = clienteSuscripcion.subscribe(
    {
      query: `subscription NotificacionesEnTiempoReal {
        notificaciones(order_by: { created_at: desc }, limit: 50) {
          id tipo titulo mensaje estado datos created_at
        }
      }`,
    },
    {
      next: (resultado) => {
        if (resultado.errors?.length) return;
        const proyectoSeleccionado = ui.proyectoId.value;
        if (!proyectoSeleccionado) return;
        cargarNotificaciones().catch(() => {});
      },
      error: () => {},
      complete: () => {},
    },
  );
  intervaloNotificaciones = setInterval(() => {
    cargarNotificaciones().catch(() => {});
    cargarSeguimientoProveedores().catch(() => {});
  }, 30000);
}

async function cerrarSolicitud(solicitud) {
  const confirmado = window.confirm(
    `¿Cerrar ${solicitud.codigo} — ${solicitud.nombre}? Esta acción requiere un cuadro comparativo vigente y no se puede deshacer.`,
  );
  if (!confirmado) return;
  try {
    const respuesta = await graphql(
      `mutation CerrarSolicitud($id: uuid!) {
        update_solicitudes_cotizacion_by_pk(
          pk_columns: { id: $id }
          _set: { estado: "cerrado" }
        ) { id estado }
      }`,
      { id: solicitud.id },
    );
    if (!respuesta.update_solicitudes_cotizacion_by_pk) {
      throw new Error("No se pudo cerrar la solicitud.");
    }
    mostrarResultado(`Solicitud ${solicitud.codigo} cerrada correctamente.`, "exito");
    await cargarEstadoSolicitudes();
    await cargarSeguimientoProveedores();
  } catch (error) {
    mostrarResultado(mensajeError(error), "error");
  }
}

async function cargarEstadoSolicitudes() {
  const proyectoId = ui.proyectoId.value;
  ui.estadoSolicitudes.replaceChildren();
  if (!proyectoId) return;
  const respuesta = await graphql(`query EstadoSolicitudes($id: uuid!) {
    solicitudes_cotizacion(
      where: { proyecto_id: { _eq: $id } }
      order_by: { created_at: desc }
    ) { id codigo nombre fecha_limite estado preparada_para_envio }
  }`, { id: proyectoId });
  if (ui.proyectoId.value !== proyectoId) return;
  const etiquetas = {
    inicio: "Inicio",
    cerrado: "Cerrado",
    cerrado_sin_proveedores: "Cerrado sin proveedores",
  };
  for (const solicitud of respuesta.solicitudes_cotizacion) {
    const item = document.createElement("li");
    item.className = "solicitud-inicio";
    const detalle = document.createElement("div");
    const nombre = document.createElement("p");
    nombre.textContent = `${solicitud.codigo} — ${solicitud.nombre} · Fecha fin: ${solicitud.fecha_limite}`;
    const estado = document.createElement("span");
    estado.className = "estado-solicitud";
    estado.textContent = etiquetas[solicitud.estado] ?? solicitud.estado;
    detalle.append(nombre, estado);
    item.append(detalle);
    if (solicitud.estado === "inicio" && solicitud.preparada_para_envio) {
      const boton = document.createElement("button");
      boton.type = "button";
      boton.className = "secundario";
      boton.textContent = "Cerrar solicitud";
      boton.addEventListener("click", () => cerrarSolicitud(solicitud));
      item.append(boton);
    }
    ui.estadoSolicitudes.append(item);
  }
  if (!ui.estadoSolicitudes.children.length) {
    const vacio = document.createElement("li");
    vacio.textContent = "No hay solicitudes para este proyecto.";
    ui.estadoSolicitudes.append(vacio);
  }
}

async function actualizarCodigoSugerido() {
  const proyectoId = ui.proyectoId.value;
  ui.codigoSugerido.value = "";
  if (!proyectoId) return;
  const tipo = ui.tipoSolicitud.value;
  const respuesta = await graphql(`query CodigosDelProyecto($id: uuid!) {
    solicitudes_cotizacion(where: { proyecto_id: { _eq: $id } }) { codigo }
  }`, { id: proyectoId });
  const prefijo = `${tipo}-`;
  const mayor = respuesta.solicitudes_cotizacion.reduce((actual, solicitud) => {
    if (!solicitud.codigo.startsWith(prefijo)) return actual;
    const numero = solicitud.codigo.slice(prefijo.length);
    return /^[0-9]+$/.test(numero) ? Math.max(actual, Number(numero)) : actual;
  }, 0);
  ui.codigoSugerido.value = `${prefijo}${String(mayor + 1).padStart(3, "0")}`;
}

async function registrarProyecto(evento) {
  evento.preventDefault();
  const boton = ui.formProyecto.querySelector('button[type="submit"]');
  boton.disabled = true;
  try {
    const datos = new FormData(ui.formProyecto);
    const proyectoId = await crearProyecto(datos);
    await cargarProyectos(proyectoId);
    ui.formProyecto.reset();
    ui.resultadoProyecto.textContent = "Proyecto guardado. Ya puedes crear solicitudes para él.";
    ui.resultadoProyecto.className = "resultado exito";
  } catch (error) {
    ui.resultadoProyecto.textContent = mensajeError(error);
    ui.resultadoProyecto.className = "resultado error";
  } finally {
    boton.disabled = false;
  }
}

async function crearProyecto(datos) {
  const respuesta = await graphql(
    `mutation GuardarProyecto($objeto: proyectos_insert_input!) {
      insert_proyectos_one(object: $objeto) { id }
    }`,
    {
      objeto: {
        codigo: datos.get("proyecto_codigo").trim(),
        nombre: datos.get("proyecto_nombre").trim(),
      },
    },
  );
  return respuesta.insert_proyectos_one.id;
}

async function crearSolicitud(proyectoId, datos) {
  const respuesta = await graphql(
    `mutation CrearSolicitud($objeto: solicitudes_cotizacion_insert_input!) {
      insert_solicitudes_cotizacion_one(object: $objeto) { id codigo }
    }`,
    {
      objeto: {
        proyecto_id: proyectoId,
        tipo: datos.get("tipo"),
        nombre: datos.get("solicitud_nombre").trim(),
        moneda: datos.get("moneda"),
        fecha_limite: limpiar(datos.get("fecha_limite")),
        partida_critica: datos.get("partida_critica") === "true",
      },
    },
  );
  return respuesta.insert_solicitudes_cotizacion_one;
}

async function guardarProveedor(proveedor) {
  const identificadores = [];
  if (proveedor.ruc) identificadores.push({ ruc: { _eq: proveedor.ruc } });
  if (proveedor.correo) identificadores.push({ correo: { _ilike: proveedor.correo } });
  const where = identificadores.length ? { _or: identificadores } : null;

  if (where) {
    const busqueda = await graphql(
      `query BuscarProveedor($where: proveedores_bool_exp!) {
        proveedores(where: $where, limit: 2) { id }
      }`,
      { where },
    );
    if (busqueda.proveedores.length > 1) {
      throw new Error("El RUC y el correo pertenecen a proveedores diferentes.");
    }
    const existente = busqueda.proveedores[0];
    if (existente) {
      const actualizacion = await graphql(
        `mutation ActualizarProveedor($id: uuid!, $cambios: proveedores_set_input!) {
          update_proveedores_by_pk(pk_columns: { id: $id }, _set: $cambios) { id }
        }`,
        { id: existente.id, cambios: proveedor },
      );
      if (!actualizacion.update_proveedores_by_pk) {
        throw new Error("No se pudo actualizar el proveedor existente.");
      }
      return actualizacion.update_proveedores_by_pk.id;
    }
  }

  const respuesta = await graphql(
    `mutation CrearProveedor($objeto: proveedores_insert_input!) {
      insert_proveedores_one(object: $objeto) { id }
    }`,
    { objeto: proveedor },
  );
  return respuesta.insert_proveedores_one.id;
}

async function guardarProveedores(solicitudId, proveedores) {
  for (const proveedor of proveedores) {
    const proveedorId = await guardarProveedor(proveedor);
    await graphql(
      `mutation VincularProveedor($objeto: solicitud_proveedores_insert_input!) {
        insert_solicitud_proveedores_one(
          object: $objeto
          on_conflict: {
            constraint: solicitud_proveedores_pkey
            update_columns: []
          }
        ) { solicitud_id }
      }`,
      { objeto: { solicitud_id: solicitudId, proveedor_id: proveedorId } },
    );
  }
}

async function subirDocumento(solicitudId, tipo, archivo) {
  validarExcel(archivo, tipo);
  const existente = await graphql(
    `query BuscarDocumento($solicitudId: uuid!, $tipo: String!) {
      documentos(
        where: { solicitud_id: { _eq: $solicitudId }, tipo: { _eq: $tipo } }
        limit: 1
      ) { id }
    }`,
    { solicitudId, tipo },
  );
  if (existente.documentos.length) return;

  const nombre = `${solicitudId}-${tipo}-${Date.now()}-${nombreSeguro(archivo.name)}`;
  const carga = await nhost.storage.uploadFiles({
    "bucket-id": "solicitudes",
    "file[]": [archivo],
    "metadata[]": [{ name, metadata: { solicitudId, tipo } }],
  }, opcionesRolUsuario);
  const archivoGuardado = carga.body.processedFiles[0];
  if (!archivoGuardado) throw new Error(`No se pudo almacenar el archivo ${tipo}.`);

  try {
    await graphql(
      `mutation RegistrarDocumento($objeto: documentos_insert_input!) {
        insert_documentos_one(object: $objeto) { id }
      }`,
      {
        objeto: {
          solicitud_id: solicitudId,
          tipo,
          nombre_original: archivo.name,
          storage_file_id: archivoGuardado.id,
          mime_type: mimeExcel(archivo),
          tamano_bytes: archivo.size,
        },
      },
    );
  } catch (error) {
    await nhost.storage.deleteFile(archivoGuardado.id, opcionesRolUsuario).catch(() => {});
    throw error;
  }
}

async function registrarSolicitud(evento) {
  evento.preventDefault();
  actualizarFechaInicio();
  ui.guardarSolicitud.disabled = true;
  mostrarResultado("Creando solicitud y subiendo documentos…");
  try {
    if (!nhost.getUserSession()?.user?.id) throw new Error("La sesión venció. Vuelve a ingresar.");

    const datos = new FormData(ui.formSolicitud);
    const proveedores = leerProveedores();
    if (!proveedores.length) throw new Error("Agrega al menos un proveedor.");

    const proyectoId = datos.get("proyecto_id");
    if (!proyectoId) throw new Error("Selecciona un proyecto registrado.");
    mostrarResultado("Guardando la solicitud…");
    const solicitud = await crearSolicitud(proyectoId, datos);
    const solicitudId = solicitud.id;
    mostrarResultado("Guardando los proveedores…");
    await guardarProveedores(solicitudId, proveedores);

    for (const tipo of ["itemizado", "plantilla_comparativo"]) {
      const archivo = datos.get(tipo);
      if (!(archivo instanceof File) || !archivo.size) {
        if (tipo === "itemizado") throw new Error("Falta el itemizado y metrados.");
        continue;
      }
      mostrarResultado(`Subiendo el documento ${tipo.replaceAll("_", " ")}…`);
      await subirDocumento(solicitudId, tipo, archivo);
    }

    await graphql(
      `mutation PrepararSolicitudParaEnvio($id: uuid!) {
        update_solicitudes_cotizacion_by_pk(
          pk_columns: { id: $id }
          _set: { preparada_para_envio: true }
        ) { id estado preparada_para_envio }
      }`,
      { id: solicitudId },
    );

    mostrarResultado(`Solicitud ${solicitud.codigo} creada correctamente. Identificador: ${solicitudId}`, "exito");
    cargarEstadoSolicitudes().catch((error) => mostrarResultado(mensajeError(error), "error"));
    cargarSeguimientoProveedores().catch((error) => mostrarResultado(mensajeError(error), "error"));
    ui.formSolicitud.reset();
    actualizarFechaInicio();
    ui.proyectoId.value = proyectoId;
    mostrarProyectoSeleccionado();
    ui.guardarSolicitud.disabled = false;
    actualizarCodigoSugerido().catch((error) => mostrarResultado(mensajeError(error), "error"));
    ui.proveedores.replaceChildren();
    agregarProveedor();
  } catch (error) {
    mostrarResultado(mensajeError(error), "error");
  } finally {
    ui.guardarSolicitud.disabled = false;
  }
}

ui.formAcceso.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  try { await autenticar(false); } catch (error) { alert(mensajeError(error)); }
});
ui.crearCuenta.addEventListener("click", async () => {
  if (!ui.formAcceso.reportValidity()) return;
  try { await autenticar(true); } catch (error) { alert(mensajeError(error)); }
});
ui.cerrarSesion.addEventListener("click", async () => {
  const session = nhost.getUserSession();
  try { await nhost.auth.signOut({ refreshToken: session?.refreshToken }); } finally { nhost.clearSession(); }
});
ui.agregarProveedor.addEventListener("click", agregarProveedor);
ui.formCoordinacion.addEventListener("submit", registrarCoordinacion);
ui.cancelarCoordinacion.addEventListener("click", () => ui.dialogoCoordinacion.close());
ui.formProyecto.addEventListener("submit", registrarProyecto);
ui.proyectoId.addEventListener("change", () => {
  ui.guardarSolicitud.disabled = !ui.proyectoId.value;
  mostrarProyectoSeleccionado();
  actualizarCodigoSugerido().catch((error) => mostrarResultado(mensajeError(error), "error"));
  cargarEstadoSolicitudes().catch((error) => mostrarResultado(mensajeError(error), "error"));
  cargarSeguimientoProveedores().catch((error) => mostrarResultado(mensajeError(error), "error"));
  cargarNotificaciones().catch((error) => mostrarResultado(mensajeError(error), "error"));
});
ui.tipoSolicitud.addEventListener("change", () => actualizarCodigoSugerido().catch((error) => mostrarResultado(mensajeError(error), "error")));
ui.formSolicitud.addEventListener("submit", registrarSolicitud);

function actualizarFechaInicio() {
  const hoy = new Date();
  ui.fechaInicio.value = hoy.toLocaleDateString("es-PE", { timeZone: "America/Lima" });
  ui.fechaLimite.min = hoy.toLocaleDateString("en-CA", { timeZone: "America/Lima" });
}

agregarProveedor();
actualizarFechaInicio();
configurarNhost();
