import { createClient } from "https://esm.sh/@nhost/nhost-js@4.9.0";

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
  avisosSeguimiento: document.querySelector("#avisos-seguimiento"),
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
const opcionesRolUsuario = { headers: { "x-hasura-role": "user" } };

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
  if (conectado) cargarProyectos().catch((error) => mostrarResultado(mensajeError(error), "error"));
  else ui.proyectoId.replaceChildren();
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
  await cargarAvisosSeguimiento();
}

function mostrarProyectoSeleccionado() {
  const proyecto = proyectosDisponibles.find((item) => item.id === ui.proyectoId.value);
  ui.proyectoCodigo.value = proyecto?.codigo ?? "";
  ui.proyectoNombre.value = proyecto?.nombre ?? "";
}

async function cargarAvisosSeguimiento() {
  const proyectoId = ui.proyectoId.value;
  ui.avisosSeguimiento.replaceChildren();
  if (!proyectoId) return;
  const respuesta = await graphql(`query SolicitudesParaSeguimiento($id: uuid!) {
    solicitudes_cotizacion(where: {
      proyecto_id: { _eq: $id }, estado: { _in: ["lista", "en_proceso"] }
    }) { codigo nombre created_at fecha_limite frecuencia_aviso_dias }
  }`, { id: proyectoId });
  if (ui.proyectoId.value !== proyectoId) return;
  const fechaHoy = new Date().toLocaleDateString("en-CA", { timeZone: "America/Lima" });
  const diaHoy = Date.parse(`${fechaHoy}T00:00:00Z`);
  for (const solicitud of respuesta.solicitudes_cotizacion) {
    const fechaInicio = new Date(solicitud.created_at)
      .toLocaleDateString("en-CA", { timeZone: "America/Lima" });
    const dias = Math.floor((diaHoy - Date.parse(`${fechaInicio}T00:00:00Z`)) / 86400000);
    const vencida = solicitud.fecha_limite && solicitud.fecha_limite < fechaHoy;
    if (!vencida && (dias < solicitud.frecuencia_aviso_dias || dias % solicitud.frecuencia_aviso_dias !== 0)) continue;
    const aviso = document.createElement("li");
    aviso.textContent = `${solicitud.codigo} — ${solicitud.nombre}: ${vencida ? "fecha fin vencida" : "revisar seguimiento"}.`;
    ui.avisosSeguimiento.append(aviso);
  }
  if (!ui.avisosSeguimiento.children.length) {
    const vacio = document.createElement("li");
    vacio.textContent = "No hay avisos pendientes hoy.";
    ui.avisosSeguimiento.append(vacio);
  }
}

async function actualizarCodigoSugerido() {
  const proyectoId = ui.proyectoId.value;
  ui.codigoSugerido.value = "";
  if (!proyectoId) return;
  const tipo = ui.tipoSolicitud.value;
  const respuesta = await graphql(`query CodigosDelUsuario {
    solicitudes_cotizacion { codigo }
  }`);
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
  const where = proveedor.ruc
    ? { ruc: { _eq: proveedor.ruc } }
    : proveedor.correo
      ? { correo: { _ilike: proveedor.correo } }
      : null;

  if (where) {
    const busqueda = await graphql(
      `query BuscarProveedor($where: proveedores_bool_exp!) {
        proveedores(where: $where, limit: 1) { id }
      }`,
      { where },
    );
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
      `mutation MarcarSolicitudLista($id: uuid!) {
        update_solicitudes_cotizacion_by_pk(pk_columns: { id: $id }, _set: { estado: "lista" }) { id }
      }`,
      { id: solicitudId },
    );

    mostrarResultado(`Solicitud ${solicitud.codigo} creada correctamente. Identificador: ${solicitudId}`, "exito");
    cargarAvisosSeguimiento().catch((error) => mostrarResultado(mensajeError(error), "error"));
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
ui.formProyecto.addEventListener("submit", registrarProyecto);
ui.proyectoId.addEventListener("change", () => {
  ui.guardarSolicitud.disabled = !ui.proyectoId.value;
  mostrarProyectoSeleccionado();
  actualizarCodigoSugerido().catch((error) => mostrarResultado(mensajeError(error), "error"));
  cargarAvisosSeguimiento().catch((error) => mostrarResultado(mensajeError(error), "error"));
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
