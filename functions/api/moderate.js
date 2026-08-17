/**
 * Maintainer-only moderation endpoint. Protected by a shared secret token that
 * you set as the Pages environment variable / secret ADMIN_TOKEN.
 *
 *   GET  /api/moderate                     → list pending submissions (needs token)
 *   POST /api/moderate {id, action}        → approve | reject | delete   (needs token)
 *
 * Send the token in the `x-admin-token` header (admin.html does this for you).
 * Set it with:  npx wrangler pages secret put ADMIN_TOKEN
 */

function authed(request, env) {
  const t = request.headers.get('x-admin-token') || '';
  return env.ADMIN_TOKEN && t.length > 0 && t === env.ADMIN_TOKEN;
}

export async function onRequestGet({ request, env }) {
  if (!env.DB) return json({ error: 'no database bound' }, 503);
  if (!authed(request, env)) return json({ error: 'unauthorized' }, 401);
  const { results } = await env.DB.prepare(
    `SELECT id, kind, cat, lat, lon, name, note, reason, status, created
       FROM suggestions
      WHERE status = 'new'
      ORDER BY created DESC
      LIMIT 500`
  ).all();
  return json(results ?? []);
}

export async function onRequestPost({ request, env }) {
  if (!env.DB) return json({ error: 'no database bound' }, 503);
  if (!authed(request, env)) return json({ error: 'unauthorized' }, 401);

  let b;
  try { b = await request.json(); } catch { return json({ error: 'invalid json' }, 400); }
  const id = Number(b.id);
  const action = String(b.action || '');
  if (!Number.isInteger(id)) return json({ error: 'bad id' }, 400);

  if (action === 'approve') {
    await env.DB.prepare("UPDATE suggestions SET status='approved' WHERE id=?").bind(id).run();
  } else if (action === 'reject') {
    await env.DB.prepare("UPDATE suggestions SET status='rejected' WHERE id=?").bind(id).run();
  } else if (action === 'delete') {
    await env.DB.prepare("DELETE FROM suggestions WHERE id=?").bind(id).run();
  } else {
    return json({ error: 'bad action' }, 400);
  }
  return json({ ok: true });
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });
}
