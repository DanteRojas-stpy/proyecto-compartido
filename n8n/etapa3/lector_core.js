// E3 en n8n: lector documental sin servicio aparte. Equivale a app/etapa3 (documents.py, rag.py y contract.py) en JavaScript puro,
// para correr dentro de nodos de código de n8n Cloud (sin librerías externas).
//  - huellas y UUID estables (SHA-256, SHA-1, uuid5) y JSON al estilo de Python, para que los identificadores sean los mismos;
//  - fragmentos de texto, lectura de Excel (.xlsx) y CSV;
//  - petición a Claude, lectura de su respuesta y validación independiente (combine): toda cita debe existir literalmente en el
//    fragmento, y los importes deben coincidir con su texto original.
// Cambio respecto a la versión con servicio: sin OCR ni embeddings. Los fragmentos se envían todos, por tandas, como ya ocurría
// con los documentos sin búsqueda semántica.

class DocumentoInvalido extends Error {} // archivo ilegible o fuera de límites: no se reintenta

const limpio = (x) => Number(x.toPrecision(15));
const nulo = (v) => v === null || v === undefined;
const verdadero = (v) => !nulo(v) && v !== '' && v !== 0 && v !== false;

// ---- Huellas -------------------------------------------------------------------------------------------------
function sha1(buffer) {
  const datos = Buffer.from(buffer);
  const largo = datos.length;
  const total = (((largo + 9 + 63) >> 6) << 6);
  const bloque = Buffer.alloc(total);
  datos.copy(bloque);
  bloque[largo] = 0x80;
  bloque.writeUInt32BE(Math.floor((largo * 8) / 0x100000000), total - 8);
  bloque.writeUInt32BE((largo * 8) >>> 0, total - 4);
  let h0 = 0x67452301, h1 = 0xefcdab89, h2 = 0x98badcfe, h3 = 0x10325476, h4 = 0xc3d2e1f0;
  const w = new Array(80);
  const rotar = (x, n) => (x << n) | (x >>> (32 - n));
  for (let o = 0; o < total; o += 64) {
    for (let i = 0; i < 16; i++) w[i] = bloque.readUInt32BE(o + i * 4);
    for (let i = 16; i < 80; i++) w[i] = rotar(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1) >>> 0;
    let a = h0, b = h1, c = h2, d = h3, e = h4;
    for (let i = 0; i < 80; i++) {
      let f, k;
      if (i < 20) { f = (b & c) | (~b & d); k = 0x5a827999; }
      else if (i < 40) { f = b ^ c ^ d; k = 0x6ed9eba1; }
      else if (i < 60) { f = (b & c) | (b & d) | (c & d); k = 0x8f1bbcdc; }
      else { f = b ^ c ^ d; k = 0xca62c1d6; }
      const t = (rotar(a, 5) + f + e + k + w[i]) >>> 0;
      e = d; d = c; c = rotar(b, 30) >>> 0; b = a; a = t;
    }
    h0 = (h0 + a) >>> 0; h1 = (h1 + b) >>> 0; h2 = (h2 + c) >>> 0; h3 = (h3 + d) >>> 0; h4 = (h4 + e) >>> 0;
  }
  const salida = Buffer.alloc(20);
  [h0, h1, h2, h3, h4].forEach((h, i) => salida.writeUInt32BE(h, i * 4));
  return salida;
}

function sha256(buffer) {
  const K = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be,
    0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc,
    0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
    0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585,
    0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814,
    0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2];
  const h = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
  const datos = Buffer.from(buffer);
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

const NAMESPACE = Buffer.from('52bf8df4e06244c88e3c5be90c5c3d37', 'hex');
function stableId(valor) {
  const h = sha1(Buffer.concat([NAMESPACE, Buffer.from(valor, 'utf8')]));
  h[6] = (h[6] & 0x0f) | 0x50;
  h[8] = (h[8] & 0x3f) | 0x80;
  const x = h.subarray(0, 16).toString('hex');
  return `${x.slice(0, 8)}-${x.slice(8, 12)}-${x.slice(12, 16)}-${x.slice(16, 20)}-${x.slice(20)}`;
}

