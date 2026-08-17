/**
 * Public endpoint for community submissions.
 *
 *   GET  /api/suggestions  → new+approved ADD pins (for the map's Community layer)
 *   POST /api/suggestions  → store an 'add' or a 'report' (status "new", unverified)
 *
 * Nothing posted here is ever trusted automatically: adds appear only as an
 * unverified "Community" layer, reports are invisible to the public, and the
 * maintainer approves/rejects everything via /api/moderate (see admin.html).
 * So a bot can at worst create pending rows you can mass-reject — it can never
 * alter the OpenStreetMap-derived base data.
 *
 * Security measures here:
 *   - parameterised D1 queries (no SQL injection)
 *   - strict validation: Belgium bbox, allowed categories/reasons, length caps
 *   - link/URL rejection (crude spam guard) + a hidden honeypot field
 *   - per-IP rate limiting (hashed IP, never stored in the clear)
 *
 * Requires a D1 database bound as `DB` (see wrangler.toml / docs/DEPLOY.md).
 */
import { json, ipHash } from '../_util.js';

const CATS = ['water', 'vdrinks', 'vsnacks', 'shop', 'fuel'];
const REASONS = ['no_shop', 'gone', 'moved', 'closed_wrong', 'other'];
const BE = { latMin: 49.4, latMax: 51.6, lonMin: 2.5, lonMax: 6.5 };
const URLISH = /(https?:\/\/|www\.|\[url|<a\s)/i;
const RATE_LIMIT = 20;          // max submissions …
const RATE_WINDOW_MS = 3600e3;  // … per IP per hour

export async function onRequestGet({ env }) {
  if (!env.DB) return json([]);
  const { results } = await env.DB.prepare(
    `SELECT id, lat, lon, cat, name, note, status
       FROM suggestions
      WHERE kind = 'add' AND status IN ('new', 'approved')
      ORDER BY created DESC
      LIMIT 2000`
  ).all();
  return json(results ?? []);
}

export async function onRequestPost({ request, env }) {
  if (!env.DB) return json({ error: 'no database bound' }, 503);

  let b;
  try { b = await request.json(); } catch { return json({ error: 'invalid json' }, 400); }

  // Honeypot: real users never fill the hidden `hp` field.
  if (b.hp) return json({ ok: true });   // silently accept-and-drop

  const kind = b.kind === 'report' ? 'report' : 'add';
  const lat = Number(b.lat), lon = Number(b.lon);
  const cat = String(b.cat || '');
  const name = String(b.name || '').trim().slice(0, 80);
  const note = String(b.note || '').trim().slice(0, 280);
  const reason = kind === 'report' ? String(b.reason || 'other') : null;

  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return json({ error: 'bad coords' }, 400);
  if (lat < BE.latMin || lat > BE.latMax || lon < BE.lonMin || lon > BE.lonMax)
    return json({ error: 'coords outside Belgium' }, 400);
  if (!CATS.includes(cat)) return json({ error: 'bad category' }, 400);
  if (kind === 'report' && !REASONS.includes(reason)) return json({ error: 'bad reason' }, 400);
  if (URLISH.test(name) || URLISH.test(note)) return json({ error: 'links not allowed' }, 400);

  // Per-IP rate limit (hashed IP; we never persist the raw address).
  const iphash = await ipHash(request, env);
  if (iphash) {
    const since = new Date(Date.now() - RATE_WINDOW_MS).toISOString();
    const row = await env.DB.prepare(
      `SELECT COUNT(*) AS c FROM suggestions WHERE iphash = ? AND created > ?`
    ).bind(iphash, since).first();
    if (row && row.c >= RATE_LIMIT) return json({ error: 'rate limit — try later' }, 429);
  }

  await env.DB.prepare(
    `INSERT INTO suggestions (kind, cat, lat, lon, name, note, reason, status, created, iphash)
     VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)`
  ).bind(kind, cat, +lat.toFixed(6), +lon.toFixed(6), name, note, reason, new Date().toISOString(), iphash).run();

  return json({ ok: true });
}
