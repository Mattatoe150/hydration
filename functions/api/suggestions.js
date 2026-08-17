/**
 * Cloudflare Pages Function — community spot suggestions.
 *
 * Routes (served automatically at /api/suggestions):
 *   GET   → returns recent, non-rejected suggestions as JSON
 *   POST  → stores a new suggestion (status "new", awaiting moderation)
 *
 * Requires a D1 database bound as `DB` (see wrangler.toml / docs/DEPLOY.md).
 * If no backend is deployed, the front-end degrades gracefully and offers an
 * "open an OpenStreetMap note" fallback instead.
 */

const CATS = ['water', 'vending', 'shop', 'fuel'];

// Rough bounding box for Belgium — rejects obviously bogus coordinates.
const BE = { latMin: 49.4, latMax: 51.6, lonMin: 2.5, lonMax: 6.5 };

export async function onRequestGet({ env }) {
  if (!env.DB) return json([], 200);
  const { results } = await env.DB.prepare(
    `SELECT id, lat, lon, cat, name, note, created
       FROM suggestions
      WHERE status IN ('new', 'approved')
      ORDER BY created DESC
      LIMIT 1000`
  ).all();
  return json(results ?? []);
}

export async function onRequestPost({ request, env }) {
  if (!env.DB) return json({ error: 'no database bound' }, 503);

  let b;
  try { b = await request.json(); } catch { return json({ error: 'invalid json' }, 400); }

  const lat = Number(b.lat), lon = Number(b.lon);
  const cat = String(b.cat || '');
  const name = String(b.name || '').trim().slice(0, 80);
  const note = String(b.note || '').trim().slice(0, 280);

  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return json({ error: 'bad coords' }, 400);
  if (lat < BE.latMin || lat > BE.latMax || lon < BE.lonMin || lon > BE.lonMax)
    return json({ error: 'coords outside Belgium' }, 400);
  if (!CATS.includes(cat)) return json({ error: 'bad category' }, 400);

  await env.DB.prepare(
    `INSERT INTO suggestions (lat, lon, cat, name, note, status, created)
     VALUES (?, ?, ?, ?, ?, 'new', ?)`
  ).bind(+lat.toFixed(6), +lon.toFixed(6), cat, name, note, new Date().toISOString()).run();

  return json({ ok: true });
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });
}
