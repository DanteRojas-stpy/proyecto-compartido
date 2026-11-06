// --- E3.2 · «Armar tandas»: comprueba que se guardaron las fuentes y arma una petición a Claude por tanda de contexto.
// El máximo por tanda se reduce a la mitad en cada reintento (como en el servicio).
const SISTEMA = __SISTEMA__;
const ESQUEMA = __ESQUEMA__;
const lectura = $('Reunir fuentes').first().json;
const base = { version_id: lectura.version_id, token: lectura.token };
try {
  if ($input.all().some((i) => i.json.respuesta?.resultado !== 'fuentes_guardadas')) {
    throw new Error('Nhost no guardó los fragmentos: ' + JSON.stringify($input.first().json).slice(0, 300));
  }
  const maximo = Math.floor(lectura.contexto / 2 ** (lectura.intento - 1));
  return tandas(lectura.fuentes, maximo).map((lote, indice) => ({ json: { ...base, indice, cuerpo: requestClaude(lote, lectura.fuentes, lectura.modelo, SISTEMA, ESQUEMA) } }));
} catch (error) {
  return [{ json: { ...base, fallo: { tipo: error.constructor.name, mensaje: String(error.message).slice(0, 2000), recuperable: !(error instanceof DocumentoInvalido) } } }];
}
