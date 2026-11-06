// --- Pegamento de n8n: arma la petición a Claude con las versiones finales de E3 (sin servicio aparte).
// El modelo se cambia aquí; el texto del sistema (método de homologación + esquema de respuesta) lo inserta el generador desde app/homologacion.
const MODELO = __MODELO__;
const SYSTEM_PROMPT = __SYSTEM_PROMPT__;
try {
  const preparado = prepare($input.first().json.paquete);
  return [{ json: { huella: preparado.huella, version_ids: preparado.version_ids, base: preparado.base.tipo, postores: preparado.postores.length,
    sin_final: preparado.sin_final, modelo: MODELO, cuerpo_claude: requestClaude(preparado, MODELO, SYSTEM_PROMPT) } }];
} catch (error) {
  return [{ json: { error: String(error.message).slice(0, 300) } }];
}
