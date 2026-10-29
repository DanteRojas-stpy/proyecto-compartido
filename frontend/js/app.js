import { createClient } from "https://esm.sh/@nhost/nhost-js@4.9.0";
import { createClient as createSubscriptionClient } from "https://esm.sh/graphql-ws@5.16.2";
import { describirEstadoE4, describirEstadoE5, formatearImporte, leerTipoCambio, nombreArchivoCuadro, nombreArchivoHomologacion, resumirHomologacion } from "./e4.js";

const ui = {
  configuracion: document.querySelector("#configuracion"),
  acceso: document.querySelector("#acceso"),
  proyectos: document.querySelector("#proyectos"),
  listaProyectos: document.querySelector("#lista-proyectos"),
  registro: document.querySelector("#registro"),
  solicitudes: document.querySelector("#solicitudes"),
  nuevoProyecto: document.querySelector("#nuevo-proyecto"),
  cancelarProyecto: document.querySelector("#cancelar-proyecto"),
  irInicio: document.querySelector("#ir-inicio"),
  volverProyectos: document.querySelector("#volver-proyectos"),
  nuevaSolicitud: document.querySelector("#nueva-solicitud"),
  cancelarSolicitud: document.querySelector("#cancelar-solicitud"),
  panelNuevaSolicitud: document.querySelector("#panel-nueva-solicitud"),
  proyectoActivoCodigo: document.querySelector("#proyecto-activo-codigo"),
  proyectoActivoNombre: document.querySelector("#proyecto-activo-nombre"),
  proyectoActivoResumen: document.querySelector("#proyecto-activo-resumen"),
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
let usuarioSesionId;
let proyectoActivoId = "";
const opcionesRolUsuario = { headers: { "x-hasura-role": "user" } };

const estadosCorreo = [
  ["respuesta_sin_nueva_cotizacion_ni_ficha_tecnica", "Respuesta sin nueva cotización ni ficha técnica"],
  ["cotizacion_o_ficha_tecnica_recibida", "Cotización o ficha técnica recibida"],
  ["cotizacion_o_ficha_tecnica_aceptada_final", "Cotización o ficha técnica aceptada como final"],
];

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
  const nuevaSesion = conectado && usuarioSesionId !== session.user.id;
  usuarioSesionId = conectado ? session.user.id : undefined;
  ui.acceso.classList.toggle("oculto", conectado);
  ui.cerrarSesion.classList.toggle("oculto", !conectado);
  ui.usuarioActivo.textContent = conectado ? session.user.email : "";
  if (conectado) {
    if (nuevaSesion) {
      proyectosDisponibles = [];
      ui.listaProyectos.replaceChildren();
      mostrarDashboard();
      cargarProyectos().catch((error) => mostrarResultado(mensajeError(error), "error"));
    }
    iniciarNotificacionesEnTiempoReal();
  } else {
    detenerNotificacionesEnTiempoReal();
    ui.proyectos.classList.add("oculto");
    ui.registro.classList.add("oculto");
    ui.solicitudes.classList.add("oculto");
    ui.proyectoId.replaceChildren();
    ui.listaProyectos.replaceChildren();
    proyectoActivoId = "";
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

function mostrarDashboard() {
  ui.proyectos.classList.remove("oculto");
  ui.registro.classList.add("oculto");
  ui.solicitudes.classList.add("oculto");
  ui.panelNuevaSolicitud.classList.add("oculto");
  document.title = "CostFlow | Proyectos";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function metricasProyecto(proyectoId) {
  const solicitudes = proyectosDisponibles.find((item) => item.id === proyectoId)?.solicitudes ?? [];
  return {
    total: solicitudes.length,
    criticas: solicitudes.filter((item) => item.partida_critica).length,
    activas: solicitudes.filter((item) => item.estado === "inicio").length,
  };
}

function actualizarCabeceraProyecto() {
  const proyecto = proyectosDisponibles.find((item) => item.id === proyectoActivoId);
  if (!proyecto) return;
  const metricas = metricasProyecto(proyecto.id);
  ui.proyectoActivoCodigo.textContent = proyecto.codigo;
  ui.proyectoActivoNombre.textContent = proyecto.nombre;
  ui.proyectoActivoResumen.textContent = `${metricas.total} solicitud${metricas.total === 1 ? "" : "es"} · ${metricas.criticas} crítica${metricas.criticas === 1 ? "" : "s"}`;
}

function renderizarProyectos() {
  ui.listaProyectos.replaceChildren();
  for (const proyecto of proyectosDisponibles) {
    const metricas = metricasProyecto(proyecto.id);
    const tarjeta = document.createElement("button");
    tarjeta.type = "button";
    tarjeta.className = "tarjeta-proyecto";
    tarjeta.setAttribute("aria-label", `Abrir proyecto ${proyecto.nombre}`);

    const cabecera = document.createElement("span");
    const codigo = document.createElement("span");
    codigo.className = "codigo";
    codigo.textContent = proyecto.codigo;
    const nombre = document.createElement("span");
    nombre.className = "titulo";
    nombre.textContent = proyecto.nombre;
    const estado = document.createElement("span");
    estado.className = `estado-proyecto${metricas.total && !metricas.activas ? " completo" : ""}`;
    estado.textContent = metricas.activas
      ? `${metricas.activas} activa${metricas.activas === 1 ? "" : "s"}`
      : metricas.total ? "Sin solicitudes activas" : "Sin solicitudes";
    cabecera.append(codigo, nombre, estado);

    const metricasElemento = document.createElement("span");
    metricasElemento.className = "metricas-proyecto";
    for (const [valor, etiqueta] of [[metricas.total, "Solicitudes"], [metricas.criticas, "Críticas"]]) {
      const metrica = document.createElement("span");
      metrica.className = "metrica";
      const cifra = document.createElement("strong");
      cifra.textContent = valor;
      const texto = document.createElement("span");
      texto.textContent = etiqueta;
      metrica.append(cifra, texto);
      metricasElemento.append(metrica);
    }

    const pie = document.createElement("span");
    pie.className = "pie-tarjeta";
    const actividad = document.createElement("span");
    actividad.className = "ayuda";
    actividad.textContent = `Actualizado ${formatearFecha(proyecto.actividad_at)}`;
    const enlace = document.createElement("span");
    enlace.className = "enlace-tarjeta";
    enlace.textContent = "Abrir →";
    pie.append(actividad, enlace);
    tarjeta.append(cabecera, metricasElemento, pie);
    tarjeta.addEventListener("click", () => abrirProyecto(proyecto.id));
    ui.listaProyectos.append(tarjeta);
  }
  if (!proyectosDisponibles.length) {
    const vacio = document.createElement("div");
    vacio.className = "vacio-proyectos";
    vacio.innerHTML = "<h2>Aún no hay proyectos</h2><p>Crea el primer proyecto para comenzar a gestionar solicitudes de cotización.</p>";
    ui.listaProyectos.append(vacio);
  }
}

async function abrirProyecto(proyectoId) {
  const proyecto = proyectosDisponibles.find((item) => item.id === proyectoId);
  if (!proyecto) return;
  proyectoActivoId = proyectoId;
  ui.proyectoId.value = proyectoId;
  ui.guardarSolicitud.disabled = false;
  mostrarProyectoSeleccionado();
  ui.proyectos.classList.add("oculto");
  ui.registro.classList.add("oculto");
  ui.solicitudes.classList.remove("oculto");
  ui.panelNuevaSolicitud.classList.add("oculto");
  actualizarCabeceraProyecto();
  document.title = `CostFlow | ${proyecto.nombre}`;
  await Promise.all([cargarDetalleProyecto(), cargarNotificaciones(), actualizarCodigoSugerido()]);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function cargarProyectos(seleccionarId = ui.proyectoId.value) {
  const respuesta = await graphql(`query ProyectosDisponibles {
    proyectos(order_by: { codigo: asc }) { id codigo nombre updated_at }
    solicitudes_cotizacion(order_by: { created_at: desc }) {
      id proyecto_id estado partida_critica updated_at
    }
  }`);
  const solicitudesPorProyecto = new Map();
  for (const solicitud of respuesta.solicitudes_cotizacion) {
    if (!solicitudesPorProyecto.has(solicitud.proyecto_id)) solicitudesPorProyecto.set(solicitud.proyecto_id, []);
    solicitudesPorProyecto.get(solicitud.proyecto_id).push(solicitud);
  }
  proyectosDisponibles = respuesta.proyectos.map((proyecto) => ({
    ...proyecto,
    solicitudes: solicitudesPorProyecto.get(proyecto.id) ?? [],
    actividad_at: (solicitudesPorProyecto.get(proyecto.id) ?? []).reduce(
      (ultima, solicitud) => solicitud.updated_at > ultima ? solicitud.updated_at : ultima,
      proyecto.updated_at,
    ),
  }));
  ui.proyectoId.replaceChildren(new Option("Selecciona un proyecto", ""));
  for (const proyecto of respuesta.proyectos) {
    ui.proyectoId.add(new Option(`${proyecto.codigo} — ${proyecto.nombre}`, proyecto.id));
  }
  if (respuesta.proyectos.some((proyecto) => proyecto.id === seleccionarId)) ui.proyectoId.value = seleccionarId;
  ui.guardarSolicitud.disabled = !ui.proyectoId.value;
  renderizarProyectos();
  mostrarProyectoSeleccionado();
  if (!ui.solicitudes.classList.contains("oculto")) actualizarCabeceraProyecto();
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

function formatearFecha(valor) {
  if (!valor) return "sin actividad";
  return new Date(valor).toLocaleDateString("es-PE", {
    timeZone: "America/Lima",
    day: "2-digit",
    month: "short",
    year: "numeric",
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
    await cargarDetalleProyecto();
    await cargarNotificaciones();
  } catch (error) {
    mostrarResultado(mensajeError(error), "error");
  }
}

// Aceptar como final pasa por la decisión de E3: la base registra quién decidió, conserva la
// versión anterior y guarda la auditoría. Un cambio directo del estado se rechaza.
async function aceptarComoFinal(correo, conObservaciones = false) {
  // Se usa la vista de E3 que el rol del especialista puede leer (versiones_cotizacion no está publicada para él).
  const datos = await graphql(
    `query VersionParaFinal($correo: uuid!) {
      e3_bandeja_versiones(where: { correo_id: { _eq: $correo } }, order_by: { numero_version: desc }, limit: 1) {
        version_id solicitud_id proveedor_id numero_version
      }
    }`,
    { correo: correo.id },
  );
  const fila = datos.e3_bandeja_versiones?.[0];
  if (!fila) throw new Error("Esta cotización todavía no tiene una versión procesada por E3.");
  const version = { id: fila.version_id, solicitud_id: fila.solicitud_id, proveedor_id: fila.proveedor_id, version: fila.numero_version };

  const token = nhost.getUserSession()?.accessToken;
  if (!token) throw new Error("La sesión venció. Vuelve a ingresar.");
  const url = `https://${configuracionNhost.NHOST_SUBDOMAIN}.functions.${configuracionNhost.NHOST_REGION}.nhost.run/v1/e3-operar`;
  const respuesta = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      operacion: "decision",
      datos: {
        accion: {
          accion: "aceptar_version",
          version_id: version.id,
          accion_id: crypto.randomUUID(),
          medio: "plataforma",
          motivo: conObservaciones
            ? "Aceptada como final por el especialista, con observaciones pendientes"
            : "Aceptada como final por el especialista",
          aceptar_con_observaciones: conObservaciones,
        },
      },
    }),
  });
  const cuerpo = await respuesta.json().catch(() => ({}));
  // La función entrega la respuesta de E3 dentro de { respuesta: ... }; el rechazo está en ese interior.
  const resultado = cuerpo.respuesta ?? cuerpo;
  if (resultado.requiere_confirmacion) {
    // No es un fallo: el especialista decide si acepta la versión con sus observaciones pendientes.
    const pregunta = new Error(resultado.mensaje);
    pregunta.pendientes = resultado.pendientes;
    pregunta.requiereConfirmacion = true;
    throw pregunta;
  }
  if (!respuesta.ok || resultado.ok !== true) {
    throw new Error(resultado.mensaje ?? resultado.error ?? cuerpo.error ?? "E3 no aceptó la versión como final.");
  }
  return version;
}

// Genera el .json de la versión final con el resultado de E3, lo guarda en Storage y lo descarga.
async function guardarJsonFinal(version) {
  const datos = await graphql(
    `query ResultadoFinal($version: uuid!) {
      e3_resultados(where: { version_id: { _eq: $version } }) { resultado }
    }`,
    { version: version.id },
  );
  const resultado = datos.e3_resultados?.[0]?.resultado;
  if (!resultado) throw new Error("E3 todavía no tiene el resultado de esta versión.");

  const contenido = {
    solicitud_id: version.solicitud_id,
    proveedor_id: version.proveedor_id,
    version_id: version.id,
    numero_version: version.version,
    aceptada_at: new Date().toISOString(),
    resultado,
  };
  const nombre = `final-${version.solicitud_id}-${version.proveedor_id}-v${version.version}.json`;
  const archivo = new File([JSON.stringify(contenido, null, 2)], nombre, { type: "application/json" });

  await nhost.storage.uploadFiles({
    "bucket-id": "cotizaciones",
    "file[]": [archivo],
    "metadata[]": [{ name: nombre, metadata: { solicitudId: version.solicitud_id, tipo: "resultado_final" } }],
  }, opcionesRolUsuario);

  const enlace = document.createElement("a");
  enlace.href = URL.createObjectURL(archivo);
  enlace.download = nombre;
  enlace.click();
  URL.revokeObjectURL(enlace.href);
}

function avisarCorreo(aviso, texto, tipo = "") {
  aviso.textContent = texto;
  aviso.className = `ayuda estado-correo-aviso ${tipo}`.trim();
}

// Lee el estado tal como quedó en Nhost, para mostrar lo que realmente se guardó.
async function estadoGuardadoEnNhost(correo) {
  const datos = await graphql(
    `query EstadoGuardado($id: uuid!) {
      correos_proveedor_by_pk(id: $id) { estado_correo estado_asignado_at origen_estado }
    }`,
    { id: correo.id },
  );
  return datos.correos_proveedor_by_pk ?? null;
}

async function guardarEstadoCorreo(correo, estado, boton, aviso) {
  // La confirmación se pide dentro de la tarjeta: un cuadro del navegador puede bloquearse y dejar el botón sin respuesta.
  if (estado === "cotizacion_o_ficha_tecnica_aceptada_final" && boton.dataset.confirmado !== "si") {
    boton.dataset.confirmado = "si";
    avisarCorreo(
      aviso,
      "Confirma con otro clic en «Guardar estado»: la cotización pasará a final.",
      "",
    );
    return;
  }
  delete boton.dataset.confirmado;
  const conObservaciones = boton.dataset.conObservaciones === "si";
  delete boton.dataset.conObservaciones;
  const texto = estadosCorreo.find(([valor]) => valor === estado)?.[1] ?? estado;
  boton.disabled = true;
  avisarCorreo(aviso, "Guardando en Nhost…");
  try {
    let notaJson = "";
    if (estado === "cotizacion_o_ficha_tecnica_aceptada_final") {
      // La aceptación ya quedó registrada en E3; el .json es un paso aparte que puede fallar sin deshacerla.
      const version = await aceptarComoFinal(correo, conObservaciones);
      try {
        await guardarJsonFinal(version);
        notaJson = " y guardada como .json";
      } catch (errorJson) {
        notaJson = `. El .json no se generó: ${mensajeError(errorJson)}`;
      }
    } else {
      await graphql(
        `mutation GuardarEstadoCorreo($id: uuid!, $estado: String!) {
          update_correos_proveedor_by_pk(
            pk_columns: { id: $id }
            _set: { estado_correo: $estado }
          ) { id estado_correo origen_estado estado_asignado_at }
        }`,
        { id: correo.id, estado },
      );
    }

    // Se vuelve a leer desde Nhost: el aviso muestra lo que quedó guardado, no lo que se intentó guardar.
    const guardado = await estadoGuardadoEnNhost(correo);
    const estadoEnNhost = guardado?.estado_correo ?? null;
    if (estadoEnNhost === estado) {
      correo.estado_correo = estadoEnNhost;
      correo.estado_asignado_at = guardado.estado_asignado_at;
      correo.origen_estado = guardado.origen_estado;
      const cuando = guardado.estado_asignado_at ? formatearFechaHora(guardado.estado_asignado_at) : "sin fecha";
      avisarCorreo(aviso, `Guardado en Nhost: ${texto} · ${cuando}${notaJson}.`, "exito");
    } else {
      avisarCorreo(aviso, `No se guardó como «${texto}». Nhost conserva: ${estadoEnNhost ?? "sin estado"}.`, "error");
    }
  } catch (error) {
    if (error.requiereConfirmacion) {
      // La siguiente pulsación acepta la versión con sus observaciones pendientes.
      boton.dataset.confirmado = "si";
      boton.dataset.conObservaciones = "si";
      avisarCorreo(
        aviso,
        `${mensajeError(error)} Pulsa «Guardar estado» otra vez para aceptarla de todos modos.`,
        "",
      );
    } else {
      avisarCorreo(aviso, `No se guardó: ${mensajeError(error)}`, "error");
    }
  } finally {
    boton.disabled = false;
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
    await cargarDetalleProyecto();
  } catch (error) {
    mostrarResultado(mensajeError(error), "error");
  }
}

function crearTarjetaCorreo(correo, esMasReciente, correosDelProveedor = []) {
  const tarjeta = document.createElement("article");
  tarjeta.className = "correo-proveedor";
  const cabecera = document.createElement("div");
  cabecera.className = "correo-cabecera";
  const asunto = document.createElement("strong");
  asunto.textContent = correo.asunto || "Correo sin asunto";
  const fecha = document.createElement("time");
  fecha.dateTime = correo.recibido_at;
  fecha.textContent = formatearFechaHora(correo.recibido_at);
  cabecera.append(asunto, fecha);
  if (esMasReciente) {
    const reciente = document.createElement("span");
    reciente.className = "badge respondio";
    reciente.textContent = "MÁS RECIENTE";
    cabecera.append(reciente);
  }
  // Indica si esta cotización es la final o si otra de este proveedor ya lo es.
  const finalDelProveedor = correosDelProveedor.find(
    (item) => item.estado_correo === "cotizacion_o_ficha_tecnica_aceptada_final",
  );
  const situacion = document.createElement("span");
  if (correo.estado_correo === "cotizacion_o_ficha_tecnica_aceptada_final") {
    situacion.className = "badge respondio";
    situacion.textContent = "VERSIÓN FINAL";
    cabecera.append(situacion);
  } else if (finalDelProveedor) {
    situacion.className = "badge";
    situacion.textContent = "Reemplazada por la versión final";
    cabecera.append(situacion);
  }

  const contenido = document.createElement("details");
  contenido.className = "contenido-correo";
  const abrir = document.createElement("summary");
  abrir.textContent = "Ver contenido del correo";
  const cuerpo = document.createElement("p");
  cuerpo.className = "cuerpo-correo";
  cuerpo.textContent = correo.cuerpo_texto || "El correo no contiene texto disponible.";
  contenido.append(abrir, cuerpo);

  const adjuntos = Array.isArray(correo.adjuntos) ? correo.adjuntos : [];
  const bloqueAdjuntos = document.createElement("div");
  bloqueAdjuntos.className = "adjuntos-correo";
  const tituloAdjuntos = document.createElement("strong");
  tituloAdjuntos.textContent = `Adjuntos (${adjuntos.length})`;
  bloqueAdjuntos.append(tituloAdjuntos);
  if (adjuntos.length) {
    const lista = document.createElement("ul");
    for (const adjunto of adjuntos) {
      const item = document.createElement("li");
      item.textContent = adjunto.nombre || "Archivo adjunto";
      lista.append(item);
    }
    bloqueAdjuntos.append(lista);
  } else {
    const vacio = document.createElement("span");
    vacio.className = "ayuda";
    vacio.textContent = "Sin archivos adjuntos registrados.";
    bloqueAdjuntos.append(vacio);
  }

  const documentos = Array.isArray(correo.documentos) ? correo.documentos : [];
  const bloqueDocumentos = document.createElement("div");
  bloqueDocumentos.className = "documentos-correo";
  const tituloDocumentos = document.createElement("strong");
  tituloDocumentos.textContent = `Documentos recuperados por E3 (${documentos.length})`;
  bloqueDocumentos.append(tituloDocumentos);
  if (documentos.length) {
    const lista = document.createElement("ul");
    for (const documento of documentos) {
      const item = document.createElement("li");
      const tipo = documento.tipo === "cotizacion_proveedor" ? "Cotización" : "Ficha técnica";
      item.textContent = `${tipo} · versión ${documento.version} · ${documento.nombre_original}`;
      lista.append(item);
    }
    bloqueDocumentos.append(lista);
  } else {
    const vacio = document.createElement("span");
    vacio.className = "ayuda";
    vacio.textContent = "E3 todavía no ha registrado documentos de este correo.";
    bloqueDocumentos.append(vacio);
  }

  const acciones = document.createElement("div");
  acciones.className = "estado-correo-acciones";
  const etiqueta = document.createElement("label");
  etiqueta.textContent = "Estado del correo";
  const selector = document.createElement("select");
  for (const [valor, texto] of estadosCorreo) {
    selector.add(new Option(texto, valor, false, valor === correo.estado_correo));
  }
  etiqueta.append(selector);
  const origen = document.createElement("span");
  origen.className = "ayuda estado-correo-origen";
  origen.textContent = correo.origen_estado === "usuario"
    ? `Asignado por el especialista · ${formatearFechaHora(correo.estado_asignado_at)}`
    : "Asignación preliminar de n8n";
  const guardar = document.createElement("button");
  guardar.type = "button";
  guardar.className = "secundario";
  guardar.textContent = "Guardar estado";
  const aviso = document.createElement("p");
  aviso.className = "ayuda estado-correo-aviso";
  aviso.setAttribute("role", "status");
  guardar.addEventListener("click", () => guardarEstadoCorreo(correo, selector.value, guardar, aviso));
  acciones.append(etiqueta, origen, guardar, aviso);
  tarjeta.append(cabecera, contenido, bloqueAdjuntos, bloqueDocumentos, acciones);
  return tarjeta;
}

function resumenEstadoProveedor(correos, participacion) {
  if (!correos.length) {
    return participacion.considerado
      ? { texto: "Sin respuesta", pendiente: true }
      : { texto: "No envió cotización ni ficha técnica", pendiente: true };
  }
  if (correos.some((correo) => correo.estado_correo === "cotizacion_o_ficha_tecnica_aceptada_final")) {
    return { texto: "Cotización o ficha técnica aceptada como final", pendiente: false };
  }
  if (correos.some((correo) => correo.estado_correo === "cotizacion_o_ficha_tecnica_recibida")) {
    return { texto: "Cotización o ficha técnica recibida", pendiente: false };
  }
  return { texto: "Respuesta sin nueva cotización ni ficha técnica", pendiente: true };
}

function crearTarjetaProveedor(participacion, aclaraciones, correos) {
  const tarjeta = document.createElement("article");
  tarjeta.className = `seguimiento-proveedor${participacion.considerado ? "" : " excluido"}`;
  const cabecera = document.createElement("div");
  cabecera.className = "seguimiento-cabecera";
  const identidad = document.createElement("div");
  const titulo = document.createElement("h3");
  titulo.textContent = participacion.proveedor_asociado.nombre;
  const correo = document.createElement("p");
  correo.className = "ayuda";
  correo.textContent = participacion.proveedor_asociado.correo || "Sin correo";
  identidad.append(titulo, correo);
  const estado = document.createElement("span");
  const resumenEstado = resumenEstadoProveedor(correos, participacion);
  estado.className = `estado-respuesta${resumenEstado.pendiente ? " pendiente" : ""}`;
  estado.textContent = resumenEstado.texto;
  cabecera.append(identidad, estado);

  const detalle = document.createElement("p");
  detalle.textContent = `${correos.length} correo${correos.length === 1 ? "" : "s"}. Coordinaciones: ${participacion.numero_coordinaciones}/3. Último correo: ${formatearFechaHora(participacion.ultimo_correo_at)}.`;
  tarjeta.append(cabecera, detalle);

  if (correos.length) {
    const historial = document.createElement("div");
    historial.className = "historial-correos";
    const tituloHistorial = document.createElement("h4");
    tituloHistorial.textContent = "Correos del proveedor";
    historial.append(tituloHistorial);
    correos.forEach((correoItem, indice) => historial.append(crearTarjetaCorreo(correoItem, indice === 0, correos)));
    tarjeta.append(historial);
  }

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

    if (acciones.children.length) tarjeta.append(acciones);
  }
  return tarjeta;
}

function crearDatoResumen(etiqueta, valor) {
  const elemento = document.createElement("span");
  elemento.className = "dato-resumen";
  elemento.textContent = etiqueta;
  const dato = document.createElement("strong");
  dato.textContent = valor;
  elemento.append(dato);
  return elemento;
}

// ---- E4: homologación ---------------------------------------------------------------------------------
// El especialista decide cuándo homologar. La Function e4-operar verifica su sesión; n8n hace el trabajo y avisa al terminar.

async function llamarFuncionNhost(funcion, operacion, datos) {
  const token = nhost.getUserSession()?.accessToken;
  if (!token) throw new Error("La sesión venció. Vuelve a ingresar.");
  const url = `https://${configuracionNhost.NHOST_SUBDOMAIN}.functions.${configuracionNhost.NHOST_REGION}.nhost.run/v1/${funcion}`;
  const respuesta = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ operacion, datos }),
  });
  const cuerpo = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok && !cuerpo.respuesta) throw new Error(cuerpo.error ?? "No se pudo completar la operación.");
  return cuerpo.respuesta ?? cuerpo;
}

