// Compara n8n/etapa4/homologacion_core.js con la salida de referencia de app/homologacion (archivo indicado en CASOS).
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const core = require('../../n8n/etapa4/homologacion_core.js');

const datos = JSON.parse(fs.readFileSync(process.env.CASOS, 'utf8'));

function casi(a, b, ruta) {
  if (typeof a === 'number' && typeof b === 'number') return assert.ok(Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(b)), `${ruta}: ${a} != ${b}`);
  if (Array.isArray(a)) { assert.ok(Array.isArray(b), `${ruta}: se esperaba lista`); assert.equal(a.length, b.length, `${ruta}: largo`); return a.forEach((x, i) => casi(x, b[i], `${ruta}[${i}]`)); }
  if (a && typeof a === 'object') {
    assert.ok(b && typeof b === 'object', `${ruta}: se esperaba objeto`);
    assert.deepEqual(Object.keys(a).sort(), Object.keys(b).sort(), `${ruta}: claves`);
    return Object.keys(a).forEach((k) => casi(a[k], b[k], `${ruta}.${k}`));
  }
  assert.equal(a, b, ruta);
}

test('SHA-256 coincide con el estándar', () => {
  assert.equal(core.sha256(''), 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855');
  assert.equal(core.sha256('abc'), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
  assert.equal(core.sha256('ñandú ✓'.repeat(40)).length, 64);
});

for (const [nombre, caso] of Object.entries(datos.casos)) {
  test(`E4 ${nombre}`, () => {
    const preparado = core.prepare(caso.paquete);
    casi(preparado, caso.preparado, 'preparado');
    // La petición a Claude lleva lo mismo que la de Python (el texto del sistema lo trae el flujo).
    const cuerpo = core.requestClaude(preparado, 'claude-sonnet-5-5', caso.cuerpo_claude.system);
    assert.deepEqual({ ...cuerpo, messages: undefined }, { ...caso.cuerpo_claude, messages: undefined });
    casi(JSON.parse(cuerpo.messages[0].content), JSON.parse(caso.cuerpo_claude.messages[0].content), 'mensaje');
    if (caso.esperado.errores) {
      assert.throws(() => core.build(preparado, caso.salida, 'claude-sonnet-5-5', datos.esquema, datos.ahora), (e) => {
        assert.ok(e instanceof core.HomologacionInvalida);
        assert.equal(e.errores.length, caso.esperado.errores.length, `errores: ${e.errores.join(' | ')}`);
        // Los mensajes de forma pueden variar entre validadores; los demás deben coincidir.
        if (!caso.esperado.errores[0].startsWith('La respuesta no cumple el formato')) assert.deepEqual(e.errores, caso.esperado.errores);
        return true;
      });
      return;
    }
    const h = core.build(preparado, caso.salida, 'claude-sonnet-5-5', datos.esquema, datos.ahora.replace('+00:00', '+00:00'));
    casi(h, caso.esperado.homologacion, 'homologacion');
  });
}

for (const [nombre, texto] of Object.entries(datos.textos)) {
  test(`lectura del texto: ${nombre}`, () => {
    const ref = datos.lecturas[nombre];
    if (ref.error) return assert.throws(() => core.parseTexto(texto, datos.esquema));
    casi(core.parseTexto(texto, datos.esquema), ref.ok, 'respuesta');
  });
}
