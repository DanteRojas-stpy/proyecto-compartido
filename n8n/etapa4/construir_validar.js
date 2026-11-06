// --- Pegamento de n8n: valida la respuesta de Claude contra la entrada y construye homologacion.json (sin servicio aparte).
// Un error de formato o una cita inexistente no se corrige: se rechaza y el flujo lo reintenta.
const MODELO = __MODELO__;
const ESQUEMA = __ESQUEMA__;
const entrada = $input.first().json;
try {
  const preparado = prepare(entrada.paquete);
  const homologacion = build(preparado, parseTexto(entrada.texto, ESQUEMA), entrada.modelo ?? MODELO, ESQUEMA);
  return [{ json: { resultado: 'construida', homologacion, estado_revision: homologacion.estado_revision, huella: preparado.huella,
    version_ids: preparado.version_ids } }];
} catch (error) {
  const errores = error instanceof HomologacionInvalida ? error.errores : [String(error.message).slice(0, 300)];
  return [{ json: { resultado: 'respuesta_invalida', errores } }];
}
