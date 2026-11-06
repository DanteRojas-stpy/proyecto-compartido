// --- E3.2 · «Interpretar Claude»: lee la respuesta de cada tanda y la valida contra el esquema. Un error aquí es reintentable.
const ESQUEMA = __ESQUEMA__;
return $input.all().map((item, i) => {
  const tanda = $('Armar tandas').itemMatching(i).json;
  const base = { version_id: tanda.version_id, token: tanda.token, indice: tanda.indice };
  try {
    return { json: { ...base, respuesta: parseRespuesta(item.json, ESQUEMA) }, pairedItem: { item: i } };
  } catch (error) {
    return { json: { ...base, error: { tipo: error.constructor.name, mensaje: String(error.message).slice(0, 2000), recuperable: true } }, pairedItem: { item: i } };
  }
});
