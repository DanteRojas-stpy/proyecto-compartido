const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { prepararPdfs, idArchivoEstable, nombrePdf, comprobarExistencia, confirmarGuardado } = require('../app/recepcion/adjuntos.js');

const pdf = Buffer.from('%PDF-1.7\nContenido de prueba\n%%EOF');
const deteccion = (id = 'correo-1') => ({ estado_deteccion: 'detectado', gmail_message_id: id,
  gmail_thread_id: 'hilo-1', solicitud_id: 'solicitud-1', proveedor_id: 'proveedor-1',
  solicitud: 'SC-001', proveedor: 'Proveedor de prueba' });
const correo = binary => ({ json: { id: 'correo-1', threadId: 'hilo-1' }, binary });
const archivo = (fileName = 'Ficha tecnica.pdf', mimeType = 'application/pdf') => ({
  fileName, mimeType, data: pdf.toString('base64'),
});

test('prepara todos los PDF y conserva sus bytes, sin incluir imágenes ni Excel', async () => {
  const binary = { adjunto_0: archivo(), adjunto_1: archivo('Cotizacion.PDF', 'application/octet-stream'),
    adjunto_2: archivo('logo.png', 'image/png'), adjunto_3: archivo('comparativo.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') };
  const leidos = [];
  const salida = await prepararPdfs([correo(binary)], [deteccion()], async (i, clave) => { leidos.push(clave); return pdf; });
  assert.equal(salida.length, 2);
  assert.deepEqual(leidos, ['adjunto_0', 'adjunto_1']);
  for (const item of salida) {
    assert.deepEqual(Buffer.from(item.binary.pdf.data, 'base64'), pdf);
    assert.equal(item.json.storage_bucket, 'solicitudes');
    assert.equal(item.json.tamano_bytes, pdf.length);
    assert.equal(item.json.metadata_storage.metadata.proveedor_id, 'proveedor-1');
    assert.equal(item.json.metadata_storage.metadata.solicitud_id, 'solicitud-1');
    assert.equal(item.json.metadata_storage.metadata.gmail_message_id, 'correo-1');
  }
  assert.notEqual(salida[0].json.storage_file_id, salida[1].json.storage_file_id);
});

