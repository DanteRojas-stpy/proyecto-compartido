// Lógica de pantalla de E4 (homologación). No toca el DOM: app.js dibuja lo que este módulo decide.
// Así se puede probar con Node sin navegador.

const ACTIVOS = new Set(["pendiente", "en_curso"]);

function plural(cantidad, singular, plurales) {
  return `${cantidad} ${cantidad === 1 ? singular : plurales}`;
}

// Qué mostrar y qué botones habilitar según el estado que entrega e4_estado_solicitud.
export function describirEstadoE4(fila) {
  const finales = fila?.finales_e3 ?? 0;
  const estado = fila?.e4_estado ?? null;
  const hayResultado = Boolean(fila?.homologacion_id);
  const base = { puedeVerResultado: hayResultado, activo: false, puedeHomologar: false, etiqueta: "Homologar" };

  if (ACTIVOS.has(estado)) {
    return { ...base, activo: true, etiqueta: "Homologando…", badge: { texto: "EN CURSO", clase: "pendiente" },
      mensaje: "Homologando las cotizaciones finales. Puede tardar un par de minutos; te avisaremos al terminar." };
  }
  if (finales === 0) {
    return { ...base, badge: { texto: "SIN FINALES", clase: "pendiente" },
      mensaje: "Todavía no hay cotizaciones aceptadas como finales. Acepta al menos una desde el estado de su correo para poder homologar." };
  }
  const puedeHomologar = true;
  const lista = plural(finales, "cotización final", "cotizaciones finales");
  if (estado === "error") {
    return { ...base, puedeHomologar, etiqueta: "Reintentar homologación", badge: { texto: "CON ERROR", clase: "critica" },
      mensaje: fila.e4_error ?? "La homologación no terminó. Vuelve a solicitarla." };
  }
  if (hayResultado) {
    const etiqueta = "Volver a homologar";
    if (fila.estado_revision === "listo_para_cuadro") {
      return { ...base, puedeHomologar, etiqueta, badge: { texto: "LISTA", clase: "respondio" },
        mensaje: `Homologación lista para generar el cuadro comparativo. Hay ${lista} aceptada${finales === 1 ? "" : "s"}.` };
    }
    return { ...base, puedeHomologar, etiqueta, badge: { texto: "CON PENDIENTES", clase: "pendiente" },
      mensaje: "La homologación tiene pendientes que debes revisar antes de generar el cuadro comparativo." };
  }
  return { ...base, puedeHomologar, badge: { texto: "SIN HOMOLOGAR", clase: "pendiente" },
    mensaje: `Hay ${lista} para homologar.` };
}

export function formatearImporte(valor, moneda) {
  if (valor === null || valor === undefined) return "—";
  const numero = Number(valor);
  if (!Number.isFinite(numero)) return "—";
  const texto = numero.toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return moneda ? `${moneda} ${texto}` : texto;
}

const ESTADOS_OFERTA = {
  cotizado: "Cotizado", incluido_con_evidencia: "Incluido", global: "Precio global", no_cotizado: "No cotizó", pendiente: "Pendiente",
};
const EQUIVALENCIAS = { equivalente: "Equivalente", no_equivalente: "No equivalente", pendiente: "Equivalencia pendiente" };

// Resumen legible de homologacion.json para mostrarlo en la tarjeta de la solicitud.
export function resumirHomologacion(resultado) {
  const r = resultado ?? {};
  const nombres = new Map([...(r.postores ?? []), ...(r.proveedores_sin_final ?? [])].map((p) => [p.proveedor_id, p.nombre]));
  const nombre = (id) => nombres.get(id) ?? "Proveedor";
  const pendientes = (r.pendientes ?? []).map((p) => ({
    bloquea: Boolean(p.bloquea_comparacion), proveedor: p.proveedor_id ? nombre(p.proveedor_id) : null,
    motivo: p.motivo, decision: p.decision_requerida,
  }));
  const bloqueantes = pendientes.filter((p) => p.bloquea).length;
  return {
    estado: r.estado_revision === "listo_para_cuadro" ? "Lista para el cuadro" : "Requiere revisión",
    moneda: r.moneda_comparacion ?? null,
    base: r.base?.tipo === "itemizado" ? "Itemizado de la solicitud" : "Base provisional (el itemizado no está cargado)",
    postores: (r.postores ?? []).map((p) => ({
      nombre: p.nombre, moneda: p.moneda ?? null, comparable: p.comparable_en_moneda_de_comparacion !== false,
      total: p.totales_originales?.total ?? null,
      porDocumento: (p.totales_por_documento ?? []).map((d) => d.total).filter((t) => t !== null && t !== undefined),
      plazo: p.condiciones?.plazo_entrega ?? null, vigencia: p.condiciones?.vigencia_oferta ?? null,
    })),
    partidas: (r.partidas ?? []).map((partida) => ({
      titulo: [partida.codigo, partida.descripcion].filter(Boolean).join(" · "),
      ofertas: partida.ofertas.map((o) => ({
        proveedor: nombre(o.proveedor_id), estado: ESTADOS_OFERTA[o.estado] ?? o.estado,
        equivalencia: EQUIVALENCIAS[o.equivalencia] ?? o.equivalencia, items: o.items.length,
      })),
    })),
    adicionales: (r.adicionales ?? []).length,
    pendientes, bloqueantes, informativos: pendientes.length - bloqueantes,
  };
}

