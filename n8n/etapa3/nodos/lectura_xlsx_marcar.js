// --- E3.2 · «Marcar xlsx como zip»: un .xlsx es un zip, pero el nodo «Compression» solo abre archivos cuya extensión es zip.
return $input.all().map((item, i) => {
  const binario = item.binary?.data;
  if (binario) { binario.fileName = 'documento.zip'; binario.fileExtension = 'zip'; binario.mimeType = 'application/zip'; }
  return { json: item.json, binary: item.binary, pairedItem: { item: i } };
});
