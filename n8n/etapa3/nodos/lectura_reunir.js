// --- E3.2 · «Reunir fuentes»: junta la lectura de todos los documentos. Cualquier documento ilegible detiene la lectura de la versión:
// nunca se guarda una lectura parcial.
const items = $input.all();
const primero = items[0].json;
const base = { version_id: primero.version_id, token: primero.token, intento: primero.intento, version: primero.version, modelo: primero.modelo, contexto: primero.contexto };
const conError = items.filter((i) => i.json.error).sort((a, b) => a.json.orden - b.json.orden);
if (conError.length) return [{ json: { ...base, fallo: conError[0].json.error } }];
return [{ json: { ...base, fuentes: items.slice().sort((a, b) => a.json.orden - b.json.orden).map((i) => i.json.fuente) } }];
