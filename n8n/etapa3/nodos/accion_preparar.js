// --- E3.4/E3.5 · «Preparar decisión»: valida el origen, la sesión y la forma de la petición del frontend. La identidad real la verifica Nhost Auth.
const r = $json;
const origen = String(r.headers?.origin ?? '');
const origenes = ['http://127.0.0.1:8001', 'http://localhost:8001'];
if (origen && !origenes.includes(origen)) return [{ json: { ok: false, http_code: 403, mensaje: 'Origen de frontend no autorizado.' } }];
if (!/^Bearer\s+\S+$/i.test(String(r.headers?.authorization ?? ''))) return [{ json: { ok: false, http_code: 401, mensaje: 'Inicia sesión en Nhost.' } }];
if (!r.body || typeof r.body !== 'object' || Array.isArray(r.body)) return [{ json: { ok: false, http_code: 400, mensaje: 'Envía una decisión en JSON.' } }];
return [{ json: { ok: true, body: __CUERPO__, authorization: r.headers.authorization } }];
