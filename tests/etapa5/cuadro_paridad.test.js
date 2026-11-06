// Compara n8n/etapa5/cuadro_core.js con la salida de referencia de app/cuadro/llenar.py (archivo indicado en CASOS).
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const core = require('../../n8n/etapa5/cuadro_core.js');

const casos = JSON.parse(fs.readFileSync(process.env.CASOS, 'utf8'));

function casi(a, b, ruta) {
  if (typeof a === 'number' && typeof b === 'number') return assert.ok(Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(b)), `${ruta}: ${a} != ${b}`);
  if (Array.isArray(a)) { assert.equal(a.length, b.length, ruta); return a.forEach((x, i) => casi(x, b[i], `${ruta}[${i}]`)); }
  if (a && typeof a === 'object') {
    assert.deepEqual(Object.keys(a).sort(), Object.keys(b).sort(), `${ruta}: claves`);
    return Object.keys(a).forEach((k) => casi(a[k], b[k], `${ruta}.${k}`));
  }
  assert.equal(a, b, ruta);
}

for (const [nombre, caso] of Object.entries(casos)) {
  for (const etiqueta of ['minima', 'real']) {
    const ref = caso[etiqueta];
    if (!ref) continue;
    test(`${nombre} / plantilla ${etiqueta}`, () => {
      let plan;
      try { plan = core.plan(caso.homologacion, caso.tipo_cambio); } catch (e) {
        assert.ok(e instanceof core.CuadroNoGenerable, `error inesperado: ${e.message}`);
        assert.equal(e.message, ref.error);
        return;
      }
      assert.equal(ref.error, undefined, `Python rechazó (${ref.error}) y JS no`);
      casi(plan, ref.plan, 'plan');
      const hoja = core.llenarHoja(ref.hoja_entrada, plan.celdas);
      assert.equal(hoja, ref.salida['xl/worksheets/sheet1.xml'], 'hoja');
      assert.equal(core.llenarLibro(ref.workbook_entrada), ref.salida['xl/workbook.xml'], 'workbook');
      assert.equal(core.llenarTipos(ref.tipos_entrada), ref.salida['[Content_Types].xml'], 'tipos');
      assert.equal(core.llenarRelaciones(ref.rels_entrada), ref.salida['xl/_rels/workbook.xml.rels'], 'relaciones');
    });
  }
}
