// --- E3.2 · «Preparar guardado de fuentes»: los fragmentos se guardan en grupos de 250 para respetar el límite de cuerpo.
const { fuentes, version_id, token } = $input.first().json;
const salida = [];
for (const fuente of fuentes) {
  for (let desde = 0; desde < fuente.fragmentos.length; desde += 250) {
    salida.push({ json: { version_id, token, documentos: [{ ...fuente, fragmentos: fuente.fragmentos.slice(desde, desde + 250) }] } });
  }
}
return salida;