const CAMPOS_ESTADO_E4 = "solicitud_id finales_e3 e4_estado e4_solicitada_at e4_error homologacion_id estado_revision homologada_at e4_modelo cuadro_id e5_estado e5_revision nombre_archivo cuadro_storage_file_id e5_error";

async function cargarEstadosE4(proyectoId) {
  try {
    const datos = await graphql(
      `query EstadoE4($id: uuid!) {
        e4_estado_solicitud(where: { solicitud_e3: { proyecto_id: { _eq: $id } } }) { ${CAMPOS_ESTADO_E4} }
      }`,
      { id: proyectoId },
    );
    return new Map(datos.e4_estado_solicitud.map((fila) => [fila.solicitud_id, fila]));
  } catch (error) {
    // Sin la migración 017 o sus permisos, la pantalla sigue funcionando sin el bloque de homologación.
    console.warn("E4 no disponible:", mensajeError(error));
    return null;
  }
}

async function cargarEstadoE4DeSolicitud(solicitudId) {
  const datos = await graphql(
    `query EstadoE4Solicitud($id: uuid!) { e4_estado_solicitud(where: { solicitud_id: { _eq: $id } }) { ${CAMPOS_ESTADO_E4} } }`,
    { id: solicitudId },
  );
  return datos.e4_estado_solicitud?.[0] ?? null;
}

