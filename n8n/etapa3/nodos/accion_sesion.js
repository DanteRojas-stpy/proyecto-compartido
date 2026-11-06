// --- E3.4/E3.5 · «Evaluar sesión»: Nhost Auth respondió por el token del especialista. La identidad del cuerpo nunca se usa para autorizar ni auditar.
const preparado = $('Preparar decisión').first().json;
const respuesta = $input.first().json;
const rechazo = (codigo, mensaje) => [{ json: { ok: false, http_code: codigo, mensaje } }];
if (respuesta.statusCode !== 200) {
  return rechazo([400, 401, 403].includes(respuesta.statusCode) ? 401 : 503, 'La sesión venció o no pudo verificarse. Vuelve a ingresar.');
}
const usuario = respuesta.body ?? {};
if (usuario.isAnonymous || ![...(usuario.roles ?? []), usuario.defaultRole].includes('user')) return rechazo(403, 'La cuenta no tiene el rol requerido.');
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const { usuario_id, accessToken, refreshToken, ...datos } = preparado.body;
if (!uuid.test(String(usuario.id)) || (datos.accion === 'ver_documento' && !uuid.test(String(datos.documento_id)))) {
  return rechazo(400, 'La petición contiene un identificador o dato inválido.');
}
return [{ json: { ok: true, usuario_id: String(usuario.id).toLowerCase(), accion: datos.accion, datos } }];
