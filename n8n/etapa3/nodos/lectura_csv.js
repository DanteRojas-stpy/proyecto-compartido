// --- E3.2 · «Leer CSV»
const salida = [];
const items = $input.all();
for (let i = 0; i < items.length; i++) {
  const { meta, ...resto } = items[i].json;
  const base = { version_id: resto.version_id, token: resto.token, intento: resto.intento, orden: resto.orden, version: resto.version, modelo: resto.modelo, contexto: resto.contexto };
  try {
    const buffer = await this.helpers.getBinaryDataBuffer(i, 'data');
    salida.push({ json: { ...base, fuente: extraerCsv(buffer, meta) }, pairedItem: { item: i } });
  } catch (error) {
    salida.push({ json: { ...base, error: { tipo: error.constructor.name, mensaje: String(error.message).slice(0, 2000), recuperable: !(error instanceof DocumentoInvalido) } }, pairedItem: { item: i } });
  }
}
return salida;
