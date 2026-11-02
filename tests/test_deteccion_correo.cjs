const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const reglas = require('../app/correo/deteccion.js');

const mensaje = (id = 'respuesta-1', threadId = 'hilo-1', from = 'Proveedor <ventas@example.test>') => ({
  id, threadId, From: from, Subject: 'Re: cotización actualizada',
  labelIds: ['INBOX'], internalDate: String(Date.parse('2026-10-25T18:00:00Z')),
});
const envio = (id = 'envio-1', solicitud = 'solicitud-1') => ({
  id, solicitud_id: solicitud, proveedor_id: 'proveedor-1', estado: 'enviado',
  destinatario: 'VENTAS@example.test', mensaje_id: 'original-' + id,
});
const original = (e, hilo = 'hilo-1') => ({
  id: e.mensaje_id, threadId: hilo, labelIds: ['SENT'],
  internalDate: String(Date.parse('2026-10-25T17:00:00Z')),
});

test('normaliza el remitente y acepta mensajes leídos, conservando los dos IDs', () => {
  const m = reglas.normalizarCorreo(mensaje());
  assert.equal(m.remitente, 'ventas@example.test');
  assert.equal(m.gmail_message_id, 'respuesta-1');
  assert.equal(m.gmail_thread_id, 'hilo-1');
  assert.equal(m.fecha_recepcion, '2026-10-25T18:00:00.000Z');
});

test('acepta las cabeceras sin simplificar y el formato de mailparser', () => {
  const m = mensaje();
  delete m.From;
  m.payload = { headers: [{ name: 'From', value: 'ventas@example.test' }] };
  assert.equal(reglas.normalizarCorreo(m).remitente, 'ventas@example.test');
  m.from = { value: [{ address: 'Ventas@example.test' }] };
  assert.equal(reglas.normalizarCorreo(m).remitente, 'ventas@example.test');
  m.from.value.push({ address: 'otro@example.test' });
  assert.equal(reglas.normalizarCorreo(m), null);
});

test('ignora enviados, borradores, spam, papelera y correos incompletos', () => {
  for (const label of ['SENT', 'DRAFT', 'SPAM', 'TRASH']) {
    assert.equal(reglas.normalizarCorreo({ ...mensaje(), labelIds: [label] }), null);
  }
  assert.equal(reglas.normalizarCorreo({ ...mensaje(), threadId: '' }), null);
  assert.equal(reglas.normalizarCorreo({ ...mensaje(), From: 'correo inválido' }), null);
});

test('escapa comodines de SQL y exige el destinatario exacto del envío', () => {
  assert.equal(reglas.patronCorreo('a_b%z@example.test'), 'a\\_b\\%z@example.test');
  const e = envio();
  const respuesta = { data: { envios_solicitud: [e, e, { ...e, id: 'otro', destinatario: 'otro@example.test' }, { ...e, id: 'pendiente', estado: 'pendiente' }] } };
  assert.deepEqual(reglas.prepararCandidatos(respuesta, reglas.normalizarCorreo(mensaje())).map(c => c.envio.id), ['envio-1']);
});

test('un error de Nhost detiene la detección y no parece una lista vacía', () => {
  assert.throws(() => reglas.prepararCandidatos({ errors: [{ message: 'sin permiso' }] }, {}), /sin permiso/);
  assert.throws(() => reglas.prepararCandidatos({ data: {} }, {}), /lista de envíos/);
});

test('distingue dos solicitudes del mismo proveedor aunque tengan el mismo asunto', () => {
  const correo = reglas.normalizarCorreo(mensaje());
  const a = envio('a', 'solicitud-a');
  const b = envio('b', 'solicitud-b');
  const salida = reglas.identificarRespuestas([
    { correo, envio: a, original: original(a, 'otro-hilo') },
    { correo, envio: b, original: original(b) },
  ]);
  assert.equal(salida.length, 1);
  assert.equal(salida[0].estado_deteccion, 'detectado');
  assert.equal(salida[0].solicitud_id, 'solicitud-b');
});

