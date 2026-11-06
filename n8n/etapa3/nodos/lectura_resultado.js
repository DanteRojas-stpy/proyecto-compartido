// --- E3.2 · «Validar lectura»: validación independiente. Toda cita debe existir literalmente en su fragmento y los importes deben
// coincidir con su texto original; la aritmética se verifica sin rellenar importes que no estén escritos.
const ESQUEMA = __ESQUEMA__;
const items = $input.all();
const lectura = $('Reunir fuentes').first().json;
const base = { version_id: lectura.version_id, token: lectura.token };
const conError = items.filter((i) => i.json.error);
if (conError.length) return [{ json: { ...base, fallo: conError[0].json.error } }];
try {
  const respuestas = items.slice().sort((a, b) => a.json.indice - b.json.indice).map((i) => i.json.respuesta);
  return [{ json: { ...base, resultado: combine(respuestas, lectura.fuentes, lectura.version, lectura.modelo, ESQUEMA) } }];
} catch (error) {
  return [{ json: { ...base, fallo: { tipo: error.constructor.name, mensaje: String(error.message).slice(0, 2000), recuperable: !(error instanceof DocumentoInvalido) } } }];
}
