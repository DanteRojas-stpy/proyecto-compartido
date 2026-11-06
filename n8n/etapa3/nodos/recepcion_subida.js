// --- E3.1 · «Confirmar subida»: Storage responde con los archivos creados; el identificador debe ser el estable que se pidió.
// Si no lo confirma (por ejemplo, otro correo guardó el mismo archivo a la vez), el archivo queda sin confirmar y el intento se
// reintenta: en el siguiente la comprobación lo encontrará.
return $input.all().map((item, indice) => {
  const contexto = $('Merge de existencia').itemMatching(indice).json;
  const guardado = (item.json.processedFiles ?? []).some((x) => x.id === contexto.meta.storage_file_id);
  return { json: { ...contexto, confirmado: guardado, motivo: guardado ? null : 'Storage no confirmó el archivo guardado.' }, pairedItem: { item: indice } };
});
