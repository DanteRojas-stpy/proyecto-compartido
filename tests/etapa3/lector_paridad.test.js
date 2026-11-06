// Compara n8n/etapa3/lector_core.js con la salida de referencia de app/etapa3 (archivo indicado en CASOS).
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const core = require('../../n8n/etapa3/lector_core.js');

const datos = JSON.parse(fs.readFileSync(process.env.CASOS, 'utf8'));
const ESQUEMA = datos.esquema;

function casi(a, b, ruta) {
  if (typeof a === 'number' && typeof b === 'number') return assert.ok(Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(b)), `${ruta}: ${a} != ${b}`);
  if (Array.isArray(a)) { assert.ok(Array.isArray(b), `${ruta}: se esperaba lista`); assert.equal(a.length, b.length, `${ruta}: largo ${a.length} != ${b.length}`); return a.forEach((x, i) => casi(x, b[i], `${ruta}[${i}]`)); }
  if (a && typeof a === 'object') {
    assert.ok(b && typeof b === 'object', `${ruta}: se esperaba objeto`);
    assert.deepEqual(Object.keys(a).sort(), Object.keys(b).sort(), `${ruta}: claves`);
    return Object.keys(a).forEach((k) => casi(a[k], b[k], `${ruta}.${k}`));
  }
  assert.equal(a, b, ruta);
}