test('el mismo adjunto conserva ID al reintentar, pero otro correo o archivo tiene otro ID', async () => {
  const preparar = async (id, clave = 'adjunto_0') => {
    const item = correo({ [clave]: archivo('duplicado.pdf') });
    item.json.id = id;
    return (await prepararPdfs([item], [deteccion(id)], async () => pdf))[0].json.storage_file_id;
  };
  assert.equal(await preparar('correo-1'), await preparar('correo-1'));
  assert.notEqual(await preparar('correo-1'), await preparar('correo-2'));
  assert.notEqual(await preparar('correo-1'), await preparar('correo-1', 'adjunto_1'));
  assert.match(idArchivoEstable('ejemplo'), /^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});

test('una respuesta sin PDF queda visible y no produce una carga vacía', async () => {
  const salida = await prepararPdfs([correo({ foto: archivo('foto.jpg', 'image/jpeg') })], [deteccion()], async () => { throw new Error('No debe leer archivos no PDF'); });
  assert.equal(salida.length, 1);
  assert.equal(salida[0].json.estado_adjunto, 'sin_pdf');
  assert.equal(salida[0].binary, undefined);
});

test('rechaza archivos renombrados como PDF y no mezcla mensajes de proveedores', async () => {
  const item = correo({ adjunto_0: archivo() });
  const resultado = await prepararPdfs([item], [deteccion()], async () => Buffer.from('<html>No es un PDF</html>'));
  assert.equal(resultado[0].json.estado_adjunto, 'rechazado');
  assert.equal(resultado[0].binary, undefined);
  await assert.rejects(prepararPdfs([item], [deteccion('otro-correo')], async () => pdf), /no corresponde/);
});

test('los nombres no permiten rutas y un PDF sin extensión recibe .pdf', () => {
  assert.equal(nombrePdf('../../ficha\ntecnica.pdf').includes('/'), false);
  assert.equal(nombrePdf('Ficha técnica'), 'Ficha tecnica.pdf');
});

test('404 permite cargar, 200 omite duplicados y errores de acceso detienen el flujo', async () => {
  const adjunto = (await prepararPdfs([correo({ adjunto_0: archivo() })], [deteccion()], async () => pdf))[0];
  assert.equal(comprobarExistencia({ statusCode: 404 }, adjunto).json.ya_guardado, false);
  const existente = comprobarExistencia({ statusCode: 200, headers: { 'content-length': String(pdf.length), 'content-type': 'application/pdf', etag: 'archivo-existente' } }, adjunto);
  assert.equal(existente.json.estado_adjunto, 'ya_guardado');
  assert.deepEqual(existente.binary, adjunto.binary);
  for (const statusCode of [401, 403, 429, 500]) assert.throws(() => comprobarExistencia({ statusCode }, adjunto), /No se pudo comprobar/);
  assert.throws(() => comprobarExistencia({ statusCode: 200, headers: {} }, adjunto), /metadatos no coinciden/);
});

test('solo confirma una subida completa del archivo esperado en el bucket correcto', async () => {
  const adjunto = (await prepararPdfs([correo({ adjunto_0: archivo() })], [deteccion()], async () => pdf))[0].json;
  const respuesta = { processedFiles: [{ id: adjunto.storage_file_id, bucketId: 'solicitudes', isUploaded: true, size: pdf.length, name: adjunto.nombre_archivo }] };
  assert.equal(confirmarGuardado(respuesta, adjunto).estado_adjunto, 'guardado');
  for (const cambios of [{ id: 'otro' }, { bucketId: 'otro' }, { isUploaded: false }, { size: 0 }]) {
    assert.throws(() => confirmarGuardado({ processedFiles: [{ ...respuesta.processedFiles[0], ...cambios }] }, adjunto), /no corresponde/);
  }
  assert.throws(() => confirmarGuardado({ error: { message: 'sin espacio' }, processedFiles: [] }, adjunto), /no confirmó/);
});

test('el JSON ejecuta la preparación y recupera los binarios después de comprobar Storage', async () => {
  const flujo = JSON.parse(fs.readFileSync(path.join(__dirname, '../n8n/flujos/detectar-respuestas-proveedores.json'), 'utf8'));
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  const ejecutar = async (nombre, items, contexto, helpers = {}) => {
    const node = flujo.nodes.find(n => n.name === nombre);
    return new AsyncFunction('$input', '$', node.parameters.jsCode).call({ helpers },
      { all: () => items }, name => ({ itemMatching: index => contexto[name][index] }));
  };
  const preparados = await ejecutar('Preparar PDF del proveedor', [correo({ adjunto_0: archivo() })],
    { 'Respuesta de proveedor detectada': [{ json: deteccion() }] }, { getBinaryDataBuffer: async () => pdf });
  const pendientes = await ejecutar('Comprobar si ya está guardado', [{ json: { statusCode: 404 } }], { '¿Hay un PDF válido?': preparados });
  assert.equal(pendientes[0].binary.pdf.data, pdf.toString('base64'));
  const p = pendientes[0].json;
  const resultado = await ejecutar('PDF guardado y vinculado', [{ json: { processedFiles: [{
    id: p.storage_file_id, bucketId: 'solicitudes', isUploaded: true, size: pdf.length, name: p.nombre_archivo,
  }] } }], { '¿Se debe subir el PDF?': pendientes });
  assert.equal(resultado[0].json.estado_adjunto, 'guardado');
  assert.equal(resultado[0].json.proveedor_id, deteccion().proveedor_id);
  const subida = flujo.nodes.find(n => n.name === 'Guardar PDF en Nhost Storage');
  assert.equal(subida.parameters.contentType, 'multipart-form-data');
  assert.deepEqual(subida.parameters.bodyParameters.parameters.find(p => p.parameterType === 'formBinaryData'),
    { parameterType: 'formBinaryData', name: 'file[]', inputDataFieldName: 'pdf' });
  assert.equal(flujo.connections['¿Hay un PDF válido?'].main[1][0].node, 'Respuesta sin PDF o archivo rechazado');
  assert.equal(flujo.connections['¿Se debe subir el PDF?'].main[1][0].node, 'PDF ya guardado anteriormente');
});
