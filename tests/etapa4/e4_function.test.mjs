import assert from 'node:assert/strict';
import { test, beforeEach, afterEach } from 'node:test';
import handler from '../../functions/e4-operar.ts';

const originalEnv = { ...process.env };
const originalFetch = globalThis.fetch;
let llamadas;

beforeEach(() => {
  process.env.NHOST_HASURA_URL = 'https://abcd.hasura.sa-east-1.nhost.run';
  process.env.NHOST_ADMIN_SECRET = 'secreto-de-prueba';
  process.env.E3_INTERNAL_KEY = 'clave-interna-de-prueba';
  llamadas = [];
});

afterEach(() => {
  process.env = { ...originalEnv };
  globalThis.fetch = originalFetch;
});

function peticion({ token, clave, cuerpo, metodo = 'POST', origen }) {
  const cabeceras = { authorization: token ? `Bearer ${token}` : undefined, 'x-costflow-internal-key': clave, origin: origen };
  return { method: metodo, header: (n) => cabeceras[n.toLowerCase()], body: cuerpo };
}

function respuesta() {
  const res = { cabeceras: {}, codigo: 200, cuerpo: null };
  res.setHeader = (n, v) => { res.cabeceras[n] = v; };
  res.status = (c) => { res.codigo = c; return res; };
  res.json = (o) => { res.cuerpo = o; return res; };
  res.end = () => res;
  return res;
}

const respuestaDeHasura = (objeto) => new Response(JSON.stringify({ result: [['respuesta'], [JSON.stringify(objeto)]] }), { status: 200 });

test('solicitar E4 sin sesión se rechaza antes de llamar a Nhost', async () => {
  globalThis.fetch = async (...args) => { llamadas.push(args); return new Response('{}'); };
  const res = respuesta();
  await handler(peticion({ cuerpo: { operacion: 'solicitar_e4', datos: { solicitud_id: 's1' } } }), res);
  assert.equal(res.codigo, 401);
  assert.equal(llamadas.length, 0);
});

test('con sesión válida usa el id de Nhost y no el que envía el cliente', async () => {
  globalThis.fetch = async (url, opciones) => {
    llamadas.push([url, opciones]);
    if (String(url).endsWith('/v1/user')) return new Response(JSON.stringify({ id: 'usuario-real' }), { status: 200 });
    return respuestaDeHasura({ ok: true, http_code: 200 });
  };
  const res = respuesta();
  await handler(peticion({ token: 'token-valido', cuerpo: { operacion: 'solicitar_e5', datos: { solicitud_id: 's1', usuario_id_verificado: 'usuario-falso' } } }), res);
  assert.equal(res.codigo, 200);
  assert.deepEqual(res.cuerpo, { respuesta: { ok: true, http_code: 200 } });
  const sql = String(llamadas.find(([url]) => String(url).includes('/v2/query'))[1].body);
  assert.ok(sql.includes('usuario-real') && !sql.includes('usuario-falso'));
  assert.ok(sql.includes('e4_operar'));
});

test('las operaciones internas exigen la clave y el especialista no puede usarlas', async () => {
  globalThis.fetch = async (...args) => { llamadas.push(args); return respuestaDeHasura({ resultado: 'vacio' }); };
  let res = respuesta();
  await handler(peticion({ token: 'token-valido', cuerpo: { operacion: 'tomar_e4', datos: {} } }), res);
  assert.equal(res.codigo, 401);
  assert.equal(llamadas.length, 0);
  res = respuesta();
  await handler(peticion({ clave: 'clave-incorrecta', cuerpo: { operacion: 'guardar_e4', datos: {} } }), res);
  assert.equal(res.codigo, 401);
  res = respuesta();
  await handler(peticion({ clave: 'clave-interna-de-prueba', cuerpo: { operacion: 'tomar_e4', datos: {} } }), res);
  assert.equal(res.codigo, 200);
  assert.deepEqual(res.cuerpo, { respuesta: { resultado: 'vacio' } });
});

test('una operación desconocida, datos inválidos o un método distinto se rechazan', async () => {
  globalThis.fetch = async (...args) => { llamadas.push(args); return respuestaDeHasura({}); };
  let res = respuesta();
  await handler(peticion({ clave: 'clave-interna-de-prueba', cuerpo: { operacion: 'borrar_todo', datos: {} } }), res);
  assert.equal(res.codigo, 400);
  res = respuesta();
  await handler(peticion({ clave: 'clave-interna-de-prueba', cuerpo: { operacion: 'tomar_e4', datos: [] } }), res);
  assert.equal(res.codigo, 400);
  res = respuesta();
  await handler(peticion({ metodo: 'GET', cuerpo: {} }), res);
  assert.equal(res.codigo, 405);
  assert.equal(llamadas.length, 0);
});

test('CORS permite el front local y responde al preflight', async () => {
  const res = respuesta();
  await handler(peticion({ metodo: 'OPTIONS', origen: 'http://localhost:8000', cuerpo: {} }), res);
  assert.equal(res.codigo, 204);
  assert.equal(res.cabeceras['Access-Control-Allow-Origin'], 'http://localhost:8000');
});

const CUADRO = '11111111-1111-1111-1111-111111111111';

