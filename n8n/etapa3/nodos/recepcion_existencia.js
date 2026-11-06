// --- E3.1 · «Marcar existencia»: Storage respondió a la comprobación (HEAD) de cada archivo.
// 200 = ya está guardado; 404 = hay que subirlo; cualquier otra respuesta no permite decidir (fallo reintentable, como en el servicio).
return $input.all().map((item, indice) => {
  const estado = item.json.statusCode;
  return { json: { accion: estado === 200 ? 'existe' : estado === 404 ? 'subir' : 'no_decidible', estado_head: estado ?? null }, pairedItem: { item: indice } };
});