export function nombreArchivoHomologacion(codigoSolicitud, fechaIso) {
  const codigo = String(codigoSolicitud ?? "solicitud").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^A-Za-z0-9._-]+/g, "-");
  return `homologacion-${codigo}-${String(fechaIso ?? "").slice(0, 10) || "sin-fecha"}.json`;
}

// ---- E5: cuadro comparativo ---------------------------------------------------------------------------

// Qué mostrar y qué botones habilitar para el cuadro, según el estado que entrega e4_estado_solicitud.
export function describirEstadoE5(fila) {
  const hayHomologacion = Boolean(fila?.homologacion_id);
  const estado = fila?.e5_estado ?? null;
  const archivo = Boolean(fila?.cuadro_storage_file_id) && (estado === "borrador" || estado === "validado");
  const base = { activo: false, puedeGenerar: false, puedeDescargar: archivo, etiqueta: "Generar cuadro" };

  if (ACTIVOS.has(estado)) {
    return { ...base, activo: true, etiqueta: "Generando…", badge: { texto: "EN CURSO", clase: "pendiente" },
      mensaje: "Generando el cuadro comparativo en tu plantilla. Te avisaremos al terminar." };
  }
  if (!hayHomologacion) {
    return { ...base, badge: { texto: "SIN HOMOLOGAR", clase: "pendiente" },
      mensaje: "Primero homologa las cotizaciones finales (E4) para poder generar el cuadro." };
  }
  const puedeGenerar = true;
  if (estado === "error") {
    return { ...base, puedeGenerar, etiqueta: "Reintentar cuadro", badge: { texto: "CON ERROR", clase: "critica" },
      mensaje: fila.e5_error ?? "El cuadro no terminó. Vuelve a solicitarlo." };
  }
  if (estado === "validado") {
    return { ...base, puedeGenerar, etiqueta: "Volver a generar", badge: { texto: "VALIDADO", clase: "respondio" },
      mensaje: `Cuadro comparativo validado (revisión ${fila.e5_revision}).` };
  }
  if (estado === "borrador") {
    return { ...base, puedeGenerar, etiqueta: "Volver a generar", badge: { texto: "BORRADOR", clase: "pendiente" },
      mensaje: `Cuadro generado como borrador (revisión ${fila.e5_revision}): tiene pendientes o comprobaciones sin cumplir.` };
  }
  const aviso = fila.estado_revision === "listo_para_cuadro" ? "" : " La homologación tiene pendientes: el cuadro saldrá como borrador.";
  return { ...base, puedeGenerar, badge: { texto: "SIN CUADRO", clase: "pendiente" }, mensaje: `Listo para generar el cuadro.${aviso}` };
}

// El tipo de cambio es opcional; si se indica, debe traer valor, fecha y fuente (E4 y E5 nunca lo inventan).
export function leerTipoCambio({ valor, fecha, fuente }) {
  const texto = String(valor ?? "").trim().replace(",", ".");
  if (!texto && !String(fecha ?? "").trim() && !String(fuente ?? "").trim()) return { tipoCambio: null };
  const numero = Number(texto);
  if (!texto || !Number.isFinite(numero) || numero <= 0) return { error: "El tipo de cambio debe ser un número mayor que cero." };
  if (!String(fecha ?? "").trim()) return { error: "Indica la fecha del tipo de cambio." };
  if (!String(fuente ?? "").trim()) return { error: "Indica la fuente del tipo de cambio (por ejemplo, SBS)." };
  return { tipoCambio: { valor: numero, fecha: String(fecha).trim(), fuente: String(fuente).trim() } };
}

export function nombreArchivoCuadro(nombreGuardado, codigoSolicitud, revision) {
  if (nombreGuardado) return nombreGuardado;
  const codigo = String(codigoSolicitud ?? "solicitud").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^A-Za-z0-9._-]+/g, "-");
  return `cuadro-${codigo}-rev${revision ?? 1}.xlsx`;
}
