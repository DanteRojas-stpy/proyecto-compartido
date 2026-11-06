// --- E3.4/E3.5 · «Resultado de la decisión»: lo que respondió la Function e3-operar, o un aviso reintentable si no respondió.
const r = $input.first().json;
if (r.respuesta && typeof r.respuesta === 'object') return [{ json: r.respuesta }];
return [{ json: { ok: false, http_code: 503, mensaje: 'No se pudo verificar o registrar la decisión. Reintenta con el mismo accion_id.' } }];
