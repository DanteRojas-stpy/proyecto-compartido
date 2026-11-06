// --- E3.2 · «Leer PDF»: el nodo «Extract From File» entregó el texto de cada página (sin OCR).
// Ese nodo reemplaza el JSON del ítem, así que el contexto (documento, versión, token) se recupera de «Detectar tipo».
return $input.all().map((item, i) => {
  const { meta, ...resto } = $('Detectar tipo').itemMatching(i).json;
  const base = { version_id: resto.version_id, token: resto.token, intento: resto.intento, orden: resto.orden, version: resto.version, modelo: resto.modelo, contexto: resto.contexto };
  try {
    if (item.json.error) throw new DocumentoInvalido('El PDF está dañado o no se pudo interpretar.');
    const { text } = item.json;
    return { json: { ...base, fuente: extraerPdf(Array.isArray(text) ? text : [String(text ?? '')], meta) }, pairedItem: { item: i } };
  } catch (error) {
    return { json: { ...base, error: { tipo: error.constructor.name, mensaje: String(error.message).slice(0, 2000), recuperable: !(error instanceof DocumentoInvalido) } }, pairedItem: { item: i } };
  }
});
