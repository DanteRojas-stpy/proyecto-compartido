// E4 en n8n: prepara lo que ve el modelo, valida su respuesta y construye homologacion.json.
// Es el equivalente de app/homologacion/entrada.py + contrato.py (request, parse_text) + construir.py, en JavaScript puro para correr
// dentro de un nodo de código de n8n Cloud (sin librerías externas). El modelo decide relaciones y equivalencias por identificador;
// todas las cifras se copian de los resultados de E3. Si la respuesta cita algo que no existe en la entrada, se rechaza.

const MAX_TEXTO = 400;
const TOLERANCIA = 0.02;

class HomologacionInvalida extends Error {
  constructor(errores) {
    super(errores.slice(0, 6).join('; ') + (errores.length > 6 ? ` (+${errores.length - 6} más)` : ''));
    this.errores = errores;
  }
}

const limpio = (x) => Number(x.toPrecision(15));
const nulo = (v) => v === null || v === undefined;
const verdadero = (v) => !nulo(v) && v !== '' && v !== 0 && v !== false;
const numero = (v) => (nulo(v) ? null : Number(v));
const suma = (lista) => limpio(lista.reduce((a, b) => a + b, 0));
const unicos = (lista) => [...new Set(lista)];

// ---- JSON canónico y huella ----------------------------------------------------------------------------------
function canonico(valor) {
  if (Array.isArray(valor)) return '[' + valor.map(canonico).join(',') + ']';
  if (valor && typeof valor === 'object') {
    return '{' + Object.keys(valor).sort().map((k) => JSON.stringify(k) + ':' + canonico(valor[k])).join(',') + '}';
  }
  return JSON.stringify(valor);
}

