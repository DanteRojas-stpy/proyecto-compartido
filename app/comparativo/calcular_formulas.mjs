import fs from 'node:fs/promises';
import { Workbook } from '@oai/artifact-tool';
// Calcula en un libro auxiliar; la plantilla se conserva con el parche OOXML.
const [entrada, salida] = process.argv.slice(2);
const plan = JSON.parse(await fs.readFile(entrada, 'utf8'));
const libro = Workbook.create();
const hoja = libro.worksheets.add('PLANTILLA');
for (const [celda, dato] of Object.entries(plan.celdas)) {
  if (dato.formula) hoja.getRange(celda).formulas = [[`=${dato.formula}`]];
  else {
    const v=dato.valor;
    hoja.getRange(celda).values = [[typeof v==='string'&&v.startsWith('=') ? `'${v}` : v??null]];
  }
}
libro.recalculate();
const valores = {};
for (const [celda, dato] of Object.entries(plan.celdas)) {
  if (!dato.formula) continue;
  const valor = hoja.getRange(celda).values[0][0];
  if (typeof valor === 'string' && /^#(?:REF!|VALUE!|DIV\/0!|NAME\?|N\/A|NUM!|NULL!)/.test(valor))
    throw new Error(`Error de cálculo en ${celda}: ${valor}`);
  valores[celda] = valor ?? '';
}
await fs.writeFile(salida, JSON.stringify(valores), 'utf8');
