import assert from 'node:assert/strict';
import { test, beforeEach, afterEach } from 'node:test';
import handler, { baseHasura } from '../../functions/e3-operar.ts';

const originalEnv = { ...process.env };
const originalFetch = globalThis.fetch;
const originalError = console.error;
let calls;
let logs;

beforeEach(() => {
  for (const key of ['NHOST_HASURA_URL', 'NHOST_GRAPHQL_URL', 'HASURA_GRAPHQL_ADMIN_SECRET']) delete process.env[key];
  process.env.E3_INTERNAL_KEY = 'clave-interna-de-prueba';
  process.env.NHOST_ADMIN_SECRET = 'admin-de-prueba';
  process.env.NHOST_HASURA_URL = 'https://proyecto.hasura.sa-east-1.nhost.run/console';
  process.env.NHOST_GRAPHQL_URL = 'https://proyecto.graphql.sa-east-1.nhost.run/v1';
  calls = [];
  logs = [];
  console.error = (...args) => logs.push(args);
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ result: [['respuesta'], ['{"eventos":[]}']] }), { status: 200 });
  };
});

afterEach(() => {
  for (const key of Object.keys(process.env)) if (!(key in originalEnv)) delete process.env[key];
  Object.assign(process.env, originalEnv);
  globalThis.fetch = originalFetch;
  console.error = originalError;
});

async function invoke(body = { operacion: 'eventos', datos: {} }, key = 'clave-interna-de-prueba', method = 'POST') {
  const req = { method, body, header: () => key };
  const res = {
    code: 200, headers: {},
    setHeader(name, value) { this.headers[name] = value; },
    status(code) { this.code = code; return this; },
    json(body) { this.body = body; return this; },
  };
  await handler(req, res);
  return res;
}

test('prefiere la dirección administrativa cuando Nhost también proporciona GraphQL', () => {
  assert.equal(baseHasura(), 'https://proyecto.hasura.sa-east-1.nhost.run');
});

test('resuelve el dominio público GraphQL si falta NHOST_HASURA_URL', () => {
  delete process.env.NHOST_HASURA_URL;
  assert.equal(baseHasura(), 'https://proyecto.hasura.sa-east-1.nhost.run');
});

test('admite Hasura interno sin convertirlo en un dominio público', () => {
  delete process.env.NHOST_HASURA_URL;
  process.env.NHOST_GRAPHQL_URL = 'http://hasura:8080/v1/graphql';
  assert.equal(baseHasura(), 'http://hasura:8080');
});

test('rechaza direcciones con credenciales o rutas administrativas ambiguas', () => {
  process.env.NHOST_HASURA_URL = 'https://usuario:clave@hasura.example/console';
  assert.throws(baseHasura);
  process.env.NHOST_HASURA_URL = 'https://hasura.example/v1';
  assert.throws(baseHasura);
});

test('rechaza peticiones sin clave, con clave distinta o por GET antes de llamar Hasura', async () => {
  assert.equal((await invoke(undefined, '')).code, 401);
  assert.equal((await invoke(undefined, 'otra-clave')).code, 401);
  assert.equal((await invoke(undefined, undefined, 'GET')).code, 405);
  delete process.env.E3_INTERNAL_KEY;
  assert.equal((await invoke()).code, 401);
  assert.equal(calls.length, 0);
});

test('rechaza SQL libre y datos que no sean un objeto', async () => {
  assert.equal((await invoke({ operacion: 'DROP TABLE public.proyectos', datos: {} })).code, 400);
  assert.equal((await invoke({ operacion: 'eventos', datos: [] })).code, 400);
  assert.equal((await invoke({ operacion: 'eventos', datos: null })).code, 400);
  assert.equal(calls.length, 0);
});

test('invoca solo e3_operar, conserva el contrato de n8n y no expone el secreto', async () => {
  const result = await invoke({ operacion: 'preparar_correo', datos: { motivo: "O'Brien" } });
  assert.equal(result.code, 200);
  assert.deepEqual(result.body, { respuesta: { eventos: [] } });
  assert.equal(result.headers['Cache-Control'], 'no-store');
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'https://proyecto.hasura.sa-east-1.nhost.run/v2/query');
  const request = JSON.parse(calls[0].options.body);
  assert.equal(request.type, 'run_sql');
  assert.equal(request.args.sql, `SELECT public.e3_operar('preparar_correo','{"motivo":"O''Brien"}'::jsonb)::text AS respuesta;`);
  assert.equal(calls[0].options.headers['x-hasura-admin-secret'], 'admin-de-prueba');
  assert.ok(calls[0].options.signal instanceof AbortSignal);
  assert.ok(!JSON.stringify(result.body).includes('admin-de-prueba'));
});

test('no registra respuestas de Hasura con datos o secretos cuando falla', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ error: 'contenido-sensible-de-prueba' }), { status: 403 });
  assert.equal((await invoke()).code, 502);
  assert.ok(!JSON.stringify(logs).includes('contenido-sensible-de-prueba'));
});

test('respuesta mal formada, dirección incompleta o falta de admin producen error visible', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ result: [] }), { status: 200 });
  assert.equal((await invoke()).code, 500);
  delete process.env.NHOST_HASURA_URL;
  delete process.env.NHOST_GRAPHQL_URL;
  assert.equal((await invoke()).code, 500);
  delete process.env.NHOST_ADMIN_SECRET;
  assert.equal((await invoke()).code, 503);
});
