import { json } from '../_util.js';

export async function onRequestGet({ env }) {
  if (!env.DB) return json({ ok: false, database: 'unbound' }, 503);
  try {
    const row = await env.DB.prepare('SELECT 1 AS ok').first();
    return json({ ok: row?.ok === 1, database: 'reachable' });
  } catch (error) {
    console.error(JSON.stringify({ event: 'health-check-failed', error: String(error) }));
    return json({ ok: false, database: 'unreachable' }, 503);
  }
}