async function cargarResultadoE4(homologacionId) {
  const datos = await graphql(
    `query ResultadoE4($id: uuid!) { e4_homologaciones(where: { id: { _eq: $id } }) { resultado created_at modelo } }`,
    { id: homologacionId },
  );
  const fila = datos.e4_homologaciones?.[0];
  if (!fila) throw new Error("No se encontró el resultado de la homologación.");
  return fila;
}

function crearTextoE4(etiqueta, texto, clase = "") {
  const nodo = document.createElement(etiqueta);
  if (clase) nodo.className = clase;
  nodo.textContent = texto;
  return nodo;
}

function dibujarResumenE4(panel, resumen) {
  panel.replaceChildren();
  const moneda = resumen.moneda ? `Moneda de comparación: ${resumen.moneda}` : "Moneda de comparación sin definir";
  panel.append(crearTextoE4("p", `${resumen.estado} · ${moneda} · ${resumen.base}`, "ayuda"));

  panel.append(crearTextoE4("h4", "Proveedores"));
  const proveedores = document.createElement("ul");
  for (const postor of resumen.postores) {
    const totales = postor.total !== null
      ? formatearImporte(postor.total, postor.moneda)
      : postor.porDocumento.length
        ? `por documento: ${postor.porDocumento.map((total) => formatearImporte(total, postor.moneda)).join(" y ")}`
        : "no informado";
    const linea = `${postor.nombre} — total declarado ${totales}`
      + `${postor.plazo ? ` · plazo ${postor.plazo}` : ""}${postor.vigencia ? ` · vigencia ${postor.vigencia}` : ""}`
      + `${postor.comparable ? "" : " · no comparable en la moneda de comparación"}`;
    proveedores.append(crearTextoE4("li", linea));
  }
  panel.append(proveedores);

  panel.append(crearTextoE4("h4", "Partidas"));
  for (const partida of resumen.partidas) {
    panel.append(crearTextoE4("strong", partida.titulo || "Partida sin descripción"));
    const ofertas = document.createElement("ul");
    for (const oferta of partida.ofertas) {
      ofertas.append(crearTextoE4("li", `${oferta.proveedor}: ${oferta.estado} · ${oferta.equivalencia}`));
    }
    panel.append(ofertas);
  }
  if (resumen.adicionales) panel.append(crearTextoE4("p", `Ítems adicionales fuera de la base: ${resumen.adicionales}.`, "ayuda"));

  panel.append(crearTextoE4("h4", `Pendientes: ${resumen.bloqueantes} bloquean la comparación, ${resumen.informativos} informativos`));
  const pendientes = document.createElement("ul");
  for (const pendiente of resumen.pendientes) {
    const item = document.createElement("li");
    item.append(
      crearTextoE4("strong", pendiente.bloquea ? "Bloquea · " : "Informativo · "),
      document.createTextNode(`${pendiente.motivo}${pendiente.decision ? ` Decisión: ${pendiente.decision}` : ""}`),
    );
    pendientes.append(item);
  }
  panel.append(pendientes);
}

