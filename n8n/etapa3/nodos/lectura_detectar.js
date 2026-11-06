// --- E3.2 · «Detectar tipo»: huella del archivo descargado y clase de documento (PDF, XLSX, CSV o no admitido).
// La huella debe coincidir con la registrada al recibir el correo.
const salida = [];
const items = $input.all();
for (let i = 0; i < items.length; i++) {
  const ctx = $('Documentos por leer').itemMatching(i).json;
  const base = { version_id: ctx.version_id, token: ctx.token, intento: ctx.intento, orden: ctx.orden, version: ctx.version, modelo: ctx.modelo, contexto: ctx.contexto };
  try {
    const buffer = await this.helpers.getBinaryDataBuffer(i, 'data');
    const meta = describe(buffer, ctx.documento.nombre_original, ctx.documento.mime_type, ctx.version_id);
    // Mantiene el documento ya registrado, incluso al releer.
    meta.documento_id = ctx.documento.id;
    meta.storage_file_id = ctx.documento.storage_file_id;
    meta.nombres_originales = ctx.documento.nombres_originales;
    if (ctx.documento.sha256 && ctx.documento.sha256 !== meta.sha256) throw new DocumentoInvalido('La huella del archivo cambió desde su recepción.');
    const nombre = ctx.documento.nombre_original.toLowerCase();
    const tipo = buffer.subarray(0, 4).toString('latin1') === '%PDF' ? 'pdf' : nombre.endsWith('.xlsx') ? 'xlsx' : nombre.endsWith('.csv') ? 'csv' : null;
    if (!tipo) throw new DocumentoInvalido('Formato no admitido en esta versión. Se admiten PDF con texto, XLSX y CSV.');
    salida.push({ json: { ...base, meta, tipo }, binary: items[i].binary, pairedItem: { item: i } });
  } catch (error) {
    salida.push({ json: { ...base, tipo: 'error', error: { tipo: error.constructor.name, mensaje: String(error.message).slice(0, 2000), recuperable: !(error instanceof DocumentoInvalido) } }, pairedItem: { item: i } });
  }
}
return salida;
