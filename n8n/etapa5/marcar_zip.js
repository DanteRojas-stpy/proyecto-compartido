// Un .xlsx es un zip, pero el nodo «Descomprimir» solo abre archivos cuya extensión es zip: se le cambia la etiqueta.
const item = $input.first();
const binario = item.binary?.data;
if (!binario) throw new Error('No llegó la plantilla del cuadro.');
binario.fileName = 'plantilla.zip';
binario.fileExtension = 'zip';
binario.mimeType = 'application/zip';
return [item];
