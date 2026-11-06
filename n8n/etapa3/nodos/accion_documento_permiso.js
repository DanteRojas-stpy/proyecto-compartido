// --- E3.4 · «Documento permitido»: ¿la cuenta puede ver este documento?
const r = $input.first().json.respuesta;
if (!r || !r.storage_file_id) return [{ json: { ok: false, http_code: 404, mensaje: 'Documento no disponible para esta cuenta.' } }];
return [{ json: { ok: true, storage_file_id: r.storage_file_id, nombre_original: r.nombre_original, mime_type: r.mime_type } }];
