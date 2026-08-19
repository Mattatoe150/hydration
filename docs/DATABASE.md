# The database, writing to it, and its security

The map has **two data sources**, kept deliberately separate:

1. **Base map** — water/vending/shops/fuel, baked into `index.html` from
   OpenStreetMap. Read-only at runtime; refreshed by `tools/refresh_data.py`
   (daily via GitHub Actions — see below). **The app never writes to this.**
2. **Community submissions** — a small [Cloudflare D1](https://developers.cloudflare.com/d1/)
   (SQLite) database, the *only* thing the app writes to.

Keeping them apart is the core safety property: **no submission, and no bot, can
change the OpenStreetMap-derived base map.** Worst case, junk lands in the
submissions table, which you moderate away.

## Schema

One table, `suggestions` (full DDL in [`schema.sql`](../schema.sql)):

| column | meaning |
|--------|---------|
| `id` | autoincrement primary key |
| `kind` | `add` (new spot) or `report` (problem with an existing spot) |
| `cat` | `water` / `vdrinks` / `vsnacks` / `shop` / `fuel` |
| `lat`, `lon` | coordinates |
| `name`, `note` | free text (length-capped) |
| `reason` | for reports: `no_shop` / `gone` / `moved` / `closed_wrong` / `other` |
| `status` | `new` → `approved` / `rejected` (your moderation) |
| `created` | ISO-8601 timestamp |
| `submitter` | optional name the contributor typed, so you can recognise regulars/friends — **shown only in `admin.html`, never in the public feed** |
| `iphash` | salted hash of submitter IP, for rate limiting only — **cleared the moment you moderate the row** |

## How writes happen

There is **no direct database access from the browser.** Every write goes through
a Cloudflare Pages Function that validates first:

```
Browser ──POST /api/suggestions──▶ functions/api/suggestions.js ──▶ D1 (INSERT status='new')
Admin  ──POST /api/moderate─────▶ functions/api/moderate.js     ──▶ D1 (UPDATE/DELETE, token required)
```

- `POST /api/suggestions` is public and only ever **inserts** a `status='new'` row.
- `POST /api/moderate` is token-protected and is the only thing that can approve,
  reject or delete.
- `GET /api/suggestions` returns just `new`+`approved` **adds** for the map;
  reports are never exposed publicly.

## Security measures

- **No SQL injection** — every query uses parameter binding (`.bind(...)`), never
  string concatenation.
- **Strict validation** — coordinates must be inside a Belgium bounding box;
  category and reason must be from fixed allow-lists; `name`/`note` are
  length-capped; anything containing a URL is rejected (crude spam filter).
- **Honeypot** — a hidden form field; if filled (bots do), the submission is
  silently dropped.
- **Rate limiting** — max 20 submissions per IP per hour. The IP is salted-hashed
  (`SHA-256`, see `functions/_util.js`); the raw address is **never stored**, and
  even the hash is deleted once you moderate the row. Set a private `IP_SALT`
  secret to make the hashes unguessable.
- **Constant-time token check** — the admin token comparison doesn't short-circuit,
  avoiding timing leaks.
- **Nothing trusted by default** — submissions are unverified until you approve
  them; the base map is immutable.
- **Stronger option** — put [Cloudflare Turnstile](https://developers.cloudflare.com/turnstile/)
  (free) in front of the POST for real bot resistance; a few lines in
  `functions/api/suggestions.js`.

## Inspecting, backing up, restoring

```bash
# peek at pending rows
npx wrangler d1 execute hydration --remote \
  --command "SELECT id,kind,cat,name,status,created FROM suggestions ORDER BY id DESC LIMIT 20;"

# full backup to a file
npx wrangler d1 export hydration --remote --output backup-$(date +%F).sql

# restore / re-apply schema
npx wrangler d1 execute hydration --remote --file backup-2026-08-17.sql
```

D1 also keeps automatic Time Travel backups (point-in-time restore) for the last
30 days — see the Cloudflare docs.

## Refreshing the base map (daily)

[`.github/workflows/refresh-data.yml`](../.github/workflows/refresh-data.yml) runs
`tools/refresh_data.py` every day at 04:17 UTC, commits `index.html` if the
OpenStreetMap data changed, and (optionally) redeploys. This keeps water/shops/
vending/fuel current without touching the submissions database. You can also run
it on demand from the repo's **Actions** tab, or locally:

```bash
python3 tools/refresh_data.py
```
