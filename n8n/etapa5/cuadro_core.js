// E5 en n8n: decide qué celdas de la plantilla se llenan con la homologación de E4 y las escribe en el XML de la hoja.
// Es el equivalente exacto de app/cuadro/llenar.py (plan, _celda y los reemplazos de llenar), en JavaScript puro para
// poder correr dentro de un nodo de código de n8n Cloud, que no admite librerías externas.
// No usa modelo. Los números vienen de la homologación, que a su vez los copió de E3.

const HOJA = 'xl/worksheets/sheet1.xml';
// [primera columna del bloque (nombre y texto), cantidad, P.U. US$, P.U. S/, parcial]
const BLOQUES = [['H', 'H', 'I', 'J', 'K'], ['L', 'L', 'M', 'N', 'O'], ['P', 'P', 'Q', 'R', 'S'], ['T', 'T', 'U', 'V', 'W'],
  ['X', 'X', 'Y', 'Z', 'AA'], ['AB', 'AB', 'AC', 'AD', 'AE'], ['AF', 'AF', 'AG', 'AH', 'AI']];
const FILA_PLAZO = 30, FILA_PAGO = 33, FILA_CONSIDERACIONES = 36;
const TOLERANCIA = 0.01;

class CuadroNoGenerable extends Error {}

// Los importes decimales se normalizan a 15 cifras significativas para que 36937.55 * 2 no deje ruido de coma flotante.
const limpio = (x) => Number(x.toPrecision(15));
const verdadero = (v) => v !== null && v !== undefined && v !== '' && v !== 0 && v !== false;

function dec(valor) {
  if (valor === null || valor === undefined || typeof valor === 'boolean') return null;
  if (typeof valor === 'number') return Number.isFinite(valor) ? valor : null;
  const texto = String(valor).trim();
  if (!/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(texto)) return null;
  return Number(texto);
}

const numero = (valor) => limpio(valor);
const suma = (lista) => limpio(lista.reduce((a, b) => a + b, 0));

