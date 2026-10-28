import assert from 'node:assert/strict';
import { test, beforeEach, afterEach } from 'node:test';
import handler from '../../functions/e3-operar.ts';

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

function peticion({ token, cuerpo }) {
  return {
    method: 'POST',
    header: (nombre) => (nombre.toLowerCase() === 'authorization' && token ? `Bearer ${token}` : undefined),
    body: cuerpo,
  };
}

function respuesta() {
  const res = { cabeceras: {}, codigo: 200, cuerpo: null };
  res.setHeader = (n, v) => { res.cabeceras[n] = v; };
  res.status = (c) => { res.codigo = c; return res; };
  res.json = (o) => { res.cuerpo = o; return res; };
  return res;
}

const cuerpoDecision = {
  operacion: 'decision',
  datos: { usuario_id_verificado: 'usuario-falso', accion: { accion: 'aceptar_version', version_id: 'v1', accion_id: 'a1' } },
};

test('una decisión sin sesión se rechaza antes de llamar a Nhost', async () => {
  globalThis.fetch = async (...args) => { llamadas.push(args); return new Response('{}', { status: 200 }); };
  const res = respuesta();

  await handler(peticion({ token: null, cuerpo: cuerpoDecision }), res);

  assert.equal(res.codigo, 401);
  assert.equal(llamadas.length, 0);
});

test('un token que Nhost no acepta se rechaza', async () => {
  globalThis.fetch = async (...args) => {
    llamadas.push(args);
    return new Response('{"message":"invalid"}', { status: 401 });
  };
  const res = respuesta();

  await handler(peticion({ token: 'token-falso', cuerpo: cuerpoDecision }), res);

  assert.equal(res.codigo, 401);
  assert.equal(llamadas.length, 1);
});

test('con sesión válida usa el id que devuelve Nhost y no el que envía el cliente', async () => {
  globalThis.fetch = async (url, opciones) => {
    llamadas.push([url, opciones]);
    if (String(url).endsWith('/v1/user')) {
      return new Response(JSON.stringify({ id: 'usuario-real' }), { status: 200 });
    }
    return new Response('{"errors":[{"message":"prueba"}]}', { status: 500 });
  };
  const res = respuesta();

  await handler(peticion({ token: 'token-valido', cuerpo: cuerpoDecision }), res);

  const consultaAuth = llamadas.find(([url]) => String(url).includes('.auth.'));
  assert.ok(consultaAuth, 'debe consultar Nhost Auth');
  assert.equal(consultaAuth[1].headers.Authorization, 'Bearer token-valido');

  const consultaSql = llamadas.find(([url]) => String(url).includes('/v2/query'));
  assert.ok(consultaSql, 'debe llamar a Hasura para ejecutar e3_operar');
  const cuerpo = String(consultaSql[1].body);
  assert.ok(cuerpo.includes('usuario-real'), 'debe usar el id verificado');
  assert.ok(!cuerpo.includes('usuario-falso'), 'no debe usar el id enviado por el cliente');
});

test('otras operaciones siguen exigiendo la clave interna', async () => {
  globalThis.fetch = async (...args) => { llamadas.push(args); return new Response('{}', { status: 200 }); };
  const res = respuesta();

  await handler(peticion({ token: 'token-valido', cuerpo: { operacion: 'configuracion', datos: {} } }), res);

  assert.equal(res.codigo, 401);
  assert.equal(llamadas.length, 0);
});