test('huellas estándar', () => {
  assert.equal(core.sha256(Buffer.from('abc')), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
  assert.equal(core.sha1(Buffer.from('abc')).toString('hex'), 'a9993e364706816aba3e25717850c26c9cd0d89d');
  assert.equal(core.sha1(Buffer.from('a'.repeat(1000))).length, 20);
});

for (const c of datos.numeros) {
  test(`número «${c.texto.replace(/\n/g, ' ')}» (${c.convencion})`, () => {
    const n = core.numeroDe(c.texto, c.convencion);
    if (c.esperado === null) assert.equal(n, null); else casi(n, c.esperado, 'numero');
  });
}
datos.deteccion.forEach((c, i) => test(`detección ${i}`, () => {
  assert.equal(core.detectarConvencion(c.textos), c.convencion);
  assert.equal(core.detectarMoneda(c.textos), c.moneda);
}));

for (const c of datos.combine) {
  test(`combine ${c.nombre}`, () => {
    const ahora = '2026-11-05T21:00:00+00:00';
    if (c.esperado.error !== undefined) {
      assert.throws(() => core.combine(c.respuestas, c.documentos, c.version, 'modelo-prueba', ESQUEMA, ahora), (e) => {
        if (!c.esperado.esquema) assert.equal(e.message, c.esperado.error);
        return true;
      });
      return;
    }
    const r = core.combine(c.respuestas, c.documentos, c.version, 'modelo-prueba', ESQUEMA, ahora);
    const ref = c.esperado.resultado;
    delete ref.procesamiento.procesado_at; delete r.procesamiento.procesado_at;
    casi(r, ref, 'resultado');
  });
}

for (const c of datos.describe) {
  test(`describe ${c.nombre}`, () => casi(core.describe(Buffer.from(c.b64, 'base64'), c.nombre, 'application/octet-stream', c.version), c.esperado, 'meta'));
}
datos.fragmentos.forEach((c, i) => test(`fragmentos ${i}`, () => casi(core.fragmentar(c.texto, c.ubicacion, c.documento, c.serie), c.esperado, 'fragmentos')));
datos.tandas.forEach((c, i) => test(`tandas ${i} (máximo ${c.maximo})`, () => casi(core.tandas(c.documentos, c.maximo), c.esperado, 'tandas')));

for (const c of datos.extraccion) {
  test(`extracción ${c.nombre}`, () => {
    const buffer = Buffer.from(c.b64, 'base64');
    const ejecutar = () => {
      const meta = core.describe(buffer, c.nombre, c.mime, datos.version);
      casi(meta, c.meta, 'meta');
      if (c.entradas) {
        const archivos = Object.fromEntries(Object.entries(c.entradas).map(([k, v]) => [k, Buffer.from(v, 'base64')]));
        return core.extraerXlsx(archivos, meta);
      }
      return core.extraerCsv(buffer, meta);
    };
    if (c.esperado.error) return assert.throws(ejecutar, (e) => { assert.equal(e.message, c.esperado.error); return true; });
    casi(ejecutar(), c.esperado.resultado, 'documento');
  });
}

// ---- PDF (no hay referencia en Python: allí se lee con PyMuPDF y OCR) ----
test('PDF: fragmenta por página y deja constancia de las páginas sin texto', () => {
  const meta = core.describe(Buffer.from('%PDF-1.4 x'), 'ficha.pdf', 'application/pdf', datos.version);
  const largo = 'Ascensor de pasajeros 630 kg, 17 paradas, velocidad 1.75 m/s. '.repeat(20);
  const r = core.extraerPdf([largo, 'corto', largo.slice(0, 80)], meta);
  assert.deepEqual(r.paginas.map((p) => [p.pagina, p.procesada, p.uso_ocr]), [[1, true, false], [2, true, false], [3, true, false]]);
  assert.deepEqual(r.fragmentos.map((f) => f.ubicacion.pagina).filter((x, i, a) => a.indexOf(x) === i), [1, 2, 3]);
  assert.ok(r.fragmentos.every((f) => f.texto.length <= 400 && f.ubicacion.origen === 'pdf_texto'));
  assert.equal(new Set(r.fragmentos.map((f) => f.id)).size, r.fragmentos.length, 'ids únicos');
  assert.deepEqual(r.observaciones.map((o) => o.descripcion.match(/página (\d)/)[1]), ['2']);
  assert.equal(r.observaciones[0].requiere_aclaracion, true);
  assert.equal(r.uso_ocr, false);
  // Los mismos datos dan los mismos identificadores (versiones y documentos estables).
  assert.deepEqual(core.extraerPdf([largo, 'corto', largo.slice(0, 80)], meta).fragmentos.map((f) => f.id), r.fragmentos.map((f) => f.id));
});

test('PDF: sin ninguna página con texto se rechaza como documento inválido', () => {
  const meta = core.describe(Buffer.from('%PDF-1.4 y'), 'escaneo.pdf', 'application/pdf', datos.version);
  assert.throws(() => core.extraerPdf(['', ' ', 'x'], meta), (e) => e instanceof core.DocumentoInvalido && /OCR/.test(e.message));
  assert.throws(() => core.extraerPdf([], meta), core.DocumentoInvalido);
});

test('Claude: pide JSON con el esquema, sin parámetros que los modelos 5.x rechazan, y lee la respuesta', () => {
  const docs = [{ documento_id: 'd1', nombre_original: 'a.pdf' }];
  const cuerpo = core.requestClaude([{ id: 'f1', texto: 'x' }], docs, 'claude-opus-5-5', 'SISTEMA', ESQUEMA);
  assert.equal(cuerpo.model, 'claude-opus-5-5'); assert.deepEqual(cuerpo.output_config, { effort: 'low' });
  assert.ok(cuerpo.system.startsWith('SISTEMA') && cuerpo.system.includes('"comerciales"'));
  assert.ok(!('temperature' in cuerpo) && !('tool_choice' in cuerpo));
  assert.deepEqual(JSON.parse(cuerpo.messages[0].content).documentos, [{ documento_id: 'd1', nombre: 'a.pdf' }]);
  assert.ok(!('output_config' in core.requestClaude([], docs, 'otro-modelo', 'S', ESQUEMA)));
  const vacio = { comerciales: [], items: [], especificaciones_tecnicas: [], evidencias: [], observaciones: [], documentos: [], inferencias: [] };
  const ok = (texto, stop = 'end_turn') => ({ type: 'message', stop_reason: stop, content: [{ type: 'text', text: texto }], usage: { output_tokens: 5 } });
  assert.deepEqual(core.parseRespuesta(ok(JSON.stringify(vacio)), ESQUEMA), vacio);
  assert.deepEqual(core.parseRespuesta(ok('```json\n' + JSON.stringify(vacio) + '\n```'), ESQUEMA), vacio);
  assert.deepEqual(core.parseRespuesta(ok('Aquí está: ' + JSON.stringify(vacio) + ' listo'), ESQUEMA), vacio);
  assert.throws(() => core.parseRespuesta(ok('{}', 'max_tokens'), ESQUEMA), /16|completa|max_tokens/);
  assert.throws(() => core.parseRespuesta({ type: 'error', error: { message: 'Overloaded' } }, ESQUEMA), /Overloaded/);
  assert.throws(() => core.parseRespuesta(ok('{}', 'refusal'), ESQUEMA), /seguridad|completa/);
  assert.throws(() => core.parseRespuesta(ok(JSON.stringify(ESQUEMA)), ESQUEMA));
});
