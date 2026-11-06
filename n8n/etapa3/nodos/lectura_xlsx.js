// --- E3.2 · «Leer Excel»: el nodo «Compression» entregó los archivos del libro sin su carpeta; se recuperan de la lista de rutas del zip original.
const salida = [];
const items = $input.all();
for (let i = 0; i < items.length; i++) {
  const { meta, ...resto } = items[i].json;
  const base = { version_id: resto.version_id, token: resto.token, intento: resto.intento, orden: resto.orden, version: resto.version, modelo: resto.modelo, contexto: resto.contexto };
  try {
    const original = await this.helpers.getBinaryDataBuffer(i, $('Marcar xlsx como zip').itemMatching(i).binary.data);
    const porRuta = archivosDelXlsx(original, items[i].binary);
    const archivos = {};
    for (const [ruta, propiedad] of Object.entries(porRuta)) archivos[ruta] = await this.helpers.getBinaryDataBuffer(i, propiedad);
    salida.push({ json: { ...base, fuente: extraerXlsx(archivos, meta) }, pairedItem: { item: i } });
  } catch (error) {
    salida.push({ json: { ...base, error: { tipo: error.constructor.name, mensaje: String(error.message).slice(0, 2000), recuperable: !(error instanceof DocumentoInvalido) } }, pairedItem: { item: i } });
  }
}
return salida;
