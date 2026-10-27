/* Homologación: las decisiones del modelo son propuestas con evidencia. */
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function datos(respuesta) {
  if (respuesta.errors?.length) throw new Error('Nhost: ' + respuesta.errors.map(e => e.message).join('; '));
  if (!respuesta.data) throw new Error('Nhost no devolvió datos.');
  return respuesta.data;
}
function espera(motivo, extra = {}) {
  return { ...extra, estado: 'esperando_insumos', habilitado_para_cuadro: false, motivo };
}
function prepararEntrada(entrada = {}) {
  const id = entrada.solicitud_id || null;
  if (id && !UUID.test(id)) throw new Error('solicitud_id debe ser un UUID válido.');
  const tc = entrada.tipo_cambio ?? null;
  if (tc && (!(Number(tc.valor) > 0) || tc.sentido !== 'USD_PEN'
    || !/^\d{4}-\d{2}-\d{2}$/.test(tc.fecha ?? '') || !tc.fuente || !tc.aprobado_por)) {
    throw new Error('El cambio requiere valor positivo, sentido USD_PEN, fecha, fuente y aprobado_por.');
  }
  return { solicitud_id: id, tipo_cambio: tc };
}
function seleccionarParticipaciones(respuesta, entrada) {
  const filas = datos(respuesta).solicitud_proveedores;
  if (!Array.isArray(filas)) throw new Error('Falta solicitud_proveedores.');
  if (filas.length > 200) throw new Error('Hay más de 200 participaciones; filtra por solicitud_id.');
  const aptas = filas.filter(p => p.estado_respuesta === 'envio_cotizacion'
    && p.detalle_respuesta === 'cotizacion_definitiva' && p.considerado === true
    && (!entrada.solicitud_id || p.solicitud_id === entrada.solicitud_id));
  return aptas.length ? aptas.map(p => ({ ...p, entrada, estado: 'consultar_version' }))
    : [espera('No hay proveedores con estado envio_cotizacion y cotización definitiva disponibles en Nhost.')];
}
function seleccionarVersion(respuesta, candidato, contrato) {
  const d = datos(respuesta), p = d.participacion;
  const base = { solicitud_id: candidato.solicitud_id, proveedor_id: candidato.proveedor_id };
  if (!p || p.estado_respuesta !== 'envio_cotizacion' || !p.considerado
    || p.detalle_respuesta !== 'cotizacion_definitiva') return espera('El proveedor todavía no tiene cotización definitiva.', base);
  if ((d.aclaraciones ?? []).length) return espera('Hay aclaraciones abiertas.', base);
  if (!d.solicitud || !d.proveedor) throw new Error('Solicitud o proveedor no disponible.');
  if (d.versiones.length > 100 || d.documentos.length > 200 || d.partidas.length > 1000)
    throw new Error('La consulta superó el tamaño admitido; no se comparará un lote incompleto.');
  const versiones = d.versiones.filter(v => v.solicitud_id === base.solicitud_id && v.proveedor_id === base.proveedor_id);
  const finales = versiones.filter(v => v.es_final === true && v.estado === 'vigente' && v.origen === 'correo');
  if (finales.length !== 1) return espera('Falta identificar una única versión final vigente del proveedor.', base);
  const version = finales[0];
  if (versiones.some(v => v.estado !== 'anulada' && v.version > version.version))
    return espera('Existe una versión posterior: debe resolverse cuál es la cotización definitiva.', base);
  const plantillas = d.documentos.filter(x => x.tipo === 'plantilla_comparativo');
  if (plantillas.length !== 1 || plantillas[0].nombre_original !== contrato.archivo)
    return espera('La solicitud no tiene identificada la plantilla compartida de ascensores; revisa su mapeo.', base);
  if (!d.partidas.length) return espera('Falta cargar el itemizado de la solicitud.', base);
  const documentos = d.documentos.filter(x => x.version_id === version.id && x.tipo === 'cotizacion_proveedor'
    && x.proveedor_id === base.proveedor_id && x.solicitud_id === base.solicitud_id);
  if (!documentos.length || documentos.some(x => !UUID.test(x.storage_file_id ?? '')))
    return espera('La versión final todavía no tiene todos sus documentos disponibles.', { ...base, version_id: version.id });
  const contexto = { ...base, participacion: p, version, solicitud: d.solicitud, proveedor: d.proveedor,
    partidas: d.partidas, plantilla: plantillas[0], contrato, documentos,
    correo: d.correos.find(c => c.gmail_message_id === version.gmail_message_id) ?? null,
    tipo_cambio: candidato.entrada.tipo_cambio };
  return { estado: 'leer_documentos', contexto };
}
function tipoArchivo(doc) {
  const ext = /\.([^.]+)$/.exec(doc.nombre_original ?? '')?.[1].toLowerCase();
  return doc.mime_type === 'application/pdf' || ext === 'pdf' ? 'pdf'
    : ['xlsx', 'xls', 'csv'].includes(ext) ? ext : 'otro';
}
function textoArchivo(items, documento) {
  const fallo = items.find(x => x.error);
  if (fallo) return { documento, texto: null, error: String(fallo.error.message ?? fallo.error) };
  const texto = tipoArchivo(documento) === 'pdf'
    ? items.map(x => x.text ?? '').join('\n') : items.map(x => JSON.stringify(x)).join('\n');
  return { documento, texto: texto.trim() || null,
    error: texto.trim() ? null : 'Archivo sin texto legible; requiere OCR o revisión.' };
}
function prepararPeticiones(archivos) {
  const grupos = new Map();
  for (const a of archivos) {
    if (!a.contexto) throw new Error('Falta el contexto del documento.');
    const key = a.contexto.version.id;
    if (!grupos.has(key)) grupos.set(key, []);
    grupos.get(key).push(a);
  }
  return [...grupos.values()].map(grupo => {
    const c = grupo[0].contexto;
    const ids = new Set(grupo.map(x => x.documento.id));
    if (ids.size !== grupo.length || ids.size !== c.documentos.length
      || c.documentos.some(x => !ids.has(x.id))) return espera('Faltan archivos de la versión; no se homologará parcialmente.', c);
    if (grupo.some(x => !x.texto || x.error)) return espera('Hay archivos no legibles o un formato no soportado.', {
      solicitud_id: c.solicitud_id, proveedor_id: c.proveedor_id, version_id: c.version.id,
      archivos: grupo.map(x => ({ documento_id: x.documento.id, error: x.error })) });
    const fuentes = grupo.map(x => ({ id: x.documento.id, nombre: x.documento.nombre_original, texto: x.texto }));
    if (c.correo?.cuerpo_texto) fuentes.push({ id: 'correo:' + c.correo.gmail_message_id, nombre: 'Cuerpo del correo final', texto: c.correo.cuerpo_texto });
    const peticion = JSON.stringify({ solicitud: c.solicitud, proveedor: c.proveedor.nombre,
      version_id: c.version.id, alcance: c.partidas,
      campos_comparar: c.contrato.campos, fuentes });
    if (peticion.length > 24000) return espera('La propuesta supera la entrada configurada del modelo; requiere lectura por secciones, sin recortar documentos.', {
      solicitud_id: c.solicitud_id, proveedor_id: c.proveedor_id, version_id: c.version.id });
    return { estado: 'homologar', contexto: c, fuentes, peticion };
  });
}
function normalizarTexto(v) { return String(v ?? '').normalize('NFKC').replace(/\s+/g, ' ').trim().toLowerCase(); }
function evidenciaValida(campo, fuentes) {
  if (!campo || campo.valor_texto === null || campo.valor_texto === '') return false;
  const fuente = fuentes.find(f => f.id === campo.documento_id);
  const cita = normalizarTexto(campo.cita), valor = normalizarTexto(campo.valor_texto);
  return !!fuente && cita.length >= 4 && normalizarTexto(fuente.texto).includes(cita) && cita.includes(valor);
}
function numero(texto) {
  if (texto === null || texto === undefined || texto === '') return null;
  const t = String(texto).replace(/(?:US\$|USD|PEN|S\/|\$)/gi, '').trim();
  if (/^-?\d+$/.test(t)) return Number(t);
  if (/^-?\d+[.,]\d{1,2}$/.test(t)) return Number(t.replace(',', '.'));
  if (/^-?\d{1,3}(?:,\d{3})+\.\d{1,4}$/.test(t)) return Number(t.replace(/,/g, ''));
  if (/^-?\d{1,3}(?:\.\d{3})+,\d{1,4}$/.test(t)) return Number(t.replace(/\./g, '').replace(',', '.'));
  return null; // Nunca decidir si 1,234 representa miles o decimales sin evidencia adicional.
}
function validarPropuesta(salida, preparado) {
  let m = salida.output ?? salida.text ?? salida;
  if (typeof m === 'string') m = JSON.parse(m);
  if (!Array.isArray(m.campos) || !Array.isArray(m.items)) throw new Error('La IA no devolvió el formato de homologación.');
  const c = preparado.contexto, pendientes = [], trazabilidad = [];
  const campos = c.contrato.campos.map(def => {
    const candidatos = m.campos.filter(x => x.campo_id === def.id);
    const f = candidatos.length === 1 ? candidatos[0] : null;
    const valido = evidenciaValida(f, preparado.fuentes);
    if (!valido) pendientes.push({ campo: def.id, motivo: 'No encontrado o sin evidencia verificable.', bloqueante: def.obligatorio });
    if (valido) trazabilidad.push({ campo: def.id, documento_id: f.documento_id, cita: f.cita,
      pagina: null, pagina_propuesta: f.pagina ?? null });
    return { campo_id: def.id, descripcion: def.descripcion, valor_original: valido ? f.valor_texto : null,
      estado: valido ? 'extraido_con_evidencia' : 'faltante' };
  });
  const items = m.items.map((item, index) => {
    const original = {};
    for (const campo of ['descripcion', 'cantidad', 'unidad', 'precio_unitario', 'parcial']) {
      const f = item[campo], valido = evidenciaValida(f, preparado.fuentes);
      original[campo] = valido ? f.valor_texto : null;
      if (valido) trazabilidad.push({ item: index, campo, documento_id: f.documento_id, cita: f.cita,
        pagina: null, pagina_propuesta: f.pagina ?? null });
    }
    const propuesta = c.partidas.find(p => p.id === item.partida_id_propuesta) ?? null;
    pendientes.push({ item: index, campo: 'correspondencia_tecnica', bloqueante: true,
      motivo: propuesta ? 'Correspondencia propuesta por IA; requiere validación técnica.' : 'No se pudo proponer una partida de base.' });
    for (const k of ['cantidad', 'precio_unitario', 'parcial']) if (numero(original[k]) === null)
      pendientes.push({ item: index, campo: k, motivo: 'Valor ausente o número ambiguo.', bloqueante: true });
    return { original, valores_numericos_originales: { cantidad: numero(original.cantidad),
      precio_unitario: numero(original.precio_unitario), parcial: numero(original.parcial) },
      partida_id_propuesta: propuesta?.id ?? null, motivo_propuesta: String(item.motivo_correspondencia ?? ''),
      correspondencia: 'pendiente_especialista', comparable: null };
  });
  if (!items.length) pendientes.push({ campo: 'items', motivo: 'La propuesta no contiene precios o ítems verificables.', bloqueante: true });
  if (campos.some(f => f.campo_id === 'moneda' && /USD|US\$|d[oó]lar/i.test(f.valor_original ?? ''))
    && c.solicitud.moneda === 'PEN' && !c.tipo_cambio)
    pendientes.push({ campo: 'tipo_cambio', motivo: 'Falta tipo de cambio autorizado para comparar en soles.', bloqueante: true });
  return { estado: 'homologacion_propuesta', estado_revision: 'requiere_revision', habilitado_para_cuadro: false,
    solicitud_id: c.solicitud_id, proveedor_id: c.proveedor_id, version_id: c.version.id,
    proyecto: c.solicitud.proyecto_asociado, especialidad: 'ASCENSORES',
    base: c.partidas, moneda_comparacion: c.solicitud.moneda, tipo_cambio: c.tipo_cambio,
    postores: [{ id: c.proveedor_id, nombre: c.proveedor.nombre, version: c.version,
      archivos: c.documentos.map(d => ({ documento_id: d.id, storage_file_id: d.storage_file_id })), campos }],
    partidas: items, trazabilidad, pendientes, escenarios: [], decisiones: [],
    plantilla: { documento_id: c.plantilla.id, storage_file_id: c.plantilla.storage_file_id,
      nombre: c.plantilla.nombre_original, contrato: c.contrato.id },
    observaciones_ia: m.observaciones ?? [] };
}
function comprobarVigencia(respuesta, propuesta) {
  const d = datos(respuesta), v = d.version, p = d.participacion;
  if (!v || !v.es_final || v.estado !== 'vigente' || v.origen !== 'correo'
    || !p?.considerado || p.estado_respuesta !== 'envio_cotizacion'
    || p.detalle_respuesta !== 'cotizacion_definitiva' || d.posteriores.length || d.aclaraciones.length)
    return espera('La cotización cambió durante la lectura; vuelve a ejecutar con la versión final confirmada.', {
      solicitud_id: propuesta.solicitud_id, proveedor_id: propuesta.proveedor_id, version_id: propuesta.version_id });
  return propuesta;
}
module.exports = { datos, espera, prepararEntrada, seleccionarParticipaciones, seleccionarVersion,
  tipoArchivo, textoArchivo, prepararPeticiones, evidenciaValida, numero, validarPropuesta, comprobarVigencia };