test('no asigna solicitudes por asunto, ni elige entre conversaciones ambiguas', () => {
  const correo = reglas.normalizarCorreo(mensaje());
  const a = envio('a');
  const b = envio('b', 'solicitud-2');
  assert.equal(reglas.identificarRespuestas([{ correo, envio: a, original: original(a, 'otro') }])[0].estado_deteccion, 'revisar');
  const ambiguo = reglas.identificarRespuestas([
    { correo, envio: a, original: original(a) }, { correo, envio: b, original: original(b) },
  ])[0];
  assert.equal(ambiguo.estado_deteccion, 'revisar');
  assert.equal(ambiguo.solicitud_id, undefined);
});

test('un envío borrado se revisa, pero no impide reconocer otro envío válido', () => {
  const correo = reglas.normalizarCorreo(mensaje());
  const a = envio('a');
  const b = envio('b');
  assert.equal(reglas.identificarRespuestas([{ correo, envio: a, original: { error: '404' } }])[0].estado_deteccion, 'revisar');
  assert.equal(reglas.identificarRespuestas([
    { correo, envio: a, original: { error: '404' } }, { correo, envio: b, original: original(b) },
  ])[0].envio_id, 'b');
});

test('no confunde un correo anterior al envío ni un mensaje que no fue enviado', () => {
  const correo = reglas.normalizarCorreo(mensaje());
  const e = envio();
  for (const o of [{ ...original(e), labelIds: ['INBOX'] }, { ...original(e), internalDate: String(Date.parse('2026-10-26T18:00:00Z')) }]) {
    assert.equal(reglas.identificarRespuestas([{ correo, envio: e, original: o }])[0].estado_deteccion, 'revisar');
  }
});

test('flujo exportado: procesa varios correos conservando su solicitud y proveedor', () => {
  const flujo = JSON.parse(fs.readFileSync(path.join(__dirname, '../n8n/flujos/detectar-respuestas-proveedores.json'), 'utf8'));
  const ejecutar = (nombre, items, contexto = {}) => {
    const node = flujo.nodes.find(n => n.name === nombre);
    return new Function('$input', '$', node.parameters.jsCode)(
      { all: () => items }, name => ({ itemMatching: index => contexto[name][index] }),
    );
  };
  const normalizados = ejecutar('Normalizar correo', [{ json: mensaje('r1', 'h1') }, { json: mensaje('r2', 'h2') }]);
  const e1 = envio('a', 's1'), e2 = envio('b', 's2');
  const respuestasNhost = normalizados.map(() => ({ json: { data: { envios_solicitud: [e1, e2] } } }));
  const candidatos = ejecutar('Preparar candidatos', respuestasNhost, { 'Normalizar correo': normalizados });
  assert.equal(candidatos.length, 4);
  const originales = candidatos.map(c => ({ json: original(c.json.envio, c.json.envio.id === 'a' ? 'h1' : 'h2') }));
  const detectados = ejecutar('Identificar respuestas', originales, { 'Preparar candidatos': candidatos });
  assert.deepEqual(detectados.map(item => [item.json.gmail_message_id, item.json.solicitud_id]), [['r1', 's1'], ['r2', 's2']]);
  const detalles = detectados.map((item, index) => ({ json: { data: {
    solicitudes_cotizacion_by_pk: { codigo: 'SC-00' + index, nombre: 'Ascensor', estado: 'en_proceso', proyecto_asociado: { nombre: 'Proyecto' } },
    proveedores_by_pk: { nombre: 'Proveedor de prueba' },
  } } }));
  const salida = ejecutar('Respuesta de proveedor detectada', detalles, { '¿Solicitud identificada?': detectados });
  assert.equal(salida[0].json.proveedor, 'Proveedor de prueba');
  assert.equal(salida[1].json.solicitud_id, 's2');
  const trigger = flujo.nodes.find(n => n.type === 'n8n-nodes-base.gmailTrigger');
  assert.equal(trigger.parameters.filters.readStatus, 'both');
  assert.equal(flujo.active, false);
  assert.equal(flujo.nodes.filter(n => n.type === 'n8n-nodes-base.gmail').every(n => n.parameters.operation === 'get'), true);
});
