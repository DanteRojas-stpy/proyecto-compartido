/* Preparación de PDF para Nhost. El contenido binario permanece en n8n. */
function idArchivoEstable(texto) {
  // FNV-1a de 128 bits: identidad reproducible, no se usa como secreto.
  let hash = 0x6c62272e07bb014262b821756295c58dn;
  for (let i = 0; i < texto.length; i++) {
    hash ^= BigInt(texto.charCodeAt(i));
    hash = BigInt.asUintN(128, hash * 0x0000000001000000000000000000013bn);
  }
  const h = hash.toString(16).padStart(32, '0');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-8${h.slice(13, 16)}-${((parseInt(h[16], 16) & 3) | 8).toString(16)}${h.slice(17, 20)}-${h.slice(20)}`;
}

function nombrePdf(nombre) {
  let limpio = String(nombre ?? 'adjunto.pdf').normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '').replace(/[\\/\u0000-\u001f\u007f]/g, '_')
    .replace(/[^a-zA-Z0-9._ -]/g, '_').replace(/^\.+/, '').trim();
  limpio = limpio.slice(0, 170) || 'adjunto';
  return /\.pdf$/i.test(limpio) ? limpio : limpio + '.pdf';
}

async function prepararPdfs(items, detecciones, leerBinario) {
  const salida = [];
  for (const [index, item] of items.entries()) {
    const deteccion = detecciones[index];
    if (!deteccion || deteccion.estado_deteccion !== 'detectado'
      || item.json.id !== deteccion.gmail_message_id
      || item.json.threadId !== deteccion.gmail_thread_id) {
      throw new Error('El adjunto no corresponde a la respuesta identificada.');
    }
    let encontrados = 0;
    for (const [clave, archivo] of Object.entries(item.binary ?? {})) {
      const mime = String(archivo.mimeType ?? '').split(';')[0].trim().toLowerCase();
      if (mime !== 'application/pdf' && !/\.pdf$/i.test(archivo.fileName ?? '')) continue;
      encontrados++;
      const buffer = await leerBinario(index, clave);
      const cabecera = String.fromCharCode(...buffer.subarray(0, 1024));
      const nombreOriginal = archivo.fileName || 'adjunto.pdf';
      if (!/^(?:\xEF\xBB\xBF)?\s*%PDF-/.test(cabecera)) {
        salida.push({ json: { ...deteccion, estado_adjunto: 'rechazado',
          nombre_original: nombreOriginal, motivo: 'El archivo anunciado como PDF no tiene cabecera PDF.' },
          pairedItem: { item: index } });
        continue;
      }
      const id = idArchivoEstable(JSON.stringify([
        'costflow-pdf-v1', 'cotizaciones', deteccion.solicitud_id, deteccion.proveedor_id,
        deteccion.gmail_message_id, clave, nombreOriginal,
      ]));
      const nombre = nombrePdf(`${deteccion.solicitud ?? 'solicitud'}-${deteccion.proveedor ?? 'proveedor'}-${nombreOriginal}`);
      const metadata = {
        solicitud_id: deteccion.solicitud_id, proveedor_id: deteccion.proveedor_id,
        gmail_message_id: deteccion.gmail_message_id,
        gmail_thread_id: deteccion.gmail_thread_id, adjunto_gmail: clave,
        nombre_original: nombreOriginal, origen: 'gmail', tipo: 'adjunto_pdf_proveedor',
      };
      salida.push({ json: { ...deteccion, estado_adjunto: 'pendiente',
        storage_file_id: id, storage_bucket: 'cotizaciones', nombre_original: nombreOriginal,
        nombre_archivo: nombre, tamano_bytes: buffer.length,
        metadata_storage: { id, name: nombre, metadata },
      }, binary: { pdf: { ...archivo, fileName: nombre, mimeType: 'application/pdf' } },
      pairedItem: { item: index } });
    }
    if (!encontrados) salida.push({ json: { ...deteccion, estado_adjunto: 'sin_pdf',
      motivo: 'La respuesta no contiene PDF adjuntos.' }, pairedItem: { item: index } });
  }
  return salida;
}

function comprobarExistencia(respuesta, adjunto) {
  const estado = Number(respuesta.statusCode);
  if (estado !== 200 && estado !== 404) {
    throw new Error(`No se pudo comprobar el PDF en Nhost Storage (HTTP ${estado || 'desconocido'}).`);
  }
  if (estado === 200) {
    const headers = Object.fromEntries(Object.entries(respuesta.headers ?? {}).map(([key, value]) => [key.toLowerCase(), value]));
    if (Number(headers['content-length']) !== adjunto.json.tamano_bytes
      || String(headers['content-type']).split(';')[0].trim().toLowerCase() !== 'application/pdf'
      || !headers.etag) {
      throw new Error('Nhost tiene un archivo con ese identificador, pero sus metadatos no coinciden con el PDF.');
    }
  }
  return { json: { ...adjunto.json, ya_guardado: estado === 200,
    estado_adjunto: estado === 200 ? 'ya_guardado' : 'pendiente' },
    binary: adjunto.binary };
}

function confirmarGuardado(respuesta, adjunto) {
  const archivos = respuesta.processedFiles;
  if (respuesta.error || !Array.isArray(archivos) || archivos.length !== 1) {
    throw new Error('Nhost Storage no confirmó la carga del PDF.');
  }
  const archivo = archivos[0];
  if (archivo.id !== adjunto.storage_file_id || archivo.bucketId !== 'cotizaciones'
      || archivo.isUploaded !== true || Number(archivo.size) !== adjunto.tamano_bytes) {
    throw new Error('La confirmación de Nhost no corresponde al PDF enviado.');
  }
  return { ...adjunto, estado_adjunto: 'guardado', ya_guardado: false,
    nombre_archivo: archivo.name };
}

module.exports = { idArchivoEstable, nombrePdf, prepararPdfs, comprobarExistencia, confirmarGuardado };