test('descargar el cuadro exige sesión, comprueba el acceso y entrega el archivo en base64', async () => {
  globalThis.fetch = async (url, opciones) => {
    llamadas.push([String(url), opciones]);
    if (String(url).endsWith('/v1/user')) return new Response(JSON.stringify({ id: 'usuario-real' }), { status: 200 });
    if (String(url).endsWith('/v2/query')) return respuestaDeHasura({ ok: true, http_code: 200, storage_file_id: 'f1', nombre_archivo: 'cuadro.xlsx' });
    return new Response(Buffer.from('xlsx-de-prueba'), { status: 200 });
  };
  const sin = respuesta();
  await handler(peticion({ cuerpo: { operacion: 'descargar_e5', datos: { cuadro_id: CUADRO } } }), sin);
  assert.equal(sin.codigo, 401);
  assert.equal(llamadas.length, 0);

  const res = respuesta();
  await handler(peticion({ token: 'jwt', cuerpo: { operacion: 'descargar_e5', datos: { cuadro_id: CUADRO } } }), res);
  assert.equal(res.codigo, 200);
  assert.equal(res.cuerpo.nombre_archivo, 'cuadro.xlsx');
  assert.equal(Buffer.from(res.cuerpo.archivo_b64, 'base64').toString(), 'xlsx-de-prueba');
  const consulta = llamadas.find(([u]) => u.endsWith('/v2/query'));
  assert.match(JSON.parse(consulta[1].body).args.sql, /e5_cuadro_para_descarga\('usuario-real'::uuid/);
  assert.ok(llamadas.some(([u]) => u === 'https://abcd.storage.sa-east-1.nhost.run/v1/files/f1'));
});

test('descargar el cuadro de otro usuario se rechaza sin tocar Storage y un id raro se descarta', async () => {
  globalThis.fetch = async (url) => {
    llamadas.push(String(url));
    if (String(url).endsWith('/v1/user')) return new Response(JSON.stringify({ id: 'ajeno' }), { status: 200 });
    return respuestaDeHasura({ ok: false, http_code: 403, mensaje: 'No tienes acceso a este cuadro.' });
  };
  const res = respuesta();
  await handler(peticion({ token: 'jwt', cuerpo: { operacion: 'descargar_e5', datos: { cuadro_id: CUADRO } } }), res);
  assert.equal(res.codigo, 403);
  assert.ok(!llamadas.some((u) => u.includes('.storage.')));
  const mala = respuesta();
  await handler(peticion({ token: 'jwt', cuerpo: { operacion: 'descargar_e5', datos: { cuadro_id: "x'; drop" } } }), mala);
  assert.equal(mala.codigo, 400);
});

function conHasuraYAviso(avisos) {
  return async (url, opciones) => {
    avisos.push([String(url), opciones]);
    if (String(url).endsWith('/v1/user')) return new Response(JSON.stringify({ id: 'usuario-real' }), { status: 200 });
    if (String(url).endsWith('/v2/query')) return respuestaDeHasura({ ok: true, http_code: 200 });
    return new Response('{}', { status: 200 });
  };
}

test('al encolar, avisa al webhook de n8n con la clave interna; sin configurar no llama a nadie más', async () => {
  const avisos = [];
  globalThis.fetch = conHasuraYAviso(avisos);
  const pedido = (operacion) => peticion({ token: 'jwt', cuerpo: { operacion, datos: { solicitud_id: 's1' } } });

  await handler(pedido('solicitar_e4'), respuesta());
  assert.ok(!avisos.some(([u]) => u.includes('n8n')), 'sin variable no debe avisar');

  process.env.N8N_AVISO_E4 = 'https://demo.app.n8n.cloud/webhook/e4-ejecutar';
  process.env.N8N_AVISO_E5 = 'https://demo.app.n8n.cloud/webhook/e5-ejecutar';
  const res = respuesta();
  await handler(pedido('solicitar_e4'), res);
  assert.equal(res.codigo, 200);
  const aviso = avisos.find(([u]) => u === 'https://demo.app.n8n.cloud/webhook/e4-ejecutar');
  assert.ok(aviso, 'avisó al webhook de E4');
  assert.equal(aviso[1].headers['x-costflow-internal-key'], 'clave-interna-de-prueba');
  await handler(pedido('solicitar_e5'), respuesta());
  assert.ok(avisos.some(([u]) => u === 'https://demo.app.n8n.cloud/webhook/e5-ejecutar'));
});

test('si el aviso falla o la solicitud no se encoló, no cambia la respuesta ni se avisa', async () => {
  process.env.N8N_AVISO_E4 = 'https://demo.app.n8n.cloud/webhook/e4-ejecutar';
  const avisos = [];
  globalThis.fetch = async (url, opciones) => {
    avisos.push(String(url));
    if (String(url).includes('n8n.cloud')) throw new Error('sin red');
    return conHasuraYAviso([])(url, opciones);
  };
  const res = respuesta();
  await handler(peticion({ token: 'jwt', cuerpo: { operacion: 'solicitar_e4', datos: { solicitud_id: 's1' } } }), res);
  assert.equal(res.codigo, 200);
  assert.equal(res.cuerpo.respuesta.ok, true);

  avisos.length = 0;
  globalThis.fetch = async (url) => {
    avisos.push(String(url));
    if (String(url).endsWith('/v1/user')) return new Response(JSON.stringify({ id: 'usuario-real' }), { status: 200 });
    return respuestaDeHasura({ ok: false, http_code: 409, mensaje: 'Ya hay una homologación en curso' });
  };
  await handler(peticion({ token: 'jwt', cuerpo: { operacion: 'solicitar_e4', datos: { solicitud_id: 's1' } } }), respuesta());
  assert.ok(!avisos.some((u) => u.includes('n8n.cloud')), 'no avisa si no se encoló');
});
