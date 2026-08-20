import test from 'node:test';
import assert from 'node:assert/strict';

import { ipHash, readJson, timingEqual } from '../functions/_util.js';
import { onRequestGet, onRequestPost } from '../functions/api/suggestions.js';

const jsonRequest = (body, headers = {}) => new Request('https://example.test/api/suggestions', {
  method: 'POST',
  headers: { 'content-type': 'application/json', ...headers },
  body: JSON.stringify(body),
});

test('token comparison handles equal, unequal, and different-length values', async () => {
  assert.equal(await timingEqual('correct horse', 'correct horse'), true);
  assert.equal(await timingEqual('correct horse', 'wrong horse'), false);
  assert.equal(await timingEqual('a', 'a much longer value'), false);
});

test('bounded JSON parser rejects oversized and malformed bodies', async () => {
  const oversized = jsonRequest({ note: 'x'.repeat(100) });
  assert.deepEqual(await readJson(oversized, 20), { error: 'request too large', status: 413 });
  const malformed = new Request('https://example.test', { method: 'POST', body: '{nope' });
  assert.deepEqual(await readJson(malformed), { error: 'invalid json', status: 400 });
});

test('IP hashes require the private salt and never contain the raw address', async () => {
  const request = new Request('https://example.test', { headers: { 'CF-Connecting-IP': '203.0.113.7' } });
  assert.equal(await ipHash(request, {}), null);
  const hash = await ipHash(request, { IP_SALT: 'test-only-secret' });
  assert.match(hash, /^[a-f0-9]{32}$/);
  assert.equal(hash.includes('203.0.113.7'), false);
});

test('public feed masks pending names and omits private notes', async () => {
  const sets = [
    [{ id: 1, lat: 50.8, lon: 4.3, cat: 'water', name: '', indoor: 0, status: 'new' }],
    [], [], [], [],
  ];
  const env = { DB: {
    prepare: query => ({ query }),
    batch: async () => sets.map(results => ({ results })),
  } };
  const response = await onRequestGet({ env });
  assert.equal(response.status, 200);
  assert.match(response.headers.get('cache-control'), /max-age=30/);
  assert.deepEqual(await response.json(), {
    pins: sets[0], hidden: [], overrides: [], comments: [], ratings: [],
  });
  assert.equal(JSON.stringify(sets[0]).includes('note'), false);
});

test('submission validation fails before touching the database', async () => {
  const DB = { prepare: () => { throw new Error('database should not be touched'); } };
  const base = { kind: 'add', cat: 'water', lat: 50.8, lon: 4.3 };
  let response = await onRequestPost({ request: jsonRequest({ ...base, cat: 'unsafe' }), env: { DB } });
  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { error: 'bad category' });
  response = await onRequestPost({ request: jsonRequest({ ...base, lat: 10 }), env: { DB } });
  assert.equal(response.status, 400);
  response = await onRequestPost({ request: jsonRequest({ ...base, note: 'https://spam.invalid' }), env: { DB } });
  assert.equal(response.status, 400);
});

test('valid submission uses the atomic rate-limit insert and returns 201', async () => {
  let sql = '', values = [];
  const DB = { prepare(query) {
    sql = query;
    return { bind(...bound) { values = bound; return { run: async () => ({ meta: { changes: 1 } }) }; } };
  } };
  const request = jsonRequest(
    { kind: 'add', cat: 'water', lat: 50.8466, lon: 4.3528, name: 'Tap' },
    { 'CF-Connecting-IP': '203.0.113.9' },
  );
  const response = await onRequestPost({ request, env: { DB, IP_SALT: 'test-secret' } });
  assert.equal(response.status, 201);
  assert.match(sql, /INSERT INTO suggestions/);
  assert.match(sql, /SELECT COUNT\(\*\)/);
  assert.equal(values.at(-1), 20);
});

test('submissions fail closed when rate-limit hashing is unavailable', async () => {
  const DB = { prepare: () => { throw new Error('database should not be touched'); } };
  const response = await onRequestPost({
    request: jsonRequest({ kind: 'add', cat: 'water', lat: 50.8, lon: 4.3 }),
    env: { DB },
  });
  assert.equal(response.status, 503);
});
