// --- Pegamento de n8n: usa las funciones de cuadro_core.js sobre los archivos que dejó el nodo «Descomprimir plantilla».
// Cada archivo del .xlsx llega como un binario cuyo nombre (fileName) es su ruta dentro del zip.
const ctx = $('Comprobar entrada').first().json;
const entrada = ctx.entrada;
const base = { cuadro_id: ctx.cuadro_id, token: ctx.token, codigo: entrada.solicitud?.codigo ?? 'solicitud', revision: entrada.revision };
const item = $input.first();
const binarios = item.binary ?? {};
const clave = {};
const MIME_XML = 'application/xml';
try {
  // El nodo «Descomprimir» pierde las carpetas: se recuperan de la lista de rutas del zip original (mismo orden).
  const original = await this.helpers.getBinaryDataBuffer(0, $('Marcar plantilla como zip').first().binary.data);
  const rutas = nombresDelZip(original);
  const propiedades = Object.keys(binarios);
  if (rutas.length !== propiedades.length) throw new CuadroNoGenerable('El archivo no parece la plantilla del cuadro comparativo.');
  propiedades.forEach((propiedad, i) => {
    if (rutas[i].split('/').pop() !== binarios[propiedad].fileName) throw new CuadroNoGenerable('El .xlsx se abrió en otro orden del esperado.');
    binarios[propiedad].fileName = rutas[i];
    clave[rutas[i]] = propiedad;
  });
  if (!clave[HOJA]) throw new CuadroNoGenerable('El archivo no parece la plantilla del cuadro comparativo.');
  const resultado = plan(entrada.homologacion, entrada.tipo_cambio ?? null);
  const leer = async (ruta) => (await this.helpers.getBinaryDataBuffer(0, clave[ruta])).toString('utf8');
  const escribir = async (ruta, texto) => {
    const nuevo = await this.helpers.prepareBinaryData(Buffer.from(texto, 'utf8'), ruta, MIME_XML);
    nuevo.fileName = ruta; // prepareBinaryData recorta la carpeta; sin ella el zip quedaría plano
    binarios[clave[ruta]] = nuevo;
  };
  await escribir(HOJA, llenarHoja(await leer(HOJA), resultado.celdas));
  for (const [ruta, cambiar] of [['xl/workbook.xml', llenarLibro], ['[Content_Types].xml', llenarTipos], ['xl/_rels/workbook.xml.rels', llenarRelaciones]]) {
    if (clave[ruta]) await escribir(ruta, cambiar(await leer(ruta)));
  }
  if (clave['xl/calcChain.xml']) delete binarios[clave['xl/calcChain.xml']]; // Excel lo reconstruye al recalcular
  const { celdas, ...validacion } = resultado;
  validacion.celdas_escritas = Object.keys(celdas).length;
  // El nodo «Comprimir cuadro» recibe aquí la lista de archivos que debe volver a empaquetar.
  return [{ json: { ...base, ok: true, validacion, propiedades: Object.keys(binarios).join(',') }, binary: binarios }];
} catch (error) {
  if (error instanceof CuadroNoGenerable) {
    // Un cuadro imposible de armar no se reintenta: reintentar no lo arregla.
    return [{ json: { ...base, ok: false, recuperable: false, error: String(error.message).slice(0, 600) } }];
  }
  throw error;
}
