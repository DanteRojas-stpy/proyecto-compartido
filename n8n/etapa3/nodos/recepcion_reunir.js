// --- E3.1 · «Reunir documentos»: junta los archivos ya guardados en Storage en una sola lista para registrarlos en la versión.
// Si alguno no se pudo confirmar no se registra nada parcial: queda un `fallo` reintentable.
const items = $input.all();
const primero = items[0].json;
const base = { contexto: primero.contexto, version_id: primero.version_id, token: primero.token };
const sin = items.find((i) => i.json.confirmado !== true);
if (sin) return [{ json: { ...base, fallo: { tipo: 'RuntimeError', mensaje: sin.json.motivo ?? 'Storage no confirmó el archivo guardado.', recuperable: true } } }];
return [{ json: { ...base, documentos: items.map((i) => i.json.meta) } }];
