/**
 * Shared helpers for the Pages Functions. Underscore-prefixed files are not
 * routed by Cloudflare Pages, but can be imported by the route handlers.
 */

export function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });
}

/** Length-aware constant-time string compare (avoids early-exit timing leaks). */
export function timingEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

/** SHA-256 hex of a string (used to pseudonymise IPs — we never store raw IPs). */
export async function sha256hex(str) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
}

/** Salted hash of the caller's IP, or null if unavailable. */
export async function ipHash(request, env) {
  const ip = request.headers.get('CF-Connecting-IP');
  if (!ip) return null;
  return (await sha256hex((env.IP_SALT || 'hydration-default-salt') + '|' + ip)).slice(0, 32);
}