async function descargarHomologacion(solicitud, homologacionId) {
  const fila = await cargarResultadoE4(homologacionId);
  const archivo = new File([JSON.stringify(fila.resultado, null, 2)], nombreArchivoHomologacion(solicitud.codigo, fila.created_at), { type: "application/json" });
  const enlace = document.createElement("a");
  enlace.href = URL.createObjectURL(archivo);
  enlace.download = archivo.name;
  enlace.click();
  URL.revokeObjectURL(enlace.href);
}

async function refrescarSeccionE4(seccion, solicitud, avisoInicial = "") {
  const fila = await cargarEstadoE4DeSolicitud(solicitud.id);
  if (!seccion.isConnected) return;
  seccion.replaceWith(crearSeccionHomologacion(solicitud, fila, avisoInicial));
  if (!describirEstadoE4(fila).activo && !describirEstadoE5(fila).activo) cargarNotificaciones().catch(() => {});
}

// Mientras E4 trabaja, la tarjeta se actualiza sola hasta que termine o el usuario cambie de pantalla.
function programarActualizacionE4(seccion, solicitud) {
  setTimeout(async () => {
    if (!seccion.isConnected) return;
    try {
      await refrescarSeccionE4(seccion, solicitud);
    } catch {
      if (seccion.isConnected) programarActualizacionE4(seccion, solicitud);
    }
  }, 8000);
}

