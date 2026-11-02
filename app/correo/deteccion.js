/* Reglas de identificación compartidas con el flujo de recepción de n8n.
 * No envía mensajes ni decide si una cotización es final.
 */
function direccion(valor) {
  if (valor && typeof valor === 'object') {
    const lista = valor.value ?? (Array.isArray(valor) ? valor : []);
    if (lista.length !== 1) return null;
    return direccion(lista[0].address ?? lista[0].email);
  }
  const texto = String(valor ?? '').trim();
  const angulos = [...texto.matchAll(/<([^<>]+)>/g)];
  const correo = (angulos.length === 1 ? angulos[0][1] : texto).trim();
  return /^[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+$/.test(correo)
    ? correo.toLowerCase() : null;
}

function cabeceras(mensaje) {
  const resultado = {};
  for (const item of mensaje.payload?.headers ?? []) {
    resultado[String(item.name).toLowerCase()] = item.value;
  }
  for (const [clave, valor] of Object.entries(mensaje.headers ?? {})) {
    resultado[clave.toLowerCase()] = valor;
  }
  return resultado;
}

function etiquetas(mensaje) {
  return (mensaje.labelIds ?? mensaje.labels ?? []).map(valor =>
    typeof valor === 'string' ? valor : valor.id);
}

function fechaMensaje(mensaje) {
  const valor = mensaje.internalDate
    ? Number(mensaje.internalDate) : mensaje.date ?? cabeceras(mensaje).date;
  if (valor === null || valor === undefined || valor === '') return null;
  const fecha = new Date(valor);
  return Number.isFinite(fecha.getTime()) ? fecha.toISOString() : null;
}

function normalizarCorreo(mensaje) {
  if (etiquetas(mensaje).some(valor => ['SENT', 'DRAFT', 'SPAM', 'TRASH'].includes(valor))) return null;
  const headers = cabeceras(mensaje);
  const remitente = direccion(mensaje.from ?? mensaje.From ?? headers.from);
  if (!remitente || !mensaje.id || !mensaje.threadId) return null;
  return {
    gmail_message_id: String(mensaje.id),
    gmail_thread_id: String(mensaje.threadId),
    remitente,
    asunto: String(mensaje.subject ?? mensaje.Subject ?? headers.subject ?? ''),
    fecha_recepcion: fechaMensaje(mensaje),
  };
}

function patronCorreo(correo) {
  // _ y % pueden existir en una dirección, pero no deben ser comodines de SQL.
  return correo.replace(/[\\%_]/g, valor => '\\' + valor);
}

function prepararCandidatos(respuesta, correo) {
  if (respuesta.errors?.length) throw new Error('Nhost rechazó la consulta de envíos: ' + respuesta.errors.map(e => e.message).join('; '));
  if (!Array.isArray(respuesta.data?.envios_solicitud)) throw new Error('Nhost no devolvió la lista de envíos.');
  const vistos = new Set();
  return respuesta.data.envios_solicitud.filter(envio => {
    const valido = ['enviado', 'respondido'].includes(envio.estado)
      && direccion(envio.destinatario) === correo.remitente
      && envio.mensaje_id && envio.solicitud_id && envio.proveedor_id && envio.id;
    if (!valido || vistos.has(envio.id)) return false;
    vistos.add(envio.id);
    return true;
  }).map(envio => ({ correo, envio }));
}

function identificarRespuestas(registros) {
  const grupos = new Map();
  for (const registro of registros) {
    const id = registro.correo.gmail_message_id;
    if (!grupos.has(id)) grupos.set(id, []);
    grupos.get(id).push(registro);
  }
  const resultado = [];
  for (const grupo of grupos.values()) {
    const correo = grupo[0].correo;
    const coincidencias = grupo.filter(({ envio, original }) => {
      if (original.error || String(original.id ?? '') !== String(envio.mensaje_id)) return false;
      if (!etiquetas(original).includes('SENT')) return false;
      if (String(original.threadId ?? '') !== correo.gmail_thread_id) return false;
      if (String(original.id) === correo.gmail_message_id) return false;
      const fechaEnvio = fechaMensaje(original);
      return !fechaEnvio || !correo.fecha_recepcion || correo.fecha_recepcion >= fechaEnvio;
    });
    if (coincidencias.length === 1) {
      const envio = coincidencias[0].envio;
      resultado.push({
        ...correo, estado_deteccion: 'detectado', envio_id: envio.id,
        solicitud_id: envio.solicitud_id, proveedor_id: envio.proveedor_id,
        gmail_message_id_envio: envio.mensaje_id,
        enlace_gmail: 'https://mail.google.com/mail/u/0/#all/' + correo.gmail_thread_id,
      });
    } else {
      resultado.push({
        ...correo, estado_deteccion: 'revisar',
        motivo: coincidencias.length > 1
          ? 'La conversación está vinculada a más de un envío.'
          : grupo.some(item => item.original.error)
            ? 'No se pudo consultar uno o más envíos originales en Gmail.'
            : 'El remitente es conocido, pero el correo no corresponde a una conversación enviada registrada.',
      });
    }
  }
  return resultado;
}

function completarDeteccion(respuesta, deteccion) {
  if (respuesta.errors?.length) throw new Error('Nhost rechazó la consulta de la solicitud.');
  const solicitud = respuesta.data?.solicitudes_cotizacion_by_pk;
  const proveedor = respuesta.data?.proveedores_by_pk;
  if (!solicitud || !proveedor) throw new Error('La solicitud o el proveedor ya no están disponibles.');
  return {
    ...deteccion,
    proveedor: proveedor.nombre,
    solicitud: solicitud.codigo,
    partida: solicitud.nombre,
    proyecto: solicitud.proyecto_asociado?.nombre ?? null,
    estado_solicitud: solicitud.estado,
  };
}

module.exports = { direccion, normalizarCorreo, patronCorreo, prepararCandidatos, identificarRespuestas, completarDeteccion };
