// --- E3.2 · «Documentos por leer»: de la versión iniciada, arma un ítem por documento registrado (en su orden).
// Si la versión no tiene documentos es un fallo no reintentable (igual que el servicio).
const contexto = $('Iniciar lectura').first().json.respuesta;
const instantanea = $('Obtener versión').first().json.respuesta;
const configuracion = $input.first().json.respuesta;
const base = { version_id: contexto.version_id, token: contexto.token, intento: contexto.intento };
const documentos = instantanea.documentos ?? [];
if (!documentos.length) return [{ json: { ...base, fallo: { tipo: 'DocumentoInvalido', mensaje: 'La versión no tiene documentos registrados.', recuperable: false } } }];
return documentos.map((d, orden) => ({ json: { ...base, orden, documento: { id: d.id, storage_file_id: d.storage_file_id, nombre_original: d.nombre_original,
  mime_type: d.mime_type, sha256: d.sha256, nombres_originales: d.e3_detalle?.nombres_originales ?? [d.nombre_original] },
  version: instantanea.version, modelo: configuracion.modelo, contexto: configuracion.parametros?.contexto_caracteres ?? 24000 } }));