// json.dumps de Python: separadores «, » y «: », claves ordenadas si se pide y caracteres no ASCII escapados salvo ensure_ascii=False.
function pyJson(valor, { ordenar = false, ascii = true } = {}) {
  const cadena = (s) => {
    const t = JSON.stringify(s);
    return ascii ? t.replace(/[\u0080-￿]/g, (c) => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0')) : t;
  };
  const ir = (v) => {
    if (v === null || v === undefined) return 'null';
    if (Array.isArray(v)) return '[' + v.map(ir).join(', ') + ']';
    if (typeof v === 'object') {
      const claves = ordenar ? Object.keys(v).sort() : Object.keys(v);
      return '{' + claves.map((k) => cadena(k) + ': ' + ir(v[k])).join(', ') + '}';
    }
    if (typeof v === 'string') return cadena(v);
    return String(v);
  };
  return ir(valor);
}
const pyStr = (v) => (v === null || v === undefined ? 'None' : v === true ? 'True' : v === false ? 'False' : String(v));

// ---- Fragmentos y documentos (documents.py) ---------------------------------------------------------------------
function describe(buffer, nombre, mime, versionId, maximo = 50000000) {
  if (!buffer.length || buffer.length > maximo) throw new DocumentoInvalido('Archivo vacío o mayor que el máximo de 50 MB.');
  const huella = sha256(buffer);
  return { documento_id: stableId(`${versionId}:${huella}`), storage_file_id: stableId(`archivo:${huella}`), sha256: huella,
    nombre_original: String(nombre).split(/[\\/]/).pop(), mime_type: mime, tamano_bytes: buffer.length };
}

function fragmentar(texto, ubicacion, documentoId, serie, tamano = 400, solape = 60) {
  if (!(solape >= 0 && solape < tamano)) throw new DocumentoInvalido('Configuración de fragmentos inválida.');
  const trozos = [];
  for (let inicio = 0; inicio < texto.length; inicio += tamano - solape) {
    const valor = texto.slice(inicio, inicio + tamano).trim();
    if (valor) {
      const loc = { ...ubicacion, bloque: serie, caracter_inicio: inicio };
      trozos.push({ id: stableId(`${documentoId}:${pyJson(loc, { ordenar: true })}:${valor}`), documento_id: documentoId, texto: valor, ubicacion: loc });
    }
    if (inicio + tamano >= texto.length) break;
  }
  return trozos;
}

const celdaPy = (v) => {
  if (v === null || v === undefined || typeof v === 'string' || typeof v === 'boolean') return v ?? null;
  if (typeof v === 'number') {
    if (!Number.isFinite(v)) throw new DocumentoInvalido('La hoja contiene un número no finito.');
    return v;
  }
  return String(v);
};

// -- CSV
function leerCsv(texto) {
  const muestra = texto.slice(0, 8192);
  let delimitador = ',';
  let mejor = 0;
  for (const d of [',', ';', '\t', '|']) {
    const conteos = muestra.split(/\r?\n/).filter((l) => l.length).slice(0, 20).map((l) => l.split(d).length - 1);
    if (!conteos.length || conteos[0] === 0) continue;
    const consistente = conteos.filter((c) => c === conteos[0]).length;
    const puntaje = consistente * 1000 + conteos[0];
    if (puntaje > mejor) { mejor = puntaje; delimitador = d; }
  }
  const filas = [];
  let fila = [], campo = '', comillas = false, hayDatos = false;
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (comillas) {
      if (c === '"') { if (texto[i + 1] === '"') { campo += '"'; i++; } else comillas = false; } else campo += c;
    } else if (c === '"') { comillas = true; hayDatos = true; }
    else if (c === delimitador) { fila.push(campo); campo = ''; hayDatos = true; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && texto[i + 1] === '\n') i++;
      if (hayDatos || campo.length) { fila.push(campo); filas.push(fila); }
      else filas.push([]); // csv.reader entrega [] para una línea vacía
      fila = []; campo = ''; hayDatos = false;
    } else { campo += c; hayDatos = true; }
  }
  if (hayDatos || campo.length) { fila.push(campo); filas.push(fila); }
  return filas;
}

// -- XLSX (a partir de los archivos del zip, ya descomprimidos: { ruta: Buffer })
const FORMATOS_INCORPORADOS = { 0: 'General', 1: '0', 2: '0.00', 3: '#,##0', 4: '#,##0.00', 9: '0%', 10: '0.00%', 11: '0.00E+00', 12: '# ?/?', 13: '# ??/??',
  14: 'mm-dd-yy', 15: 'd-mmm-yy', 16: 'd-mmm', 17: 'mmm-yy', 18: 'h:mm AM/PM', 19: 'h:mm:ss AM/PM', 20: 'h:mm', 21: 'h:mm:ss', 22: 'm/d/yy h:mm',
  37: '#,##0 ;(#,##0)', 38: '#,##0 ;[Red](#,##0)', 39: '#,##0.00;(#,##0.00)', 40: '#,##0.00;[Red](#,##0.00)', 45: 'mm:ss', 46: '[h]:mm:ss',
  47: 'mmss.0', 48: '##0.0E+0', 49: '@' };

