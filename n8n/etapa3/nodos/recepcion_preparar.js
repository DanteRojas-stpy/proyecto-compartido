// --- E3.1 · «Preparar documentos»: huella y deduplicación de los adjuntos del correo (antes lo hacía el servicio en /receive).
// Entrada: el resultado de recepción (contexto de la versión) y el correo recuperado de Gmail, con sus adjuntos como binarios.
// Salida: un ítem por archivo distinto (con su binario), o un solo ítem con `fallo` si Gmail no entregó nada utilizable.
const salida = [];
const items = $input.all();
for (let indice = 0; indice < items.length; indice++) {
  const item = items[indice];
  const contexto = $('Resultado de recepción').itemMatching(indice).json;
  const base = { contexto, version_id: contexto.version_id, token: contexto.token };
  const fallo = (tipo, mensaje, recuperable) => salida.push({ json: { ...base, fallo: { tipo, mensaje: String(mensaje).slice(0, 2000), recuperable } }, pairedItem: { item: indice } });
  if (item.json.error) { fallo('RuntimeError', 'Gmail no entregó el mensaje y sus adjuntos: ' + String(item.json.error).slice(0, 1000), true); continue; }
  const claves = Object.keys(item.binary ?? {});
  if (!claves.length) { fallo('RuntimeError', 'Gmail no devolvió adjuntos descargables.', true); continue; }
  const unicos = new Map();
  try {
    for (const clave of claves) {
      const b = item.binary[clave];
      const buffer = await this.helpers.getBinaryDataBuffer(indice, clave);
      const meta = describe(buffer, b.fileName ?? clave, b.mimeType ?? 'application/octet-stream', contexto.version_id);
      if (unicos.has(meta.sha256)) { unicos.get(meta.sha256).meta.nombres_originales.push(meta.nombre_original); continue; }
      meta.nombres_originales = [meta.nombre_original];
      unicos.set(meta.sha256, { meta, binario: b });
    }
  } catch (error) {
    fallo(error.constructor.name, error.message, !(error instanceof DocumentoInvalido));
    continue;
  }
  for (const { meta, binario } of unicos.values()) salida.push({ json: { ...base, meta }, binary: { data: binario }, pairedItem: { item: indice } });
}
return salida;
