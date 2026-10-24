import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

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

let supabase;

function mostrarResultado(mensaje, tipo = "") {
  ui.resultado.textContent = mensaje;
  ui.resultado.className = `resultado ${tipo}`;
}

function mensajeError(error) {
  return error?.message || "Ocurrió un error inesperado.";
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

async function configurarSupabase() {
  try {
    const config = await import("./config.local.js");
    if (!config.SUPABASE_URL || !config.SUPABASE_PUBLISHABLE_KEY) throw new Error("Configuración incompleta");
    supabase = createClient(config.SUPABASE_URL, config.SUPABASE_PUBLISHABLE_KEY);
    const { data } = await supabase.auth.getSession();
    mostrarSesion(data.session);
    supabase.auth.onAuthStateChange((_evento, session) => mostrarSesion(session));
  } catch (_error) {
    ui.configuracion.classList.remove("oculto");
    ui.configuracion.textContent = "Falta frontend/js/config.local.js. Copia config.example.js y completa la URL y la clave pública de Supabase.";
    ui.acceso.classList.add("oculto");
  }
}

async function autenticar(crear = false) {
  const email = document.querySelector("#correo-acceso").value.trim();
  const password = document.querySelector("#clave-acceso").value;
  const operacion = crear
    ? supabase.auth.signUp({ email, password })
    : supabase.auth.signInWithPassword({ email, password });
  const { data, error } = await operacion;
  if (error) throw error;
  if (crear && !data.session) alert("Revisa tu correo para confirmar la cuenta antes de ingresar.");
}

async function obtenerOCrearProyecto(userId, datos) {
  const proyecto = {
    responsable_id: userId,
    codigo: datos.get("proyecto_codigo").trim(),
    nombre: datos.get("proyecto_nombre").trim(),
  };
  const { data, error } = await supabase
    .from("proyectos")
    .upsert(proyecto, { onConflict: "responsable_id,codigo" })
    .select("id")
    .single();
  if (error) throw error;
  return data.id;
}

async function crearSolicitud(proyectoId, userId, datos) {
  const solicitud = {
    proyecto_id: proyectoId,
    creado_por: userId,
    codigo: datos.get("solicitud_codigo").trim(),
    nombre: datos.get("solicitud_nombre").trim(),
    moneda: datos.get("moneda"),
    vigencia_dias: Number(datos.get("vigencia_dias")),
    fecha_limite: limpiar(datos.get("fecha_limite")),
    estado: "borrador",
  };
  const { data, error } = await supabase.from("solicitudes_cotizacion").insert(solicitud).select("id").single();
  if (error) throw error;
  return data.id;
}

async function guardarProveedor(userId, proveedor) {
  let consulta = supabase.from("proveedores").select("id").eq("creado_por", userId);
  consulta = proveedor.ruc ? consulta.eq("ruc", proveedor.ruc) : consulta.ilike("correo", proveedor.correo);
  const { data: existente, error: errorBusqueda } = await consulta.maybeSingle();
  if (errorBusqueda) throw errorBusqueda;
  if (existente) return existente.id;

  const { data, error } = await supabase
    .from("proveedores")
    .insert({ ...proveedor, creado_por: userId })
    .select("id")
    .single();
  if (error) throw error;
  return data.id;
}

async function guardarProveedores(solicitudId, userId, proveedores) {
  for (const proveedor of proveedores) {
    const proveedorId = await guardarProveedor(userId, proveedor);
    const { error } = await supabase.from("solicitud_proveedores").insert({
      solicitud_id: solicitudId,
      proveedor_id: proveedorId,
    });
    if (error) throw error;
  }
}

async function subirDocumento(solicitudId, userId, tipo, archivo) {
  validarExcel(archivo, tipo);
  const ruta = `${solicitudId}/entrada/${tipo}-${Date.now()}-${nombreSeguro(archivo.name)}`;
  const { error: errorCarga } = await supabase.storage.from("solicitudes").upload(ruta, archivo, {
    contentType: mimeExcel(archivo),
    upsert: false,
  });
  if (errorCarga) throw errorCarga;

  const { error: errorRegistro } = await supabase.from("documentos").insert({
    solicitud_id: solicitudId,
    tipo,
    nombre_original: archivo.name,
    storage_path: ruta,
    mime_type: mimeExcel(archivo),
    tamano_bytes: archivo.size,
    subido_por: userId,
  });
  if (errorRegistro) {
    await supabase.storage.from("solicitudes").remove([ruta]);
    throw errorRegistro;
  }
}

async function registrarSolicitud(evento) {
  evento.preventDefault();
  ui.guardarSolicitud.disabled = true;
  mostrarResultado("Creando solicitud y subiendo documentos…");
  try {
    const { data: sesion } = await supabase.auth.getSession();
    const userId = sesion.session?.user?.id;
    if (!userId) throw new Error("La sesión venció. Vuelve a ingresar.");

    const datos = new FormData(ui.formSolicitud);
    const proveedores = leerProveedores();
    if (!proveedores.length) throw new Error("Agrega al menos un proveedor.");

    const proyectoId = await obtenerOCrearProyecto(userId, datos);
    const solicitudId = await crearSolicitud(proyectoId, userId, datos);
    await guardarProveedores(solicitudId, userId, proveedores);

    for (const tipo of ["itemizado", "plantilla_comparativo", "cuadro_procura"]) {
      const archivo = datos.get(tipo);
      if (!(archivo instanceof File) || !archivo.size) throw new Error(`Falta el archivo ${tipo}.`);
      await subirDocumento(solicitudId, userId, tipo, archivo);
    }

    const { error } = await supabase
      .from("solicitudes_cotizacion")
      .update({ estado: "lista" })
      .eq("id", solicitudId);
    if (error) throw error;

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
  try { await autenticar(true); } catch (error) { alert(mensajeError(error)); }
});
ui.cerrarSesion.addEventListener("click", () => supabase.auth.signOut());
ui.agregarProveedor.addEventListener("click", agregarProveedor);
ui.formSolicitud.addEventListener("submit", registrarSolicitud);

agregarProveedor();
configurarSupabase();
