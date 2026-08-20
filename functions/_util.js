/**
 * Shared helpers for the Pages Functions. Underscore-prefixed files are not
 * routed by Cloudflare Pages, but can be imported by the route handlers.
 */

export function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
      ...headers,
    },
  });
}

/** Constant-time string compare after hashing both values to a fixed length. */
export async function timingEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  const enc = new TextEncoder();
  const [ah, bh] = await Promise.all([
    crypto.subtle.digest('SHA-256', enc.encode(a)),
    crypto.subtle.digest('SHA-256', enc.encode(b)),
  ]);
  const left = new Uint8Array(ah), right = new Uint8Array(bh);
  let difference = 0;
  for (let i = 0; i < left.length; i++) difference |= left[i] ^ right[i];
  return difference === 0;
}

/** Parse a JSON request without allowing an unbounded body into memory. */
export async function readJson(request, maxBytes = 16_384) {
  const declared = Number(request.headers.get('content-length'));
  if (Number.isFinite(declared) && declared > maxBytes)
    return { error: 'request too large', status: 413 };

  if (!request.body) return { error: 'invalid json', status: 400 };
  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) {
        await reader.cancel();
        return { error: 'request too large', status: 413 };
      }
      chunks.push(value);
    }
  } catch {
    return { error: 'invalid json', status: 400 };
  }

  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  try {
    return { data: JSON.parse(new TextDecoder().decode(bytes)) };
  } catch {
    return { error: 'invalid json', status: 400 };
  }
}

/** SHA-256 hex of a string (used to pseudonymise IPs — we never store raw IPs). */
export async function sha256hex(str) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
}

/** Salted hash of the caller's IP, or null if unavailable. */
export async function ipHash(request, env) {
  const ip = request.headers.get('CF-Connecting-IP');
  // Never store a hash made with a public fallback salt. The submission endpoint
  // fails closed if this private salt or Cloudflare's caller address is missing.
  if (!ip || !env.IP_SALT) return null;
  return (await sha256hex(env.IP_SALT + '|' + ip)).slice(0, 32);
}