function plan(homologacion, tipoCambio) {
  const partidas = homologacion.partidas;
  if (!partidas || !partidas.length) throw new CuadroNoGenerable('La homologación no tiene partidas que comparar.');
  const postores = homologacion.postores;
  if (!postores || !postores.length) throw new CuadroNoGenerable('No hay ofertas finales para comparar.');
  let tc = null;
  if (verdadero(tipoCambio)) {
    tc = dec(tipoCambio.valor);
    if (tc === null || tc <= 0) throw new CuadroNoGenerable('El tipo de cambio no es un número positivo.');
  }
  const porTipos = partidas.length > 1;
  const avisos = [], informativos = [], comprobaciones = [];
  const celdas = {};
  const metrado = !porTipos ? dec(partidas[0].metrado) : null;
  if (porTipos) {
    celdas.I3 = homologacion.especialidad.nombre; // el título dice COMPARATIVO - <especialidad>; B13 conserva el texto de la plantilla
  } else {
    celdas.I3 = partidas[0].descripcion;
    celdas.B13 = partidas[0].descripcion;
    celdas.C13 = partidas[0].unidad;
    celdas.D13 = metrado !== null ? numero(metrado) : null;
  }
  celdas.E13 = null; // el presupuesto meta no viene de E3
  if (porTipos) celdas.D13 = null;
  celdas.F5 = tc ? numero(tc) : 0;

  const bloques = []; // [postor, etiquetaTipo, numeroTipo, partida, items]
  const ordenados = [...postores].sort((a, b) => (a.nombre < b.nombre ? -1 : a.nombre > b.nombre ? 1 : 0));
  for (const postor of ordenados) {
    const cotizadas = [];
    partidas.forEach((partida, i) => {
      const oferta = partida.ofertas.find((o) => o.proveedor_id === postor.proveedor_id);
      if (oferta && ['cotizado', 'global', 'incluido_con_evidencia'].includes(oferta.estado) && oferta.items.length) {
        cotizadas.push([i + 1, partida, oferta.items]);
      }
    });
    if (!cotizadas.length) informativos.push(`${postor.nombre}: no cotiza ninguna partida; no ocupa un bloque.`);
    for (const [numeroTipo, partida, items] of cotizadas) {
      bloques.push([postor, cotizadas.length > 1 ? numeroTipo : null, numeroTipo, partida, items]);
    }
  }
  if (!bloques.length) throw new CuadroNoGenerable('Ningún proveedor cotizó las partidas.');
  if (bloques.length > BLOQUES.length) {
    throw new CuadroNoGenerable(`La plantilla tiene ${BLOQUES.length} bloques de proveedor y se necesitan ${bloques.length} (un bloque por proveedor y tipo).`);
  }

  let usaDolares = false;
  bloques.forEach(([postor, etiquetaTipo, numeroTipo, partida, items], indice) => {
    const [n, cant, usd, pen] = BLOQUES[indice];
    celdas[`${n}6`] = postor.nombre + (etiquetaTipo ? ` (TIPO ${etiquetaTipo})` : '');
    const moneda = postor.moneda;
    const parciales = items.map((i) => dec(i.original.parcial));
    const cantidades = items.map((i) => dec(i.original.cantidad));
    let cantidad = cantidades.every((c) => c !== null) && suma(cantidades) > 0 ? suma(cantidades) : null;
    if (cantidad === null) {
      cantidad = dec(partida.metrado) || 1;
      avisos.push(`${postor.nombre}: E3 no trae la cantidad; se usó ${numero(cantidad)} (el metrado de la partida o 1).`);
    }
    const unitarioItem = items.length === 1 ? dec(items[0].original.precio_unitario) : null;
    if (moneda !== 'PEN' && moneda !== 'USD') {
      avisos.push(`${postor.nombre}: moneda ${moneda || 'no identificada'}; la plantilla solo maneja PEN y USD, el bloque queda sin precios.`);
      comprobaciones.push({ proveedor: postor.nombre, tipo: numeroTipo, cuadra: false });
      celdas[`${cant}13`] = numero(cantidad); celdas[`${usd}13`] = 0; celdas[`${pen}13`] = 0;
      if (porTipos) celdas[`${n}${FILA_CONSIDERACIONES}`] = `Tipo ${numeroTipo}: ${partida.descripcion}`;
      return;
    }
    let total, unitario;
    if (parciales.every((p) => p !== null)) {
      total = suma(parciales);
      unitario = limpio(total / cantidad);
    } else if (unitarioItem !== null) {
      unitario = unitarioItem;
      total = limpio(unitario * cantidad);
      avisos.push(`${postor.nombre}: el ítem no trae parcial; se usó precio unitario por cantidad.`);
    } else {
      avisos.push(`${postor.nombre}: faltan importes en la lectura de E3; el bloque queda sin precios (no se inventan).`);
      comprobaciones.push({ proveedor: postor.nombre, tipo: numeroTipo, cuadra: false });
      celdas[`${cant}13`] = numero(cantidad); celdas[`${usd}13`] = 0; celdas[`${pen}13`] = 0;
      if (porTipos) celdas[`${n}${FILA_CONSIDERACIONES}`] = `Tipo ${numeroTipo}: ${partida.descripcion}`;
      return;
    }
    celdas[`${cant}13`] = numero(cantidad);
    if (moneda === 'USD') {
      usaDolares = true;
      celdas[`${usd}13`] = numero(unitario);
      if (!tc) avisos.push(`${postor.nombre} cotiza en US$ y falta el tipo de cambio: las columnas en S/ quedan sin valor.`);
    } else {
      celdas[`${usd}13`] = 0; celdas[`${pen}13`] = numero(unitario);
    }
    if (items.length > 1) {
      avisos.push(`${postor.nombre}: ${items.length} ítems agrupados en la partida; el precio unitario es la suma de parciales entre la cantidad.`);
    }
    comprobaciones.push({ proveedor: postor.nombre, tipo: numeroTipo, cantidad_por_unitario: limpio(cantidad * unitario),
      suma_parciales: limpio(total), cuadra: Math.abs(cantidad * unitario - total) <= TOLERANCIA });
    const condiciones = postor.condiciones;
    if (verdadero(condiciones.plazo_entrega)) celdas[`${n}${FILA_PLAZO}`] = String(condiciones.plazo_entrega);
    if (verdadero(condiciones.condiciones_pago)) celdas[`${n}${FILA_PAGO}`] = String(condiciones.condiciones_pago);
    const texto = [];
    if (porTipos) texto.push(`Tipo ${numeroTipo}: ${partida.descripcion}`);
    if (verdadero(condiciones.vigencia_oferta)) texto.push(`Vigencia de la oferta: ${condiciones.vigencia_oferta}`);
    if (texto.length) celdas[`${n}${FILA_CONSIDERACIONES}`] = texto.join('\n');
  });
  if (usaDolares && !tc) comprobaciones.push({ proveedor: null, tipo_cambio_presente: false, cuadra: false });
  // Un pendiente que solo pide autorizar el tipo de cambio queda resuelto si el especialista lo indicó al generar.
  const bloqueantes = homologacion.pendientes.filter((p) => p.bloquea_comparacion && !(tc && p.decision_requerida.includes('tipo de cambio')));
  if (bloqueantes.length) avisos.push(`La homologación tiene ${bloqueantes.length} pendientes que bloquean la comparación.`);
  const validado = comprobaciones.every((c) => c.cuadra) && !avisos.length && !bloqueantes.length;
  return { celdas, avisos, informativos, bloques: bloques.length, comprobaciones, validado,
    pendientes_bloqueantes: bloqueantes.length, tipo_cambio: tipoCambio ?? null, moneda_comparacion: homologacion.moneda_comparacion };
}

