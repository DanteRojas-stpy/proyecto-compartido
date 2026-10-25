import { createClient } from "https://esm.sh/@nhost/nhost-js@4.9.0";

const ui = {
  configuracion: document.querySelector("#configuracion"),
  acceso: document.querySelector("#acceso"),
  registro: document.querySelector("#registro"),
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
  ui.cerrarSesion.classList.toggle("oculto", !conectado);
  ui.usuarioActivo.textContent = conectado ? session.user.email : "";
}

async function graphql(query, variables = {}) {
  const respuesta = await nhost.graphql.request({ query, variables });
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

async function obtenerOCrearProyecto(datos) {
  const respuesta = await graphql(
    `mutation GuardarProyecto($objeto: proyectos_insert_input!) {
      insert_proyectos_one(
        object: $objeto
        on_conflict: {
          constraint: proyectos_responsable_codigo_unique
          update_columns: [nombre]
        }
      ) { id }
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
      insert_solicitudes_cotizacion_one(object: $objeto) { id }
    }`,
    {
      objeto: {
        proyecto_id: proyectoId,
        codigo: datos.get("solicitud_codigo").trim(),
        nombre: datos.get("solicitud_nombre").trim(),
        moneda: datos.get("moneda"),
        vigencia_dias: Number(datos.get("vigencia_dias")),
        fecha_limite: limpiar(datos.get("fecha_limite")),
      },
    },
  );
  return respuesta.insert_solicitudes_cotizacion_one.id;
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
    if (busqueda.proveedores[0]) return busqueda.proveedores[0].id;
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
        insert_solicitud_proveedores_one(object: $objeto) { solicitud_id }
      }`,
      { objeto: { solicitud_id: solicitudId, proveedor_id: proveedorId } },
    );
  }
}

async function subirDocumento(solicitudId, tipo, archivo) {
  validarExcel(archivo, tipo);
  const nombre = `${solicitudId}-${tipo}-${Date.now()}-${nombreSeguro(archivo.name)}`;
  const carga = await nhost.storage.uploadFiles({
    "bucket-id": "solicitudes",
    "file[]": [archivo],
    "metadata[]": [{ name, metadata: { solicitudId, tipo } }],
  });
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
    await nhost.storage.deleteFile(archivoGuardado.id).catch(() => {});
    throw error;
  }
}

async function registrarSolicitud(evento) {
  evento.preventDefault();
  ui.guardarSolicitud.disabled = true;
  mostrarResultado("Creando solicitud y subiendo documentos…");
  try {
    if (!nhost.getUserSession()?.user?.id) throw new Error("La sesión venció. Vuelve a ingresar.");

    const datos = new FormData(ui.formSolicitud);
    const proveedores = leerProveedores();
    if (!proveedores.length) throw new Error("Agrega al menos un proveedor.");

    const proyectoId = await obtenerOCrearProyecto(datos);
    const solicitudId = await crearSolicitud(proyectoId, datos);
    await guardarProveedores(solicitudId, proveedores);

    for (const tipo of ["itemizado", "plantilla_comparativo", "cuadro_procura"]) {
      const archivo = datos.get(tipo);
      if (!(archivo instanceof File) || !archivo.size) throw new Error(`Falta el archivo ${tipo}.`);
      await subirDocumento(solicitudId, tipo, archivo);
    }

    await graphql(
      `mutation MarcarSolicitudLista($id: uuid!) {
        update_solicitudes_cotizacion_by_pk(pk_columns: { id: $id }, _set: { estado: "lista" }) { id }
      }`,
      { id: solicitudId },
    );

    mostrarResultado(`Solicitud creada correctamente. Identificador: ${solicitudId}`, "exito");
    ui.formSolicitud.reset();
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
ui.formSolicitud.addEventListener("submit", registrarSolicitud);

agregarProveedor();
configurarNhost();
