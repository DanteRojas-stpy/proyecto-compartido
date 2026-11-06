// --- E3.2 · «Documento no leído»: el archivo no se pudo descargar, no coincide con su huella o no es de un formato admitido.
return $input.all().map((item, i) => {
  const { meta, tipo, ...resto } = item.json;
  return { json: { version_id: resto.version_id, token: resto.token, intento: resto.intento, orden: resto.orden, version: resto.version, modelo: resto.modelo,
    contexto: resto.contexto, error: resto.error }, pairedItem: { item: i } };
});