const escapar = (t) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function celda(xml, ref, valor) {
  const patron = new RegExp(`<c r="${ref}"((?:\\s[^>]*?)?)(/>|>[\\s\\S]*?</c>)`);
  const m = patron.exec(xml);
  if (!m) throw new CuadroNoGenerable(`La plantilla no tiene la celda ${ref}; no es la plantilla esperada.`);
  const estilo = /\ss="(\d+)"/.exec(m[1]);
  const s = estilo ? ` s="${estilo[1]}"` : '';
  let nuevo;
  if (valor === null || valor === undefined) nuevo = `<c r="${ref}"${s}/>`;
  else if (typeof valor === 'string') nuevo = `<c r="${ref}"${s} t="inlineStr"><is><t xml:space="preserve">${escapar(valor)}</t></is></c>`;
  else nuevo = `<c r="${ref}"${s}><v>${valor}</v></c>`;
  return xml.slice(0, m.index) + nuevo + xml.slice(m.index + m[0].length);
}

// Escribe las celdas en la hoja, quita los valores calculados viejos (Excel recalcula al abrir).
function llenarHoja(xml, cambios) {
  let texto = xml;
  for (const [ref, valor] of Object.entries(cambios)) texto = celda(texto, ref, valor);
  texto = texto.replace(/(<f>[^<]*<\/f>)<v>[^<]*<\/v>/g, '$1');
  return texto.replace(/(<c r="[A-Z]+\d+"[^>]*?) t="str"(>\s*<f>)/g, '$1$2');
}

const llenarLibro = (xml) => xml.replace(/<calcPr[^>]*\/>/, '<calcPr calcId="191028" fullCalcOnLoad="1"/>');
const llenarTipos = (xml) => xml.replace(/<Override[^>]*calcChain[^>]*\/>/g, '');
const llenarRelaciones = (xml) => xml.replace(/<Relationship [^>]*calcChain[^>]*\/>/g, '');

// Rutas de los archivos de un zip, en el orden de su directorio central. Solo lee nombres (no descomprime nada).
// El nodo «Descomprimir» de n8n entrega cada archivo sin su carpeta; con esta lista se le devuelve su ruta completa.
function nombresDelZip(buffer) {
  const v = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
  let fin = -1;
  for (let i = buffer.length - 22; i >= Math.max(0, buffer.length - 65557); i--) {
    if (v.getUint32(i, true) === 0x06054b50) { fin = i; break; }
  }
  if (fin < 0) throw new CuadroNoGenerable('El archivo no es un .xlsx válido.');
  const cantidad = v.getUint16(fin + 10, true);
  let posicion = v.getUint32(fin + 16, true);
  const nombres = [];
  for (let i = 0; i < cantidad; i++) {
    if (v.getUint32(posicion, true) !== 0x02014b50) throw new CuadroNoGenerable('El directorio del .xlsx está dañado.');
    const largoNombre = v.getUint16(posicion + 28, true);
    const largoExtra = v.getUint16(posicion + 30, true);
    const largoComentario = v.getUint16(posicion + 32, true);
    const nombre = buffer.toString('utf8', posicion + 46, posicion + 46 + largoNombre);
    if (!nombre.endsWith('/')) nombres.push(nombre); // las carpetas no llegan como archivo
    posicion += 46 + largoNombre + largoExtra + largoComentario;
  }
  return nombres;
}

if (typeof module !== 'undefined') {
  module.exports = { plan, nombresDelZip, celda, llenarHoja, llenarLibro, llenarTipos, llenarRelaciones, CuadroNoGenerable, HOJA };
}
