// --- E3.4 · «Entregar documento»: el original, en base64, para que el frontend lo muestre.
const permiso = $('Documento permitido').first().json;
const buffer = await this.helpers.getBinaryDataBuffer(0, 'data');
return [{ json: { ok: true, http_code: 200, nombre: permiso.nombre_original, mime_type: permiso.mime_type, contenido_base64: buffer.toString('base64') } }];
