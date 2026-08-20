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
 * Requires a D1 database bound as `DB` (see wrangler.jsonc / docs/DEPLOY.md).
 */
import { json, ipHash, readJson } from '../_util.js';

const KINDS = ['add', 'report', 'comment'];
const CATS = ['water', 'vdrinks', 'vsnacks', 'shop', 'fuel'];
const REASONS = ['no_shop', 'gone', 'moved', 'closed_wrong', 'is_indoor', 'is_outdoor', 'other'];
const BE = { latMin: 49.4, latMax: 51.6, lonMin: 2.5, lonMax: 6.5 };
const URLISH = /(https?:\/\/|www\.|\[url|<a\s)/i;
const RATE_LIMIT = 20;          // max submissions …
const RATE_WINDOW_MS = 3600e3;  // … per IP per hour

export async function onRequestGet({ env }) {
  if (!env.DB) return json({ pins: [], comments: [], ratings: [], hidden: [], overrides: [] });
  const [pins, hidden, overrides, comments, ratings] = await env.DB.batch([
    env.DB.prepare(
    `SELECT id, lat, lon, cat,
            CASE WHEN status = 'approved' THEN name ELSE '' END AS name,
            indoor, status
       FROM suggestions
      WHERE kind = 'add' AND status IN ('new', 'approved')
      ORDER BY created DESC
      LIMIT 2000`
    ),
  // Spots the maintainer confirmed are wrong (gone, no shop, …). The base map is
  // rebuilt from OSM daily, so these must be suppressed at display time — the
  // suppression lives here and keeps applying after every refresh.
    env.DB.prepare(
    `SELECT lat, lon, cat
       FROM suggestions
      WHERE kind = 'report' AND suppress = 1 AND status = 'approved'
      LIMIT 2000`
    ),
  // Accepted access corrections: "you have to go inside" / "it's actually walk-up".
  // OSM tags these on only a fraction of spots, so these fix the walk-up filter
  // and, like suppressions, survive the daily rebuild.
    env.DB.prepare(
    `SELECT lat, lon, cat, reason
       FROM suggestions
      WHERE kind = 'report' AND status = 'approved'
        AND reason IN ('is_indoor', 'is_outdoor')
      LIMIT 2000`
    ),
  // Only APPROVED comments are public: unmoderated free text should never appear
  // on the map. The author's name stays maintainer-only, as promised on the form.
    env.DB.prepare(
    `SELECT lat, lon, cat, note
       FROM suggestions
      WHERE kind = 'comment' AND status = 'approved' AND note <> ''
      ORDER BY created DESC
      LIMIT 2000`
    ),
  // Star ratings are just a number — no text to abuse — so they count straight
  // away (rate-limited per IP). Rejected ones are excluded.
    env.DB.prepare(
    `SELECT ROUND(lat,5) AS lat, ROUND(lon,5) AS lon, cat,
            ROUND(AVG(rating),2) AS avg, COUNT(*) AS n
       FROM suggestions
      WHERE kind = 'comment' AND rating > 0 AND status IN ('new','approved')
      GROUP BY ROUND(lat,5), ROUND(lon,5), cat
      LIMIT 2000`
    ),
  ]);
  return json({
    pins: pins.results ?? [],
    comments: comments.results ?? [],
    ratings: ratings.results ?? [],
    hidden: hidden.results ?? [],
    overrides: (overrides.results ?? []).map(o => ({ lat: o.lat, lon: o.lon, cat: o.cat, indoor: o.reason === 'is_indoor' ? 1 : 0 })),
  }, 200, { 'cache-control': 'public, max-age=30, stale-while-revalidate=120' });
}

export async function onRequestPost({ request, env }) {
  if (!env.DB) return json({ error: 'no database bound' }, 503);

  const parsed = await readJson(request);
  if (parsed.error) return json({ error: parsed.error }, parsed.status);
  const b = parsed.data;
  if (!b || typeof b !== 'object' || Array.isArray(b)) return json({ error: 'invalid json' }, 400);

  // Honeypot: real users never fill the hidden `hp` field.
  if (b.hp) return json({ ok: true });   // silently accept-and-drop

  const kind = String(b.kind || '');
  const lat = Number(b.lat), lon = Number(b.lon);
  const cat = String(b.cat || '');
  const name = String(b.name || '').trim().slice(0, 80);
  const note = String(b.note || '').trim().slice(0, 280);
  const submitter = String(b.submitter || '').trim().slice(0, 40);
  const indoor = kind === 'add' && (b.indoor === true || b.indoor === 1) ? 1 : 0;
  const rating = kind === 'comment' ? Math.min(5, Math.max(0, Math.round(Number(b.rating) || 0))) : 0;
  const reason = kind === 'report' ? String(b.reason || 'other') : null;

  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return json({ error: 'bad coords' }, 400);
  if (lat < BE.latMin || lat > BE.latMax || lon < BE.lonMin || lon > BE.lonMax)
    return json({ error: 'coords outside Belgium' }, 400);
  if (!KINDS.includes(kind)) return json({ error: 'bad kind' }, 400);
  if (!CATS.includes(cat)) return json({ error: 'bad category' }, 400);
  if (kind === 'report' && !REASONS.includes(reason)) return json({ error: 'bad reason' }, 400);
  if (kind === 'comment' && !note && !rating) return json({ error: 'please write a comment or give a rating' }, 400);
  if (URLISH.test(name) || URLISH.test(note) || URLISH.test(submitter)) return json({ error: 'links not allowed' }, 400);

  // Per-IP rate limit and insert are one SQL statement, so concurrent requests
  // cannot race between a separate COUNT and INSERT.
  const iphash = await ipHash(request, env);
  if (!iphash) return json({ error: 'submission service unavailable' }, 503);
  const created = new Date().toISOString();
  const since = new Date(Date.now() - RATE_WINDOW_MS).toISOString();
  const result = await env.DB.prepare(
    `INSERT INTO suggestions (kind, cat, lat, lon, name, note, submitter, indoor, rating, reason, status, created, iphash)
     SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?
      WHERE ? IS NULL OR (
        SELECT COUNT(*) FROM suggestions WHERE iphash = ? AND created > ?
      ) < ?`
  ).bind(
    kind, cat, +lat.toFixed(6), +lon.toFixed(6), name, note, submitter,
    indoor, rating, reason, created, iphash, iphash, iphash, since, RATE_LIMIT
  ).run();

  if (!result.meta?.changes) return json({ error: 'rate limit — try later' }, 429);

  return json({ ok: true }, 201);
}
