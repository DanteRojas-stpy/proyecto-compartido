// Ejecuta el código del nodo «Llenar plantilla» con un n8n simulado: el nodo «Descomprimir» entrega los archivos sin carpeta
// y prepareBinaryData también recorta la ruta, igual que en n8n 2.x (comprobado en una instancia real).
const fs = require('node:fs');
const entrada = JSON.parse(fs.readFileSync(0, 'utf8'));
const almacen = new Map();
let contador = 0;
const crear = (buffer, nombre) => {
  const id = `b${contador++}`;
  almacen.set(id, buffer);
  return { data: id, fileName: nombre, mimeType: 'application/xml' };
};
const binario = {};
entrada.archivos.forEach((a, i) => { binario[`p_${i}`] = crear(Buffer.from(a.b64, 'base64'), a.nombre); });
const original = crear(Buffer.from(entrada.original_b64, 'base64'), 'plantilla.zip');
const ayudas = {
  getBinaryDataBuffer: async (indice, propiedad) => {
    const meta = typeof propiedad === 'string' ? binario[propiedad] : propiedad;
    return almacen.get(meta.data);
  },
  prepareBinaryData: async (buffer, nombre, mime) => ({ ...crear(buffer, nombre.split('/').pop()), mimeType: mime }),
};
const $ = (nodo) => ({ first: () => (nodo === 'Marcar plantilla como zip' ? { json: {}, binary: { data: original } } : { json: entrada.ctx }) });
const $input = { first: () => ({ json: {}, binary: binario }) };
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const f = new AsyncFunction('$', '$input', entrada.codigo);
f.call({ helpers: ayudas }, $, $input).then((r) => {
  const salida = { json: r[0].json, binary: {} };
  for (const [k, v] of Object.entries(r[0].binary ?? {})) salida.binary[k] = { fileName: v.fileName, b64: almacen.get(v.data).toString('base64') };
  process.stdout.write(JSON.stringify(salida));
});