const desescapar = (t) => t.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
  .replace(/&#x([0-9a-fA-F]+);/g, (_, n) => String.fromCodePoint(parseInt(n, 16))).replace(/&amp;/g, '&');
const atributo = (texto, nombre) => { const m = new RegExp(`\\s${nombre}="([^"]*)"`).exec(texto); return m ? desescapar(m[1]) : null; };
const letrasAColumna = (letras) => [...letras].reduce((n, c) => n * 26 + c.charCodeAt(0) - 64, 0);

function esFormatoFecha(codigo) {
  if (!codigo || codigo === 'General') return false;
  const limpioCodigo = codigo.replace(/"[^"]*"|\[[^\]]*\]|\\./g, '');
  return /[dmyhs]/i.test(limpioCodigo) && !/^[#0,.?%@ ]*$/.test(limpioCodigo);
}

function fechaIso(serial) {
  const dias = Math.floor(serial);
  const segundos = Math.round((serial - dias) * 86400);
  const ms = Date.UTC(1899, 11, 30) + dias * 86400000 + segundos * 1000;
  return new Date(ms).toISOString().replace(/\.\d{3}Z$/, '');
}

function leerXlsx(archivos) {
  const texto = (ruta) => (archivos[ruta] ? Buffer.from(archivos[ruta]).toString('utf8') : null);
  const libro = texto('xl/workbook.xml');
  if (!libro) throw new DocumentoInvalido('No se pudo abrir el XLSX.');
  const relaciones = {};
  for (const m of (texto('xl/_rels/workbook.xml.rels') ?? '').matchAll(/<Relationship\b[^>]*>/g)) {
    relaciones[atributo(m[0], 'Id')] = atributo(m[0], 'Target');
  }
  const compartidas = [];
  for (const m of (texto('xl/sharedStrings.xml') ?? '').matchAll(/<si\b[^>]*>([\s\S]*?)<\/si>/g)) {
    compartidas.push(desescapar([...m[1].matchAll(/<t\b[^>]*>([\s\S]*?)<\/t>/g)].map((t) => t[1]).join('')));
  }
  const estilos = texto('xl/styles.xml') ?? '';
  const formatosPropios = {};
  for (const m of estilos.matchAll(/<numFmt\b[^>]*>/g)) formatosPropios[atributo(m[0], 'numFmtId')] = atributo(m[0], 'formatCode');
  const cellXfs = (/<cellXfs\b[^>]*>([\s\S]*?)<\/cellXfs>/.exec(estilos) ?? [, ''])[1];
  const formatoDeEstilo = [...cellXfs.matchAll(/<xf\b[^>]*?(?:\/>|>)/g)].map((m) => {
    const id = atributo(m[0], 'numFmtId') ?? '0';
    return formatosPropios[id] ?? FORMATOS_INCORPORADOS[id] ?? 'General';
  });
  const hojas = [];
  for (const m of libro.matchAll(/<sheet\b[^>]*>/g)) {
    const destino = relaciones[m[0].match(/\sr:id="([^"]*)"/)?.[1]];
    hojas.push({ nombre: atributo(m[0], 'name'), oculta: (atributo(m[0], 'state') ?? 'visible') !== 'visible',
      ruta: destino ? 'xl/' + destino.replace(/^\/?(xl\/)?/, '') : null });
  }
  const fragmentos = [], observaciones = [], hojasLeidas = [];
  let celdas = 0;
  return { hojas, texto, compartidas, formatoDeEstilo, fragmentos, observaciones, hojasLeidas, celdas, relaciones };
}

function extraerXlsx(archivos, meta) {
  const documentoId = meta.documento_id;
  const lectura = leerXlsx(archivos);
  const fragmentos = [], observaciones = [], hojas = [];
  let celdas = 0;
  for (const hoja of lectura.hojas) {
    const xml = hoja.ruta ? lectura.texto(hoja.ruta) : null;
    if (xml === null) throw new DocumentoInvalido('No se pudo abrir el XLSX.');
    let filasConDatos = 0;
    for (const f of xml.matchAll(/<row\b([^>]*?)(?:\/>|>([\s\S]*?)<\/row>)/g)) {
      const numeroFila = Number(atributo(f[1], 'r'));
      const registros = [];
      for (const c of (f[2] ?? '').matchAll(/<c\b([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g)) {
        celdas += 1;
        if (celdas > 1000000) throw new DocumentoInvalido('El Excel supera un millón de celdas; no se guardó una lectura parcial.');
        const cuerpo = c[2] ?? '';
        const referencia = atributo(c[1], 'r');
        const tipo = atributo(c[1], 't') ?? 'n';
        const estilo = Number(atributo(c[1], 's') ?? 0);
        const formula = /<f\b[^>]*>([\s\S]*?)<\/f>/.exec(cuerpo);
        const formulaCompartida = /<f\b[^>]*\/>/.test(cuerpo);
        const v = /<v\b[^>]*>([\s\S]*?)<\/v>/.exec(cuerpo);
        let cruda = v ? desescapar(v[1]) : null;
        let valor = null;
        if (tipo === 'inlineStr') valor = desescapar([...cuerpo.matchAll(/<t\b[^>]*>([\s\S]*?)<\/t>/g)].map((t) => t[1]).join(''));
        else if (cruda !== null) {
          if (tipo === 's') valor = lectura.compartidas[Number(cruda)];
          else if (tipo === 'str' || tipo === 'e') valor = cruda;
          else if (tipo === 'b') valor = cruda === '1';
          else {
            const numero = Number(cruda);
            valor = esFormatoFecha(lectura.formatoDeEstilo[estilo]) ? fechaIso(numero) : numero;
          }
        }
        const tieneFormula = Boolean(formula) || formulaCompartida;
        if (valor === null && !tieneFormula) continue;
        const original = tieneFormula ? '=' + desescapar(formula ? formula[1] : '') : valor;
        const registro = { celda: referencia, valor: celdaPy(valor), original: celdaPy(original), formato: lectura.formatoDeEstilo[estilo] ?? 'General' };
        if (tieneFormula) {
          registro.formula = original;
          if (valor === null) {
            observaciones.push({ tipo: 'formula_sin_resultado', descripcion: `La fórmula de ${hoja.nombre}!${referencia} no tiene resultado guardado.`,
              severidad: 'media', requiere_aclaracion: true, documento_id: documentoId });
          }
        }
        registros.push(registro);
      }
      if (registros.length) {
        // Una fila no se divide para no romper la relación columna/valor.
        fragmentos.push({ id: stableId(`${documentoId}:${hoja.nombre}:${numeroFila}`), documento_id: documentoId, texto: pyJson(registros, { ascii: false }),
          ubicacion: { hoja: hoja.nombre, fila: numeroFila, columnas: registros.map((x) => x.celda), origen: 'xlsx' } });
        filasConDatos += 1;
      }
    }
    hojas.push({ hoja: hoja.nombre, procesada: true, filas_con_datos: filasConDatos, oculta: hoja.oculta });
  }
  if (!fragmentos.length) throw new DocumentoInvalido('El documento no tiene contenido utilizable.');
  return { ...meta, fragmentos, paginas: [], hojas, uso_ocr: false, uso_rag: false, observaciones };
}

function extraerCsv(buffer, meta) {
  const documentoId = meta.documento_id;
  let texto;
  try { texto = new TextDecoder('utf-8', { fatal: true }).decode(buffer).replace(/^﻿/, ''); } catch { texto = new TextDecoder('windows-1252').decode(buffer); }
  const fragmentos = [];
  let celdas = 0;
  leerCsv(texto).forEach((fila, i) => {
    celdas += fila.length;
    if (celdas > 1000000) throw new DocumentoInvalido('El CSV supera un millón de celdas.');
    fragmentos.push({ id: stableId(`${documentoId}:csv:${i + 1}`), documento_id: documentoId, texto: pyJson(fila, { ascii: false }),
      ubicacion: { hoja: 'CSV', fila: i + 1, columnas: fila.map((_, k) => k + 1), origen: 'csv' } });
  });
  if (!fragmentos.length) throw new DocumentoInvalido('El documento no tiene contenido utilizable.');
  return { ...meta, fragmentos, paginas: [], hojas: [{ hoja: 'CSV', procesada: true, filas_con_datos: fragmentos.length }], uso_ocr: false, uso_rag: false, observaciones: [] };
}

// -- PDF: el nodo «Extract From File» de n8n entrega el texto de cada página (sin OCR). Una página sin texto no se descarta en silencio:
// queda una observación que pide revisar el original; si ninguna página tiene texto, el documento se rechaza.
function extraerPdf(textosPorPagina, meta) {
  const documentoId = meta.documento_id;
  if (!textosPorPagina.length) throw new DocumentoInvalido('El PDF no tiene páginas.');
  if (textosPorPagina.length > 300) throw new DocumentoInvalido('PDF protegido o con más de 300 páginas.');
  const fragmentos = [], paginas = [], observaciones = [];
  let conTexto = 0;
  textosPorPagina.forEach((texto, i) => {
    const pagina = i + 1;
    const contenido = (texto ?? '').trim();
    if (contenido.length < 40) {
      observaciones.push({ tipo: 'pagina_sin_texto', descripcion: `La página ${pagina} casi no tiene texto (¿escaneada o solo imagen?). Este lector no hace OCR: revisa el documento original.`,
        severidad: 'alta', requiere_aclaracion: true, documento_id: documentoId });
    } else conTexto += 1;
    if (contenido) fragmentos.push(...fragmentar(contenido, { pagina, origen: 'pdf_texto' }, documentoId, 0));
    paginas.push({ pagina, procesada: true, uso_ocr: false });
  });
  if (!conTexto) throw new DocumentoInvalido('El PDF no tiene texto legible (¿escaneado?). Este lector no hace OCR; envía un PDF con texto.');
  return { ...meta, fragmentos, paginas, hojas: [], uso_ocr: false, uso_rag: false, observaciones };
}

// ---- Tandas de contexto (rag.py sin búsqueda semántica) ------------------------------------------------------------
function tandas(documentos, maximo = 24000) {
  const todos = new Map();
  for (const d of documentos) for (const f of d.fragmentos) todos.set(f.id, f);
  const lotes = [];
  let lote = [], usado = 0;
  for (const fragmento of todos.values()) {
    if (fragmento.texto.length > maximo) throw new Error('Una fila supera el contexto máximo; no se recortó silenciosamente.');
    if (lote.length && usado + fragmento.texto.length > maximo) { lotes.push(lote); lote = []; usado = 0; }
    const { embedding, ...sinVector } = fragmento;
    lote.push(sinVector);
    usado += fragmento.texto.length;
  }
  if (lote.length) lotes.push(lote);
  return lotes;
}

// ---- Petición a Claude y lectura de su respuesta (contract.py + traducción de n8n) ----------------------------------
function requestClaude(fragmentos, documentos, modelo, system, esquema) {
  const contenido = JSON.stringify({ documentos: documentos.map((d) => ({ documento_id: d.documento_id, nombre: d.nombre_original })), fragmentos });
  const cuerpo = { model: modelo, max_tokens: 16000,
    system: system + '\n\nResponde únicamente con un objeto JSON válido que cumpla exactamente este esquema JSON. '
      + 'Sin texto adicional, sin comentarios y sin bloques de código:\n' + JSON.stringify(esquema),
    messages: [{ role: 'user', content: contenido }] };
  // Extraer datos no necesita razonar a fondo: el esfuerzo bajo deja los tokens para el JSON (modelos 5.x).
  if (/^claude-(opus|sonnet|haiku)-5/.test(modelo)) cuerpo.output_config = { effort: 'low' };
  return cuerpo;
}

function validarEsquema(esquema, valor, ruta = '$') {
  const tipos = Array.isArray(esquema.type) ? esquema.type : esquema.type ? [esquema.type] : null;
  const tipoDe = (v) => (v === null ? 'null' : Array.isArray(v) ? 'array' : typeof v === 'number' ? 'number' : typeof v);
  if (tipos && !tipos.includes(tipoDe(valor))) throw new Error(`${ruta}: se esperaba ${tipos.join(' o ')}`);
  if (esquema.enum && !esquema.enum.includes(valor)) throw new Error(`${ruta}: ${JSON.stringify(valor)} no es uno de ${esquema.enum.join(', ')}`);
  if (typeof valor === 'number') {
    if (esquema.minimum !== undefined && valor < esquema.minimum) throw new Error(`${ruta}: menor que ${esquema.minimum}`);
    if (esquema.maximum !== undefined && valor > esquema.maximum) throw new Error(`${ruta}: mayor que ${esquema.maximum}`);
  }
  if (esquema.properties && valor && typeof valor === 'object' && !Array.isArray(valor)) {
    for (const k of esquema.required ?? []) if (!(k in valor)) throw new Error(`${ruta}: falta «${k}»`);
    if (esquema.additionalProperties === false) for (const k of Object.keys(valor)) if (!(k in esquema.properties)) throw new Error(`${ruta}: «${k}» no está permitido`);
    for (const [k, sub] of Object.entries(esquema.properties)) if (k in valor) validarEsquema(sub, valor[k], `${ruta}.${k}`);
  }
  if (esquema.items && Array.isArray(valor)) valor.forEach((x, i) => validarEsquema(esquema.items, x, `${ruta}[${i}]`));
}

function parseRespuesta(r, esquema) {
  if (r.type === 'error' || r.error) throw new Error('El modelo rechazó la petición: ' + (r.error?.message ?? 'error sin detalle'));
  if (r.stop_reason === 'refusal') throw new Error('El modelo rechazó la petición por seguridad.');
  if (!(r.stop_reason === 'end_turn' || r.stop_reason === 'stop_sequence')) {
    throw new Error(`El modelo no devolvió una respuesta completa (${r.stop_reason ?? 'sin motivo'}; salida: ${r.usage?.output_tokens ?? '?'} tokens).`);
  }
  let texto = (r.content ?? []).filter((b) => b.type === 'text').map((b) => b.text).join('').trim();
  texto = texto.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
  const ini = texto.indexOf('{'), fin = texto.lastIndexOf('}');
  if (ini >= 0 && fin > ini) texto = texto.slice(ini, fin + 1);
  const datos = JSON.parse(texto);
  validarEsquema(esquema, datos);
  return datos;
}

// ---- Validación independiente (contract.py) -------------------------------------------------------------------------
const COMERCIALES = ['moneda', 'subtotal', 'impuestos', 'total', 'plazo_entrega', 'condiciones_pago', 'vigencia_oferta'];
const NUMERICOS = new Set(['subtotal', 'impuestos', 'total', 'cantidad', 'precio_unitario', 'parcial', 'valor_numerico']);
const CAMPOS_ITEM = ['descripcion', 'cantidad', 'unidad', 'precio_unitario', 'parcial'];
const UNIDADES = { und: 'unidad', 'und.': 'unidad', un: 'unidad', unidad: 'unidad', unidades: 'unidad', kg: 'kg', kilogramo: 'kg', kilogramos: 'kg', m: 'm',
  metro: 'm', metros: 'm', m2: 'm2', 'm²': 'm2', m3: 'm3', 'm³': 'm3', mm: 'mm', cm: 'cm', l: 'l', litro: 'l', kw: 'kW', w: 'W', 'm/s': 'm/s', mes: 'mes', 'día': 'dia', dia: 'dia' };
const ALIAS_MONEDA = { 'us$': 'USD', 's/': 'PEN', 's/.': 'PEN', '€': 'EUR', 'dólares americanos': 'USD', 'dolares americanos': 'USD', 'dólares': 'USD', dolares: 'USD',
  soles: 'PEN', 'nuevos soles': 'PEN' };
const normalizarUnidad = (u) => UNIDADES[(u ?? '').toLowerCase().trim()] ?? null;

function detectarConvencion(textos) {
  const junto = textos.join(' ');
  const us = (junto.match(/\d{1,3}(?:,\d{3})+\.\d{1,2}(?!\d)/g) ?? []).length;
  const eu = (junto.match(/\d{1,3}(?:\.\d{3})+,\d{1,2}(?!\d)/g) ?? []).length;
  if (us && !eu) return 'us';
  if (eu && !us) return 'eu';
  return null;
}

function detectarMoneda(textos) {
  const t = textos.join(' ').toLowerCase();
  const usd = /d[oó]lares?\s+(?:americanos?|estadounidenses?)|\busd\b|\bus\s?\$/.test(t);
  const pen = /nuevos?\s+soles|\bsoles\b|\bpen\b|(?<![a-z])s\/\.?(?=\s*\d)/.test(t);
  if (usd && !pen) return 'USD';
  if (pen && !usd) return 'PEN';
  return null;
}

function numeroDe(original, convencion = null) {
  if (original === null || original === undefined) return null;
  const sinPorcentaje = original.replace(/\d+(?:[.,]\d+)?\s*%/g, ' '); // el porcentaje del impuesto no es el importe
  const fichas = sinPorcentaje.match(/-?\d[\d.,]*\d|-?\d/g) ?? [];
  if (fichas.length !== 1) return null;
  let texto = fichas[0];
  if (texto.includes(',') && texto.includes('.')) {
    const [decimal, miles] = texto.lastIndexOf(',') > texto.lastIndexOf('.') ? [',', '.'] : ['.', ','];
    texto = texto.split(miles).join('').replace(decimal, '.');
  } else if (texto.includes(',') || texto.includes('.')) {
    const marca = texto.includes(',') ? ',' : '.';
    const grupos = texto.split(marca);
    const esMiles = (marca === ',' && convencion === 'us') || (marca === '.' && convencion === 'eu');
    if (grupos.length > 2) {
      if (!(esMiles && grupos.slice(1).every((g) => g.length === 3))) return null;
      texto = grupos.join('');
    } else if (grupos[1].length === 3) {
      if (!esMiles) return null; // 1,234 y 1.234 son ambiguos sin la convención del documento.
      texto = grupos.join('');
    } else texto = texto.replace(marca, '.');
  }
  const n = Number(texto);
  return Number.isFinite(n) ? n : null;
}

const copiaProfunda = (v) => JSON.parse(JSON.stringify(v));
const subcadena = (parte, todo) => todo.includes(parte);

function combine(respuestas, documentos, version, nombreModelo, esquema, ahora = null) {
  const fragmentos = new Map();
  for (const d of documentos) for (const f of d.fragmentos) fragmentos.set(f.id, f);
  const docIds = new Set(documentos.map((d) => d.documento_id));
  const observaciones = [], evidencias = [], items = [], tecnicas = [], comerciales = [], inferencias = [];
  const tipos = {};
  const prioridad = { otro_documento: 0, anexo_proveedor: 1, ficha_tecnica_proveedor: 2, cotizacion_proveedor: 3 };
  const versionId = version.id;
  const textos = Object.fromEntries(documentos.map((d) => [d.documento_id, d.fragmentos.map((f) => f.texto)]));
  const convenciones = Object.fromEntries(Object.entries(textos).map(([k, t]) => [k, detectarConvencion(t)]));
  const monedas = Object.fromEntries(Object.entries(textos).map(([k, t]) => [k, detectarMoneda(t)]));

  const observar = (tipo, descripcion, severidad = 'media', aclarar = true, doc = null, refs = null) => observaciones.push({
    tipo, descripcion, severidad, requiere_aclaracion: aclarar, documento_id: doc, evidencia_ids: refs ?? [] });

  respuestas.forEach((datos, lote) => {
    validarEsquema(esquema, datos);
    const mapa = {}, evidenciaLote = {};
    for (const fuente of datos.evidencias) {
      const fragmento = fragmentos.get(fuente.fragmento_id);
      if (fuente.id in mapa || !fragmento || fragmento.documento_id !== fuente.documento_id) throw new Error('El modelo devolvió una referencia de evidencia inválida.');
      if (!fuente.texto_fuente.trim() || !subcadena(fuente.texto_fuente, fragmento.texto)) throw new Error('La cita de evidencia no existe en el fragmento indicado.');
      const clave = stableId(`${versionId}:evidencia:${lote}:${fuente.id}`);
      mapa[fuente.id] = clave;
      const registro = { ...fuente, id: clave, ubicacion: fragmento.ubicacion, confianza: Math.min(fuente.confianza, fragmento.ubicacion.confianza ?? 1) };
      evidencias.push(registro);
      evidenciaLote[clave] = registro;
    }
    const refs = (registro) => {
      if (registro.evidencia_ids.some((x) => !(x in mapa))) throw new Error('Un valor refiere a evidencia que no existe en su lote.');
      const resultado = registro.evidencia_ids.map((x) => mapa[x]);
      if (resultado.some((x) => evidenciaLote[x].documento_id !== registro.documento_id)) throw new Error('Se mezcló evidencia de documentos diferentes.');
      return resultado;
    };
    const validarValores = (valores, originales, referencias, doc) => {
      const cita = referencias.map((x) => evidenciaLote[x].texto_fuente).join(' ');
      for (const [campo, valor] of Object.entries(valores)) {
        if (valor === null) continue;
        const original = originales[campo];
        if (!referencias.length || nulo(original) || !original.trim() || !subcadena(original, cita)) throw new Error(`El campo ${campo} no tiene texto original verificable.`);
        if (NUMERICOS.has(campo)) {
          const escapado = original.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
          if (!new RegExp('(?<![\\d.,])' + escapado + '(?![\\d.,])').test(cita)) throw new Error(`El texto numérico de ${campo} no es un valor completo de la fuente.`);
          const leido = numeroDe(original, convenciones[doc]);
          if (leido === null) {
            valores[campo] = null;
            observar('numero_ambiguo', `El campo ${campo} tiene un número o unidad que necesita confirmación: ${original}`, 'media', true, doc, referencias);
          } else if (leido !== Number(valor)) throw new Error(`El número de ${campo} no coincide con el original.`);
        }
      }
    };

    for (let entrada of datos.comerciales) {
      if (!docIds.has(entrada.documento_id)) throw new Error('Datos comerciales de otra versión.');
      entrada = copiaProfunda(entrada);
      entrada.evidencia_ids = refs(entrada);
      validarValores(entrada.valores, entrada.originales, entrada.evidencia_ids, entrada.documento_id);
      const moneda = entrada.valores.moneda;
      const monedaOriginal = entrada.originales.moneda;
      const clave = (monedaOriginal ?? '').trim();
      const resuelta = ALIAS_MONEDA[clave.toLowerCase()] ?? clave.toUpperCase();
      // "$" solo no identifica la moneda; sí lo hace si el mismo documento la nombra de forma explícita.
      const porContexto = clave === '$' && monedas[entrada.documento_id] === moneda;
      if (moneda !== null && (!/^[A-Z]{3}$/.test(moneda) || (resuelta !== moneda && !porContexto))) {
        // Una moneda dudosa no invalida el resto de la lectura: se deja vacía y se pide confirmación.
        entrada.valores.moneda = null;
        observar('moneda_ambigua', `La moneda no tiene una identificación explícita inequívoca: ${monedaOriginal}`, 'media', true, entrada.documento_id, entrada.evidencia_ids);
      }
      comerciales.push(entrada);
    }
    for (let entrada of datos.items) {
      if (!docIds.has(entrada.documento_id)) throw new Error('Ítem de otra versión.');
      entrada = copiaProfunda(entrada);
      entrada.evidencia_ids = refs(entrada);
      const valores = Object.fromEntries(CAMPOS_ITEM.map((x) => [x, entrada[x]]));
      validarValores(valores, entrada.originales, entrada.evidencia_ids, entrada.documento_id);
      Object.assign(entrada, valores);
      const normalizada = normalizarUnidad(entrada.unidad);
      if (entrada.unidad_normalizada && normalizada === null) observar('unidad_no_normalizada', 'Se conservó la unidad original; requiere revisión para E4.', 'baja', false, entrada.documento_id);
      entrada.unidad_normalizada = normalizada;
      if (['cantidad', 'precio_unitario', 'parcial'].some((x) => entrada[x] !== null && entrada[x] < 0)) {
        observar('valor_negativo', 'La propuesta contiene cantidades o importes negativos.', 'alta', true, entrada.documento_id);
      }
      const anclas = [...new Set(entrada.evidencia_ids.map((x) => pyJson(Object.fromEntries(['pagina', 'bloque', 'hoja', 'fila'].map((k) => [k, evidenciaLote[x].ubicacion[k] ?? null])), { ordenar: true })))].sort();
      const identidad = [entrada.documento_id, entrada.referencia_item, entrada.originales, anclas];
      entrada.id = stableId(`${versionId}:item:${pyJson(identidad, { ordenar: true, ascii: false })}`);
      items.push(entrada);
    }
    for (let entrada of datos.especificaciones_tecnicas) {
      if (!docIds.has(entrada.documento_id)) throw new Error('Especificación de otra versión.');
      entrada = { ...entrada };
      entrada.evidencia_ids = refs(entrada);
      if (entrada.valor_original !== null) {
        const citas = entrada.evidencia_ids.map((x) => evidenciaLote[x].texto_fuente).join(' ');
        if (!entrada.evidencia_ids.length || !subcadena(entrada.valor_original, citas)) throw new Error('Especificación sin evidencia verificable.');
      }
      if (entrada.valor_numerico !== null) {
        const m = /^\s*(-?\d[\d.,]*)\s*[^\d]*$/.exec(entrada.valor_original ?? '');
        const leido = m ? numeroDe(m[1], convenciones[entrada.documento_id]) : null;
        if (leido === null) {
          entrada.valor_numerico = null;
          // Un valor compuesto (1300x1250, 220 V 60 Hz) no tiene una sola cifra: se conserva el texto y es solo informativo.
          observar('numero_tecnico_ambiguo', 'Se conservó la especificación original sin inferir su valor numérico.', 'baja', false, entrada.documento_id, entrada.evidencia_ids);
        } else if (leido !== Number(entrada.valor_numerico)) throw new Error('El número de la especificación no coincide con el original.');
      }
      entrada.unidad_normalizada = normalizarUnidad(entrada.unidad_original);
      entrada.id = stableId(`${versionId}:tecnica:${entrada.documento_id}:${entrada.campo}:${pyStr(entrada.referencia_item)}:${pyStr(entrada.valor_original)}`);
      tecnicas.push(entrada);
    }
    for (const entrada of datos.documentos) {
      if (!docIds.has(entrada.documento_id)) throw new Error('Clasificación documental ajena a la versión.');
      const previo = tipos[entrada.documento_id] ?? 'otro_documento';
      if (prioridad[entrada.tipo_documental] >= prioridad[previo]) tipos[entrada.documento_id] = entrada.tipo_documental;
    }
    for (const entrada of datos.observaciones) {
      if (entrada.documento_id !== null && !docIds.has(entrada.documento_id)) throw new Error('Observación de otra versión.');
      if (entrada.evidencia_ids.some((x) => !(x in mapa))) throw new Error('Observación sin evidencia existente.');
      // OCR correcto no es una incidencia.
      if (['uso_ocr', 'ocr_aplicado', 'ocr_correcto'].includes(entrada.tipo.toLowerCase())) continue;
      observaciones.push({ ...entrada, evidencia_ids: entrada.evidencia_ids.map((x) => mapa[x]) });
    }
    inferencias.push(...datos.inferencias);
  });
  if (Object.keys(tipos).length !== docIds.size || [...docIds].some((d) => !(d in tipos))) throw new Error('El modelo no clasificó todos los documentos.');

  const unicos = new Map();
  for (const entrada of items) {
    if (unicos.has(entrada.id)) {
      const previo = unicos.get(entrada.id);
      previo.evidencia_ids = [...new Set([...previo.evidencia_ids, ...entrada.evidencia_ids])];
    } else unicos.set(entrada.id, entrada);
  }
  let items2 = [...unicos.values()];
  const firma = (t) => (t ?? '').toLowerCase().replace(/[^a-z0-9]+/g, '');
  const conImporte = new Set(items2.filter((x) => ['cantidad', 'precio_unitario', 'parcial'].some((f) => x[f] !== null)));
  const repetidos = new Set(items2.filter((x) => !conImporte.has(x) && firma(x.descripcion) && [...conImporte].some((y) => y.documento_id === x.documento_id
    && (firma(y.descripcion).includes(firma(x.descripcion)) || firma(x.descripcion).includes(firma(y.descripcion))))).map((x) => x.id));
  items2 = items2.filter((x) => !repetidos.has(x.id));
  const tecnicas2 = [...new Map(tecnicas.map((x) => [x.id, x])).values()];
  for (const [docId, tipo] of Object.entries(tipos)) {
    const significativo = items2.concat(tecnicas2).some((x) => x.documento_id === docId)
      || comerciales.some((c) => c.documento_id === docId && Object.values(c.valores).some((v) => v !== null));
    if (['cotizacion_proveedor', 'ficha_tecnica_proveedor'].includes(tipo) && !significativo) throw new Error('La respuesta clasificó un documento pero no recuperó ninguno de sus datos.');
  }
  const combinado = {};
  for (const campo of COMERCIALES) {
    const hallados = new Set(comerciales.filter((c) => c.valores[campo] !== null).map((c) => JSON.stringify(c.valores[campo])));
    combinado[campo] = hallados.size === 1 ? JSON.parse([...hallados][0]) : null;
    if (hallados.size > 1) observar('valores_por_documento', `El campo ${campo} tiene valores distintos entre documentos; se conservaron por separado sin sumarlos ni elegir uno.`);
    else if (!hallados.size) observar('dato_no_encontrado', `No se encontró ${campo} explícito en la propuesta.`);
  }
  // Coherencia aritmética: verifica, nunca rellena importes que no estén escritos.
  for (const entrada of items2) {
    const [q, precio, parcial] = [entrada.cantidad, entrada.precio_unitario, entrada.parcial];
    if ([q, precio, parcial].every((x) => x !== null) && Math.abs(limpio(q * precio) - parcial) > 0.02) {
      observar('incoherencia_parcial', 'Cantidad por precio unitario no coincide con el parcial indicado.', 'alta', true, entrada.documento_id, entrada.evidencia_ids);
    }
    for (const campo of ['cantidad', 'unidad', 'precio_unitario', 'parcial']) {
      if (entrada[campo] === null) {
        // Que falte la unidad es informativo: no pide aclaración. Cantidad, precio y parcial sí.
        const [severidad, aclarar] = campo === 'unidad' ? ['baja', false] : ['media', true];
        observar('campo_item_faltante', `Un ítem no indica ${campo}; E4 lo recibirá vacío.`, severidad, aclarar, entrada.documento_id);
      }
    }
  }
  for (const entrada of comerciales) {
    const [sub, imp, total] = ['subtotal', 'impuestos', 'total'].map((x) => entrada.valores[x]);
    if ([sub, imp, total].every((x) => x !== null) && Math.abs(limpio(sub + imp) - total) > 0.02) {
      observar('incoherencia_total', 'Subtotal más impuestos no coincide con el total indicado.', 'alta', true, entrada.documento_id);
    }
    const mismoDoc = items2.filter((x) => x.documento_id === entrada.documento_id);
    if (sub !== null && mismoDoc.length && mismoDoc.every((x) => x.parcial !== null)) {
      if (Math.abs(limpio(mismoDoc.reduce((a, x) => a + x.parcial, 0)) - sub) > 0.02) {
        observar('incoherencia_subtotal', 'La suma de parciales leídos no coincide con el subtotal. Comprueba descuentos, cargos o ítems faltantes.', 'alta', true, entrada.documento_id);
      }
    }
  }
  // Solo compara especificaciones de la MISMA referencia explícita de equipo.
  const vistos = new Map();
  for (const entrada of tecnicas2) {
    if (!entrada.referencia_item || entrada.valor_original === null) continue;
    const clave = pyJson([entrada.referencia_item.toLowerCase(), entrada.campo.toLowerCase()]);
    const valor = entrada.valor_original.toLowerCase().trim();
    if (vistos.has(clave) && vistos.get(clave) !== valor) {
      observar('contradiccion_tecnica', `La referencia ${entrada.referencia_item} tiene valores contradictorios para ${entrada.campo}.`, 'alta', true, entrada.documento_id, entrada.evidencia_ids);
    }
    vistos.set(clave, valor);
  }
  for (const documento of documentos) {
    if (!documento.paginas.every((p) => p.procesada) || !documento.hojas.every((s) => s.procesada)) throw new Error('Cobertura de páginas u hojas incompleta.');
    observaciones.push(...documento.observaciones.map((o) => ({ ...o, evidencia_ids: [] })));
  }
  const obsUnicas = new Map();
  for (const observacion of observaciones) {
    const clave = stableId(`${versionId}:obs:${pyJson(observacion, { ordenar: true })}`);
    obsUnicas.set(clave, { ...observacion, observacion_id: clave, estado: 'pendiente' });
  }
  const lista = [...obsUnicas.values()];
  return {
    version_id: versionId, correo_id: version.correo_id, solicitud_id: version.solicitud_id, proveedor_id: version.proveedor_id,
    numero_version: version.version, es_final: version.es_final, estado_procesamiento: lista.length ? 'completado_con_observaciones' : 'completado',
    documentos: documentos.map((d) => ({ documento_id: d.documento_id, correo_id: version.correo_id, version_id: versionId, nombre_original: d.nombre_original,
      nombres_originales: d.nombres_originales ?? [d.nombre_original], mime_type: d.mime_type, sha256: d.sha256, storage_file_id: d.storage_file_id,
      tamano_bytes: d.tamano_bytes, tipo_documental: tipos[d.documento_id], paginas: d.paginas, hojas: d.hojas, estado_lectura: 'completado' })),
    datos_comerciales: combinado, datos_comerciales_documentos: comerciales, items: items2, especificaciones_tecnicas: tecnicas2, evidencias,
    observaciones: lista, inferencias,
    procesamiento: { modelo: nombreModelo, uso_ocr: documentos.some((d) => d.uso_ocr), uso_rag: documentos.some((d) => d.uso_rag),
      procesado_at: ahora ?? new Date().toISOString().replace('Z', '+00:00'), cobertura_completa: true, fragmentos_procesados: fragmentos.size },
  };
}

if (typeof module !== 'undefined') {
  module.exports = { sha1, sha256, stableId, pyJson, describe, fragmentar, leerCsv, extraerCsv, extraerXlsx, extraerPdf, tandas, requestClaude, parseRespuesta, validarEsquema,
    detectarConvencion, detectarMoneda, numeroDe, combine, DocumentoInvalido };
}