// El cuadro está en Storage; se descarga con la sesión del especialista.
async function descargarCuadro(solicitud, fila) {
  const token = nhost.getUserSession()?.accessToken;
  if (!token) throw new Error("La sesión venció. Vuelve a ingresar.");
  const url = `https://${configuracionNhost.NHOST_SUBDOMAIN}.storage.${configuracionNhost.NHOST_REGION}.nhost.run/v1/files/${fila.cuadro_storage_file_id}`;
  const respuesta = await fetch(url, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" });
  if (!respuesta.ok) throw new Error("No se pudo descargar el cuadro. Vuelve a intentarlo.");
  const enlace = document.createElement("a");
  enlace.href = URL.createObjectURL(await respuesta.blob());
  enlace.download = nombreArchivoCuadro(fila.nombre_archivo, solicitud.codigo, fila.e5_revision);
  enlace.click();
  URL.revokeObjectURL(enlace.href);
}

async function solicitarCuadro(solicitud, seccion, boton, aviso, campos) {
  const lectura = leerTipoCambio({ valor: campos.valor.value, fecha: campos.fecha.value, fuente: campos.fuente.value });
  if (lectura.error) return avisarCorreo(aviso, lectura.error, "error");
  boton.disabled = true;
  avisarCorreo(aviso, "Solicitando el cuadro…");
  try {
    const resultado = await llamarFuncionNhost("e4-operar", "solicitar_e5", { solicitud_id: solicitud.id, tipo_cambio: lectura.tipoCambio });
    if (resultado.ok !== true) throw new Error(resultado.mensaje ?? "No se pudo solicitar el cuadro.");
    await refrescarSeccionE4(seccion, solicitud, "Cuadro solicitado. Te avisaremos cuando termine.");
  } catch (error) {
    avisarCorreo(aviso, `No se pudo generar el cuadro: ${mensajeError(error)}`, "error");
    boton.disabled = false;
  }
}

function crearBloqueCuadro(solicitud, fila, seccion) {
  const estado = describirEstadoE5(fila);
  const bloque = document.createElement("div");
  bloque.className = "cuadro";
  const cabecera = document.createElement("div");
  cabecera.className = "homologacion-cabecera";
  cabecera.append(crearTextoE4("strong", "Cuadro comparativo (E5)"), crearTextoE4("span", estado.badge.texto, `badge ${estado.badge.clase}`));
  const aviso = crearTextoE4("p", "", "ayuda estado-correo-aviso");
  aviso.setAttribute("role", "status");

  const cambio = document.createElement("details");
  cambio.append(crearTextoE4("summary", "Tipo de cambio US$ → S/ (solo si hay ofertas en dólares)"));
  const campos = {};
  for (const [clave, etiqueta, tipo, ejemplo] of [["valor", "Valor", "text", "3.75"], ["fecha", "Fecha", "date", ""], ["fuente", "Fuente", "text", "SBS"]]) {
    const campo = document.createElement("label");
    campo.append(etiqueta);
    const entrada = document.createElement("input");
    entrada.type = tipo;
    entrada.placeholder = ejemplo;
    entrada.disabled = !estado.puedeGenerar;
    campos[clave] = entrada;
    campo.append(entrada);
    cambio.append(campo);
  }
  cambio.append(crearTextoE4("p", "El sistema nunca inventa el tipo de cambio: si no lo indicas, las columnas en S/ de las ofertas en dólares quedan vacías.", "ayuda"));

  const acciones = document.createElement("div");
  acciones.className = "acciones";
  const generar = crearTextoE4("button", estado.etiqueta);
  generar.type = "button";
  generar.disabled = !estado.puedeGenerar;
  generar.addEventListener("click", () => solicitarCuadro(solicitud, seccion, generar, aviso, campos));
  acciones.append(generar);
  if (estado.puedeDescargar) {
    const descargar = crearTextoE4("button", "Descargar Excel", "secundario");
    descargar.type = "button";
    descargar.addEventListener("click", () => descargarCuadro(solicitud, fila).catch((error) => avisarCorreo(aviso, mensajeError(error), "error")));
    acciones.append(descargar);
  }
  bloque.append(cabecera, crearTextoE4("p", estado.mensaje, "ayuda"), cambio, acciones, aviso);
  return bloque;
}

async function solicitarHomologacion(solicitud, seccion, boton, aviso) {
  boton.disabled = true;
  avisarCorreo(aviso, "Solicitando la homologación…");
  try {
    const resultado = await llamarFuncionNhost("e4-operar", "solicitar_e4", { solicitud_id: solicitud.id });
    if (resultado.ok !== true) throw new Error(resultado.mensaje ?? "No se pudo solicitar la homologación.");
    await refrescarSeccionE4(seccion, solicitud, "Homologación solicitada. Te avisaremos cuando termine.");
  } catch (error) {
    avisarCorreo(aviso, `No se pudo homologar: ${mensajeError(error)}`, "error");
    boton.disabled = false;
  }
}

function crearSeccionHomologacion(solicitud, fila, avisoInicial = "") {
  const estado = describirEstadoE4(fila);
  const seccion = document.createElement("section");
  seccion.className = "homologacion";
  const cabecera = document.createElement("div");
  cabecera.className = "homologacion-cabecera";
  cabecera.append(crearTextoE4("strong", "Homologación (E4)"), crearTextoE4("span", estado.badge.texto, `badge ${estado.badge.clase}`));

  const acciones = document.createElement("div");
  acciones.className = "acciones";
  const aviso = crearTextoE4("p", avisoInicial, `ayuda estado-correo-aviso${avisoInicial ? " exito" : ""}`);
  aviso.setAttribute("role", "status");
  const homologar = crearTextoE4("button", estado.etiqueta);
  homologar.type = "button";
  homologar.disabled = !estado.puedeHomologar;
  homologar.addEventListener("click", () => solicitarHomologacion(solicitud, seccion, homologar, aviso));
  acciones.append(homologar);

  const panel = document.createElement("div");
  panel.className = "homologacion-resultado";
  panel.hidden = true;
  if (estado.puedeVerResultado) {
    const ver = crearTextoE4("button", "Ver resultado", "secundario");
    ver.type = "button";
    ver.addEventListener("click", async () => {
      if (!panel.hidden) {
        panel.hidden = true;
        ver.textContent = "Ver resultado";
        return;
      }
      ver.disabled = true;
      try {
        const datos = await cargarResultadoE4(fila.homologacion_id);
        dibujarResumenE4(panel, resumirHomologacion(datos.resultado));
        panel.hidden = false;
        ver.textContent = "Ocultar resultado";
      } catch (error) {
        avisarCorreo(aviso, mensajeError(error), "error");
      } finally {
        ver.disabled = false;
      }
    });
    const descargar = crearTextoE4("button", "Descargar JSON", "secundario");
    descargar.type = "button";
    descargar.addEventListener("click", () => descargarHomologacion(solicitud, fila.homologacion_id)
      .catch((error) => avisarCorreo(aviso, mensajeError(error), "error")));
    acciones.append(ver, descargar);
  }
  seccion.append(cabecera, crearTextoE4("p", estado.mensaje, "ayuda"), acciones, aviso, panel, crearBloqueCuadro(solicitud, fila, seccion));
  if (estado.activo || describirEstadoE5(fila).activo) programarActualizacionE4(seccion, solicitud);
  return seccion;
}

async function cargarDetalleProyecto() {
  const proyectoId = ui.proyectoId.value;
  const abiertos = new Set(
    [...ui.estadoSolicitudes.querySelectorAll("details[open]")].map((item) => item.dataset.solicitudId),
  );
  ui.estadoSolicitudes.replaceChildren();
  if (!proyectoId) return;
  const respuesta = await graphql(`query DetalleProyecto($id: uuid!) {
    solicitudes_cotizacion(
      where: { proyecto_id: { _eq: $id } }
      order_by: { created_at: desc }
    ) {
      id codigo nombre fecha_limite estado preparada_para_envio partida_critica
    }
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
    correos_proveedor(
      where: { solicitud_cotizacion: { proyecto_id: { _eq: $id } } }
      order_by: { recibido_at: desc }
    ) {
      id solicitud_id proveedor_id asunto cuerpo_texto adjuntos recibido_at fuera_plazo
      estado_correo origen_estado estado_asignado_at
    }
    documentos(
      where: {
        correo_id: { _is_null: false }
        solicitud_cotizacion: { proyecto_id: { _eq: $id } }
        tipo: { _in: ["cotizacion_proveedor", "ficha_tecnica_proveedor"] }
      }
      order_by: { created_at: desc }
    ) { id correo_id tipo nombre_original version documento_estado }
  }`, { id: proyectoId });
  if (ui.proyectoId.value !== proyectoId) return;
  const estadosE4 = await cargarEstadosE4(proyectoId);
  if (ui.proyectoId.value !== proyectoId) return;

  const aclaracionesPorProveedor = new Map();
  for (const aclaracion of respuesta.aclaraciones_proveedor) {
    const clave = `${aclaracion.solicitud_id}:${aclaracion.proveedor_id}`;
    if (!aclaracionesPorProveedor.has(clave)) aclaracionesPorProveedor.set(clave, []);
    aclaracionesPorProveedor.get(clave).push(aclaracion);
  }

  const participantesPorSolicitud = new Map();
  for (const participacion of respuesta.solicitud_proveedores) {
    if (!participantesPorSolicitud.has(participacion.solicitud_id)) participantesPorSolicitud.set(participacion.solicitud_id, []);
    participantesPorSolicitud.get(participacion.solicitud_id).push(participacion);
  }

  const documentosPorCorreo = new Map();
  for (const documento of respuesta.documentos) {
    if (!documentosPorCorreo.has(documento.correo_id)) documentosPorCorreo.set(documento.correo_id, []);
    documentosPorCorreo.get(documento.correo_id).push(documento);
  }

  const correosPorProveedor = new Map();
  for (const correo of respuesta.correos_proveedor) {
    correo.documentos = documentosPorCorreo.get(correo.id) ?? [];
    const clave = `${correo.solicitud_id}:${correo.proveedor_id}`;
    if (!correosPorProveedor.has(clave)) correosPorProveedor.set(clave, []);
    correosPorProveedor.get(clave).push(correo);
  }

  for (const solicitud of respuesta.solicitudes_cotizacion) {
    const participantes = participantesPorSolicitud.get(solicitud.id) ?? [];
    const respuestas = participantes.filter((item) => item.ultimo_correo_at).length;
    const conDocumentos = participantes.filter((item) => {
      const correos = correosPorProveedor.get(`${item.solicitud_id}:${item.proveedor_id}`) ?? [];
      return correos.some((correo) => correo.estado_correo !== "respuesta_sin_nueva_cotizacion_ni_ficha_tecnica");
    }).length;
    const accordion = document.createElement("details");
    accordion.className = `solicitud-accordion${solicitud.partida_critica ? " critica" : ""}`;
    accordion.dataset.solicitudId = solicitud.id;
    accordion.open = abiertos.has(solicitud.id);

    const resumen = document.createElement("summary");
    resumen.className = "solicitud-resumen";
    const identidad = document.createElement("span");
    identidad.className = "solicitud-identidad";
    const titulo = document.createElement("strong");
    titulo.textContent = `${solicitud.codigo} · ${solicitud.nombre}`;
    const estadoTexto = document.createElement("span");
    estadoTexto.textContent = solicitud.estado === "inicio" ? "En recepción de ofertas" : "Solicitud cerrada";
    identidad.append(titulo, estadoTexto);
    resumen.append(
      identidad,
      crearDatoResumen("Proveedores", String(participantes.length)),
      crearDatoResumen("Respuestas", `${respuestas} de ${participantes.length}`),
      crearDatoResumen("Con documentos", String(conDocumentos)),
    );
    const indicador = document.createElement("span");
    indicador.className = `badge ${solicitud.partida_critica ? "critica" : conDocumentos ? "respondio" : "pendiente"}`;
    indicador.textContent = solicitud.partida_critica ? "CRÍTICA" : conDocumentos ? "CON DOCUMENTOS" : "PENDIENTE";
    const chevron = document.createElement("span");
    chevron.className = "chevron";
    chevron.textContent = "⌄";
    resumen.append(indicador, chevron);

    const contenido = document.createElement("div");
    contenido.className = "solicitud-contenido";
    const barra = document.createElement("div");
    barra.className = "barra-solicitud";
    const fecha = document.createElement("p");
    fecha.className = "ayuda";
    fecha.textContent = `Fecha límite: ${solicitud.fecha_limite || "Sin fecha"}`;
    barra.append(fecha);
    if (solicitud.estado === "inicio" && solicitud.preparada_para_envio) {
      const cerrar = document.createElement("button");
      cerrar.type = "button";
      cerrar.className = "secundario";
      cerrar.textContent = "Cerrar solicitud";
      cerrar.addEventListener("click", () => cerrarSolicitud(solicitud));
      barra.append(cerrar);
    }
    contenido.append(barra);
    if (estadosE4) contenido.append(crearSeccionHomologacion(solicitud, estadosE4.get(solicitud.id) ?? null));

    const proveedores = document.createElement("div");
    proveedores.className = "proveedores-solicitud";
    for (const participacion of participantes) {
      const clave = `${participacion.solicitud_id}:${participacion.proveedor_id}`;
      proveedores.append(crearTarjetaProveedor(
        participacion,
        aclaracionesPorProveedor.get(clave) ?? [],
        correosPorProveedor.get(clave) ?? [],
      ));
    }
    if (!participantes.length) {
      const vacio = document.createElement("p");
      vacio.className = "ayuda";
      vacio.textContent = "No hay proveedores vinculados con esta solicitud.";
      proveedores.append(vacio);
    }
    contenido.append(proveedores);
    accordion.append(resumen, contenido);
    ui.estadoSolicitudes.append(accordion);
  }

  if (!respuesta.solicitudes_cotizacion.length) {
    const vacio = document.createElement("p");
    vacio.className = "ayuda";
    vacio.textContent = "Este proyecto todavía no tiene solicitudes de cotización.";
    ui.estadoSolicitudes.append(vacio);
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
    if (ui.solicitudes.classList.contains("oculto")) return;
    cargarNotificaciones().catch(() => {});
    cargarDetalleProyecto().catch(() => {});
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
    await cargarDetalleProyecto();
    await cargarProyectos(ui.proyectoId.value);
  } catch (error) {
    mostrarResultado(mensajeError(error), "error");
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
    await abrirProyecto(proyectoId);
    ui.panelNuevaSolicitud.classList.remove("oculto");
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

    const proyectoId = proyectoActivoId;
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
    ui.formSolicitud.reset();
    actualizarFechaInicio();
    ui.proyectoId.value = proyectoId;
    mostrarProyectoSeleccionado();
    ui.guardarSolicitud.disabled = false;
    ui.proveedores.replaceChildren();
    agregarProveedor();
    ui.panelNuevaSolicitud.classList.add("oculto");
    await cargarProyectos(proyectoId);
    await Promise.all([cargarDetalleProyecto(), actualizarCodigoSugerido()]);
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
ui.nuevoProyecto.addEventListener("click", () => {
  ui.registro.classList.remove("oculto");
  ui.registro.scrollIntoView({ behavior: "smooth", block: "start" });
});
ui.cancelarProyecto.addEventListener("click", () => {
  ui.registro.classList.add("oculto");
  ui.formProyecto.reset();
});
ui.irInicio.addEventListener("click", () => {
  if (nhost?.getUserSession()?.user) mostrarDashboard();
});
ui.volverProyectos.addEventListener("click", mostrarDashboard);
ui.nuevaSolicitud.addEventListener("click", () => {
  ui.panelNuevaSolicitud.classList.remove("oculto");
  ui.panelNuevaSolicitud.scrollIntoView({ behavior: "smooth", block: "start" });
});
ui.cancelarSolicitud.addEventListener("click", () => {
  ui.panelNuevaSolicitud.classList.add("oculto");
  ui.formSolicitud.reset();
  actualizarFechaInicio();
  ui.proyectoId.value = proyectoActivoId;
  mostrarProyectoSeleccionado();
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