function sha256(texto) {
  const K = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be,
    0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc,
    0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
    0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585,
    0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814,
    0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2];
  const h = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
  const datos = Buffer.from(texto, 'utf8');
  const largo = datos.length;
  const total = (((largo + 9 + 63) >> 6) << 6);
  const bloque = Buffer.alloc(total);
  datos.copy(bloque);
  bloque[largo] = 0x80;
  bloque.writeUInt32BE(Math.floor((largo * 8) / 0x100000000), total - 8);
  bloque.writeUInt32BE((largo * 8) >>> 0, total - 4);
  const w = new Array(64);
  const rotar = (x, n) => (x >>> n) | (x << (32 - n));
  for (let o = 0; o < total; o += 64) {
    for (let i = 0; i < 16; i++) w[i] = bloque.readUInt32BE(o + i * 4);
    for (let i = 16; i < 64; i++) {
      const s0 = rotar(w[i - 15], 7) ^ rotar(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rotar(w[i - 2], 17) ^ rotar(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0;
    }
    let [a, b, c, d, e, f, g, hh] = h;
    for (let i = 0; i < 64; i++) {
      const t1 = (hh + (rotar(e, 6) ^ rotar(e, 11) ^ rotar(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i]) >>> 0;
      const t2 = ((rotar(a, 2) ^ rotar(a, 13) ^ rotar(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0;
      hh = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0;
    }
    h[0] = (h[0] + a) >>> 0; h[1] = (h[1] + b) >>> 0; h[2] = (h[2] + c) >>> 0; h[3] = (h[3] + d) >>> 0;
    h[4] = (h[4] + e) >>> 0; h[5] = (h[5] + f) >>> 0; h[6] = (h[6] + g) >>> 0; h[7] = (h[7] + hh) >>> 0;
  }
  return h.map((x) => x.toString(16).padStart(8, '0')).join('');
}

// ---- Entrada del modelo (entrada.py) -------------------------------------------------------------------------
function monedaDelPostor(resultado) {
  if (verdadero(resultado.datos_comerciales.moneda)) return resultado.datos_comerciales.moneda;
  const monedas = unicos((resultado.datos_comerciales_documentos ?? []).map((c) => c.valores.moneda).filter(verdadero));
  return monedas.length === 1 ? monedas[0] : null;
}

function prepare(paquete) {
  const solicitud = paquete.solicitud;
  const nombres = Object.fromEntries(paquete.proveedores.map((p) => [p.id, p.nombre]));
  const postores = [];
  const evidencias = {};
  const finales = [...paquete.finales].sort((a, b) => (a.proveedor_id < b.proveedor_id ? -1 : a.proveedor_id > b.proveedor_id ? 1 : 0));
  for (const final of finales) {
    const r = final.resultado;
    const porId = Object.fromEntries((r.evidencias ?? []).map((e) => [e.id, e]));
    const usadas = new Set();
    const items = [];
    for (const i of r.items ?? []) {
      i.evidencia_ids.forEach((x) => usadas.add(x));
      items.push({ item_id: i.id, documento_id: i.documento_id, referencia_item: i.referencia_item ?? null, descripcion: i.descripcion,
        cantidad: i.cantidad, unidad: i.unidad, precio_unitario: i.precio_unitario, parcial: i.parcial, originales: i.originales,
        evidencia_ids: i.evidencia_ids });
    }
    const especificaciones = [];
    for (const s of r.especificaciones_tecnicas ?? []) {
      s.evidencia_ids.forEach((x) => usadas.add(x));
      especificaciones.push({ documento_id: s.documento_id, referencia_item: s.referencia_item ?? null, campo: s.campo, valor_original: s.valor_original,
        valor_numerico: s.valor_numerico, unidad_original: s.unidad_original, evidencia_ids: s.evidencia_ids });
    }
    const porDocumento = [];
    for (const c of r.datos_comerciales_documentos ?? []) {
      c.evidencia_ids.forEach((x) => usadas.add(x));
      porDocumento.push({ documento_id: c.documento_id, valores: c.valores, originales: c.originales, evidencia_ids: c.evidencia_ids });
    }
    for (const id of [...usadas].sort()) {
      const e = porId[id];
      if (e) {
        evidencias[id] = { id: e.id, proveedor_id: final.proveedor_id, documento_id: e.documento_id, campo: e.campo,
          pagina: e.ubicacion?.pagina ?? null, texto_fuente: e.texto_fuente.slice(0, MAX_TEXTO) };
      }
    }
    const observaciones = (r.observaciones ?? []).map((o) => ({ tipo: o.tipo, severidad: o.severidad, requiere_aclaracion: o.requiere_aclaracion,
      estado: o.estado, descripcion: o.descripcion }));
    postores.push({
      proveedor_id: final.proveedor_id, nombre: nombres[final.proveedor_id] ?? final.proveedor_id, version_id: final.version_id,
      numero_version: final.numero_version, moneda: monedaDelPostor(r),
      documentos: (r.documentos ?? []).map((d) => ({ documento_id: d.documento_id, nombre: d.nombre_original })),
      comercial: r.datos_comerciales, comercial_por_documento: porDocumento, items, especificaciones, observaciones, decisiones: r.decisiones ?? [],
    });
  }
  const conFinal = new Set(postores.map((p) => p.proveedor_id));
  const sinFinal = paquete.proveedores.filter((p) => !conFinal.has(p.id) && p.estado !== 'descartado').map((p) => ({ proveedor_id: p.id, nombre: p.nombre }));
  const partidas = paquete.partidas;
  const base = { tipo: partidas.length ? 'itemizado' : 'provisional',
    partidas: partidas.map((p) => ({ codigo: p.codigo, descripcion: p.descripcion, unidad: p.unidad, metrado: p.metrado })) };
  // Moneda de comparación: la que comparten las ofertas que identifican su moneda; si hay varias, la de la solicitud.
  const monedas = unicos(postores.map((p) => p.moneda).filter(verdadero));
  const monedaComun = monedas.length === 1;
  const monedaComparacion = monedaComun ? monedas[0] : solicitud.moneda;
  const versionIds = postores.map((p) => p.version_id).sort();
  const huella = sha256(canonico({ versiones: versionIds, base: base.partidas, moneda: solicitud.moneda }));
  return {
    huella, version_ids: versionIds,
    solicitud: { id: solicitud.id, codigo: solicitud.codigo, nombre: solicitud.nombre, moneda: solicitud.moneda, moneda_comparacion: monedaComparacion,
      fecha_evaluacion: paquete.fecha_evaluacion, proyecto: solicitud.proyecto },
    moneda_comparacion_origen: monedaComun ? 'moneda común de las ofertas' : 'moneda de la solicitud',
    base, postores, evidencias: Object.values(evidencias), sin_final: sinFinal,
  };
}

// ---- Petición a Claude y lectura de su respuesta (contrato.py) ------------------------------------------------
function requestClaude(preparado, modelo, systemPrompt) {
  const entrada = { solicitud: preparado.solicitud, base: preparado.base, postores: preparado.postores, evidencias: preparado.evidencias,
    sin_final: preparado.sin_final };
  return { model: modelo, max_tokens: 16000, system: systemPrompt, messages: [{ role: 'user', content: JSON.stringify(entrada) }],
    output_config: { effort: 'medium' } };
}

// Valida un valor contra el subconjunto de JSON Schema que usa SALIDA (type, enum, properties, required, additionalProperties, items).
function validarEsquema(esquema, valor, ruta = '$') {
  const tipos = Array.isArray(esquema.type) ? esquema.type : esquema.type ? [esquema.type] : null;
  const tipoDe = (v) => (v === null ? 'null' : Array.isArray(v) ? 'array' : typeof v === 'number' ? 'number' : typeof v);
  if (tipos && !tipos.includes(tipoDe(valor))) throw new Error(`${ruta}: se esperaba ${tipos.join(' o ')}`);
  if (esquema.enum && !esquema.enum.includes(valor)) throw new Error(`${ruta}: ${JSON.stringify(valor)} no es uno de ${esquema.enum.join(', ')}`);
  if (esquema.properties && valor && typeof valor === 'object' && !Array.isArray(valor)) {
    for (const k of esquema.required ?? []) if (!(k in valor)) throw new Error(`${ruta}: falta «${k}»`);
    if (esquema.additionalProperties === false) {
      for (const k of Object.keys(valor)) if (!(k in esquema.properties)) throw new Error(`${ruta}: «${k}» no está permitido`);
    }
    for (const [k, sub] of Object.entries(esquema.properties)) if (k in valor) validarEsquema(sub, valor[k], `${ruta}.${k}`);
  }
  if (esquema.items && Array.isArray(valor)) valor.forEach((x, i) => validarEsquema(esquema.items, x, `${ruta}[${i}]`));
}

// Primer objeto JSON de la respuesta: tolera bloques de código y texto antes o después.
function parseTexto(texto, esquema) {
  const limpioTexto = texto.trim().replace(/^```(?:json)?\s*/i, '');
  const inicio = limpioTexto.indexOf('{');
  if (inicio < 0) throw new Error('El modelo no devolvió un objeto JSON.');
  let profundidad = 0, enCadena = false, escape = false, fin = -1;
  for (let i = inicio; i < limpioTexto.length; i++) {
    const c = limpioTexto[i];
    if (enCadena) { if (escape) escape = false; else if (c === '\\') escape = true; else if (c === '"') enCadena = false; continue; }
    if (c === '"') enCadena = true;
    else if (c === '{') profundidad++;
    else if (c === '}' && --profundidad === 0) { fin = i; break; }
  }
  if (fin < 0) throw new Error('El modelo no devolvió un objeto JSON válido: JSON incompleto.');
  let datos;
  try { datos = JSON.parse(limpioTexto.slice(inicio, fin + 1)); } catch (e) { throw new Error(`El modelo no devolvió un objeto JSON válido: ${e.message}.`); }
  validarEsquema(esquema, datos);
  return datos;
}

// ---- Construcción de homologacion.json (construir.py) ---------------------------------------------------------
function condicion(postor, campo) {
  const valor = postor.comercial[campo];
  if (!nulo(valor)) return valor;
  const distintos = unicos(postor.comercial_por_documento.map((c) => c.valores[campo]).filter(verdadero));
  return distintos.length ? distintos.join(' / ') : null;
}

function build(preparado, salida, modelo, esquema, ahora = null) {
  try { validarEsquema(esquema, salida); } catch (e) { throw new HomologacionInvalida([`La respuesta no cumple el formato: ${e.message.slice(0, 160)}`]); }
  const errores = [];
  const postores = Object.fromEntries(preparado.postores.map((p) => [p.proveedor_id, p]));
  const items = {};
  for (const p of preparado.postores) for (const i of p.items) items[i.item_id] = [p.proveedor_id, i];
  const evidencias = new Set(preparado.evidencias.map((e) => e.id));
  const base = preparado.base;
  const pendientes = salida.pendientes.map((p) => ({ ...p, origen: 'modelo' }));
  const sinFinalIds = new Set(preparado.sin_final.map((p) => p.proveedor_id));
  const corto = (id) => String(id).slice(0, 8);

  const comprobarEvidencias = (ids, donde) => {
    for (const id of ids) if (!evidencias.has(id)) errores.push(`${donde}: la evidencia ${corto(id)} no existe en la entrada`);
  };

  // Base: con itemizado las partidas son exactamente las de la solicitud.
  if (base.tipo === 'itemizado') {
    const esperadas = Object.fromEntries(base.partidas.map((p) => [p.codigo, p]));
    const recibidas = Object.fromEntries(salida.partidas.map((p) => [p.codigo, p]));
    const clavesE = Object.keys(esperadas), clavesR = Object.keys(recibidas);
    if (clavesR.length !== salida.partidas.length || clavesR.length !== clavesE.length || !clavesE.every((k) => k in recibidas)) {
      errores.push('Las partidas devueltas no coinciden con el itemizado de la solicitud');
    } else {
      for (const [codigo, esperada] of Object.entries(esperadas)) {
        if (recibidas[codigo].unidad !== esperada.unidad || numero(recibidas[codigo].metrado) !== numero(esperada.metrado)) {
          errores.push(`La partida ${codigo} cambió la unidad o el metrado del itemizado`);
        }
      }
    }
  } else if (salida.base.tipo !== 'provisional') {
    errores.push('Sin itemizado cargado la base solo puede ser provisional');
  }

  // Cada ítem va en una sola partida (salvo precio global) y pertenece al proveedor que la ofrece.
  const ubicaciones = {};
  for (const partida of salida.partidas) {
    const etiqueta = verdadero(partida.codigo) ? partida.codigo : partida.descripcion.slice(0, 40);
    const vistos = new Set();
    for (const oferta of partida.ofertas) {
      const proveedor = oferta.proveedor_id;
      if (!(proveedor in postores)) { errores.push(`Partida ${etiqueta}: el proveedor ${corto(proveedor)} no tiene versión final`); continue; }
      if (vistos.has(proveedor)) errores.push(`Partida ${etiqueta}: el proveedor ${corto(proveedor)} aparece dos veces`);
      vistos.add(proveedor);
      comprobarEvidencias(oferta.evidencia_ids, `Partida ${etiqueta}`);
      if (oferta.estado === 'no_cotizado' && oferta.item_ids.length) errores.push(`Partida ${etiqueta}: una oferta «no_cotizado» no puede traer ítems`);
      if ((oferta.estado === 'cotizado' || oferta.estado === 'global') && !oferta.item_ids.length) {
        errores.push(`Partida ${etiqueta}: una oferta «${oferta.estado}» necesita ítems`);
      }
      if (oferta.equivalencia === 'equivalente' && !oferta.evidencia_ids.length) {
        errores.push(`Partida ${etiqueta}: la equivalencia de ${corto(proveedor)} no cita evidencia`);
      }
      for (const itemId of oferta.item_ids) {
        if (!(itemId in items) || items[itemId][0] !== proveedor) errores.push(`Partida ${etiqueta}: el ítem ${corto(itemId)} no pertenece a ${corto(proveedor)}`);
        else (ubicaciones[itemId] ??= []).push(oferta.estado);
      }
    }
    if (base.tipo === 'provisional' && !nulo(partida.metrado)) {
      const cantidades = new Set();
      for (const o of partida.ofertas) for (const i of o.item_ids) if (i in items) cantidades.add(numero(items[i][1].cantidad));
      for (const o of partida.ofertas) {
        const s = o.item_ids.filter((i) => i in items).map((i) => numero(items[i][1].cantidad));
        if (s.length && s.every((x) => x !== null)) cantidades.add(suma(s));
      }
      if (!cantidades.has(numero(partida.metrado))) errores.push(`Partida ${etiqueta}: el metrado no coincide con ninguna cantidad cotizada`);
    }
  }
  for (const [itemId, estados] of Object.entries(ubicaciones)) {
    if (estados.length > 1 && estados.some((e) => e !== 'global')) errores.push(`El ítem ${corto(itemId)} está en varias partidas sin ser un precio global`);
  }
  const adicionales = [];
  for (const extra of salida.adicionales) {
    if (!(extra.item_id in items) || items[extra.item_id][0] !== extra.proveedor_id) {
      errores.push(`Adicional: el ítem ${corto(extra.item_id)} no pertenece a ${corto(extra.proveedor_id)}`);
    } else if (extra.item_id in ubicaciones) errores.push(`El ítem ${corto(extra.item_id)} está a la vez en una partida y en adicionales`);
    else adicionales.push(extra);
  }
  for (const diferencia of salida.diferencias) {
    comprobarEvidencias(diferencia.evidencia_ids, 'Diferencia');
    for (const proveedor of diferencia.proveedor_ids) if (!(proveedor in postores)) errores.push(`Diferencia: el proveedor ${corto(proveedor)} no tiene versión final`);
  }
  for (const pendiente of pendientes) {
    comprobarEvidencias(pendiente.evidencia_ids, 'Pendiente');
    if (pendiente.proveedor_id !== null && !(pendiente.proveedor_id in postores) && !sinFinalIds.has(pendiente.proveedor_id)) {
      errores.push(`Pendiente: el proveedor ${corto(pendiente.proveedor_id)} no es de esta solicitud`);
    }
  }
  if (errores.length) throw new HomologacionInvalida(errores);

  // Lo que el modelo no relacionó no se pierde: queda como adicional y pendiente.
  const colocados = new Set([...Object.keys(ubicaciones), ...adicionales.map((a) => a.item_id)]);
  for (const [itemId, [proveedor, item]] of Object.entries(items)) {
    if (!colocados.has(itemId)) {
      adicionales.push({ proveedor_id: proveedor, item_id: itemId, motivo: 'El modelo no lo relacionó con ninguna partida.' });
      pendientes.push({ proveedor_id: proveedor, partida_codigo: null, partida_descripcion: item.descripcion, origen: 'sistema',
        motivo: 'Un ítem cotizado no quedó relacionado con la base.', bloquea_comparacion: true,
        decision_requerida: 'Relacionar el ítem con una partida o aceptarlo como adicional.', evidencia_ids: item.evidencia_ids });
    }
  }

  // La moneda de comparación se resolvió al preparar la entrada y es la misma que vio el modelo.
  const monedaComparacion = preparado.solicitud.moneda_comparacion;
  const sistema = (proveedor, motivo, decision, bloquea) => pendientes.push({ proveedor_id: proveedor, partida_codigo: null, partida_descripcion: null,
    origen: 'sistema', motivo, bloquea_comparacion: bloquea, decision_requerida: decision, evidencia_ids: [] });

  if (base.tipo === 'provisional') {
    sistema(null, 'El itemizado de la solicitud no está cargado: la base de comparación es provisional.', 'Cargar el itemizado o aprobar la base provisional.', true);
  }
  for (const sin of preparado.sin_final) {
    if (pendientes.some((p) => p.proveedor_id === sin.proveedor_id)) continue;
    sistema(sin.proveedor_id, `${sin.nombre} no tiene una cotización aceptada como final.`, 'Esperar o aceptar su cotización; no entra en la comparación.', false);
  }

  const salidaPostores = [];
  for (const p of Object.values(postores)) {
    const comparable = p.moneda === monedaComparacion;
    if (!verdadero(p.moneda)) sistema(p.proveedor_id, `No se identificó la moneda de la oferta de ${p.nombre}.`, 'Confirmar la moneda con el proveedor.', true);
    else if (!comparable) {
      sistema(p.proveedor_id, `La oferta de ${p.nombre} está en ${p.moneda} y la comparación en ${monedaComparacion}.`, 'Autorizar un tipo de cambio con fecha y fuente.', true);
    }
    if (nulo(p.comercial.impuestos) && !p.comercial_por_documento.some((c) => !nulo(c.valores.impuestos))) {
      sistema(p.proveedor_id, `No se conoce el IGV de la oferta de ${p.nombre}; los precios se comparan tal como se cotizaron.`, 'Confirmar si los precios incluyen IGV.', false);
    }
    if (nulo(p.comercial.vigencia_oferta) && !p.comercial_por_documento.some((c) => verdadero(c.valores.vigencia_oferta))) {
      sistema(p.proveedor_id, `La oferta de ${p.nombre} no indica su vigencia.`, 'Consultar la vigencia con el proveedor.', false);
    }
    for (const c of p.comercial_por_documento) {
      const partes = p.items.filter((i) => i.documento_id === c.documento_id).map((i) => numero(i.parcial));
      const subtotal = numero(c.valores.subtotal);
      if (subtotal !== null && partes.length && partes.every((x) => x !== null) && Math.abs(suma(partes) - subtotal) > TOLERANCIA) {
        sistema(p.proveedor_id, `En ${p.nombre}, la suma de parciales (${suma(partes)}) no coincide con el subtotal (${subtotal}).`, 'Revisar descuentos, cargos o ítems faltantes.', false);
      }
    }
    const abiertas = p.observaciones.filter((o) => o.requiere_aclaracion && ['pendiente', 'aclaracion_solicitada'].includes(o.estado));
    if (abiertas.length) {
      sistema(p.proveedor_id, `${p.nombre}: el especialista aceptó la versión con ${abiertas.length} observaciones de lectura sin resolver.`, 'Revisarlas si afectan la comparación.', false);
    }
    const tres = ['subtotal', 'impuestos', 'total'];
    salidaPostores.push({
      proveedor_id: p.proveedor_id, nombre: p.nombre, version_id: p.version_id, numero_version: p.numero_version, moneda: p.moneda,
      comparable_en_moneda_de_comparacion: comparable,
      totales_originales: Object.fromEntries(tres.map((k) => [k, p.comercial[k] ?? null])),
      totales_por_documento: p.comercial_por_documento.map((c) => ({ documento_id: c.documento_id,
        ...Object.fromEntries(tres.map((k) => [k, c.valores[k] ?? null])), originales: Object.fromEntries(tres.map((k) => [k, c.originales[k] ?? null])) })),
      condiciones: Object.fromEntries(['plazo_entrega', 'condiciones_pago', 'vigencia_oferta'].map((k) => [k, condicion(p, k)])),
      estado_vigencia: 'no_determinada', archivos: p.documentos,
    });
  }

  const comparables = Object.fromEntries(Object.values(postores).map((p) => [p.proveedor_id, p.moneda === monedaComparacion]));
  const detalleItem = (proveedor, item) => {
    const cambio = comparables[proveedor] ? { cantidad: item.cantidad, precio_unitario: item.precio_unitario, parcial: item.parcial }
      : { cantidad: null, precio_unitario: null, parcial: null };
    return {
      item_id: item.item_id, documento_id: item.documento_id,
      original: { descripcion: item.descripcion, unidad: item.unidad, cantidad: item.cantidad, precio_unitario: item.precio_unitario, parcial: item.parcial,
        moneda: postores[proveedor].moneda, textos: item.originales },
      comparable: { ...cambio, moneda: comparables[proveedor] ? monedaComparacion : null, operacion: comparables[proveedor] ? 'sin_cambio' : null,
        criterio: comparables[proveedor] ? 'Misma moneda; sin conversión ni ajuste de IGV.' : 'Sin tipo de cambio autorizado.' },
      evidencia_ids: item.evidencia_ids,
    };
  };

  const salidaPartidas = [];
  for (const partida of salida.partidas) {
    const ofertas = [];
    for (const oferta of partida.ofertas) {
      const proveedor = oferta.proveedor_id;
      ofertas.push({ proveedor_id: proveedor, estado: oferta.estado, equivalencia: oferta.equivalencia, nota: oferta.nota, evidencia_ids: oferta.evidencia_ids,
        items: oferta.item_ids.map((i) => detalleItem(proveedor, items[i][1])) });
      if (oferta.equivalencia !== 'equivalente' && ['cotizado', 'global', 'incluido_con_evidencia'].includes(oferta.estado)) {
        const cubierto = pendientes.some((p) => p.proveedor_id === proveedor && ((p.partida_codigo === partida.codigo && partida.codigo !== null)
          || p.partida_descripcion === partida.descripcion));
        if (!cubierto) {
          pendientes.push({ proveedor_id: proveedor, partida_codigo: partida.codigo, partida_descripcion: partida.descripcion, origen: 'sistema',
            motivo: oferta.equivalencia === 'pendiente' ? 'La equivalencia técnica no está resuelta.' : 'La oferta es técnicamente distinta de la partida.',
            bloquea_comparacion: true, decision_requerida: 'Decidir si la oferta se acepta como equivalente.', evidencia_ids: oferta.evidencia_ids });
        }
      }
    }
    salidaPartidas.push({ codigo: partida.codigo, descripcion: partida.descripcion, unidad: partida.unidad, metrado: partida.metrado, ofertas });
  }

  const decisiones = Object.values(postores).flatMap((p) => p.decisiones.map((d) => ({ proveedor_id: p.proveedor_id, version_id: p.version_id,
    accion: d.accion, motivo: d.motivo ?? null, fecha: d.created_at ?? null, usuario_id: d.usuario_id ?? null })));
  const bloqueantes = pendientes.filter((p) => p.bloquea_comparacion).length;
  const solicitud = preparado.solicitud;
  return {
    solicitud_id: solicitud.id,
    proyecto: { codigo: solicitud.proyecto.codigo, obra: solicitud.proyecto.nombre, solicitud: solicitud.codigo, fecha_evaluacion: solicitud.fecha_evaluacion, revision: null },
    especialidad: salida.especialidad,
    estado_revision: bloqueantes ? 'requiere_revision' : 'listo_para_cuadro',
    base: { tipo: base.tipo, identificador: base.tipo === 'itemizado' ? solicitud.id : null, version: null,
      origen_proveedor_id: salida.base.origen_proveedor_id, nota: salida.base.nota },
    moneda_comparacion: monedaComparacion, tipo_cambio: null,
    postores: salidaPostores, proveedores_sin_final: preparado.sin_final, partidas: salidaPartidas, adicionales,
    trazabilidad: { entrada: 'Resultados de E3 de las versiones aceptadas como final; no se leyeron PDF ni Excel.', version_ids: preparado.version_ids,
      huella: preparado.huella, operaciones: ['Los importes se copian de E3 sin cambio; no hay conversión de moneda ni ajuste de IGV.'],
      moneda_comparacion_origen: preparado.moneda_comparacion_origen, evidencias: preparado.evidencias },
    pendientes, diferencias: salida.diferencias, escenarios: [], decisiones,
    generado: { modelo, fecha: ahora ?? new Date().toISOString().replace('Z', '+00:00') },
  };
}

if (typeof module !== 'undefined') {
  module.exports = { prepare, requestClaude, parseTexto, validarEsquema, build, canonico, sha256, HomologacionInvalida };
}
