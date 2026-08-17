# Deploying to Cloudflare Pages

The map is a static file, so hosting it is trivial. The **community suggestions**
feature additionally needs a Cloudflare D1 database and the Pages Function in
`functions/api/suggestions.js`. You can deploy the static map first and add the
backend later.

## Prerequisites

- A (free) [Cloudflare account](https://dash.cloudflare.com/sign-up)
- Node.js installed (for `wrangler`, Cloudflare's CLI)
- This repository checked out locally

Log in once:

```bash
npx wrangler login
```

## Option A — static map only (no suggestions backend)

```bash
npx wrangler pages deploy . --project-name hydration
```

That publishes the current folder and prints your `*.pages.dev` URL. The map is
fully functional; the "Suggest a spot" form will fall back to opening an
OpenStreetMap note instead of saving to a database.

## Option B — with the community suggestions backend (D1)

### 1. Create the database

```bash
npx wrangler d1 create hydration
```

Copy the printed `database_id` into [`wrangler.toml`](../wrangler.toml), replacing
`REPLACE_WITH_YOUR_DATABASE_ID`.

### 2. Create the table

```bash
npx wrangler d1 execute hydration --remote --file=schema.sql
```

### 3. Set your moderation token

The maintainer moderation page (`/admin.html`) is protected by a secret you choose.
Set it as a Pages secret named `ADMIN_TOKEN`:

```bash
npx wrangler pages secret put ADMIN_TOKEN --project-name hydration
# paste a long random string when prompted — this is your admin password
```

### 4. Deploy

```bash
npx wrangler pages deploy . --project-name hydration
```

Because `wrangler.toml` contains the `[[d1_databases]]` binding, the Pages
Functions deploy with `env.DB` bound to your database. Verify:

```bash
curl https://hydration.pages.dev/api/suggestions        # → []  (empty list)
```

Submitting the on-map form now writes rows with `status = 'new'`.

## Moderating & certifying (this is your "certify" control)

Nothing submitted is ever trusted automatically — **adds** appear only as an
unverified pink "Community" pin, and **reports** are invisible to the public until
you act. Go to:

```
https://hydration.pages.dev/admin.html
```

Enter your `ADMIN_TOKEN`, click **Load pending**, and for each item click
**Approve** (certifies it — an add becomes a ✓ verified pin), **Reject** (hides
it), or **Delete**. The token is stored only in your browser.

### Why a bot can't wreck the map

- The base map (water/shops/vending/fuel) is baked into `index.html` from
  OpenStreetMap and is **never** touched by the API.
- Public submissions can only *create* `status='new'` rows in a separate layer.
- Worst case, a spammer creates pending pins you bulk-reject/delete from the admin
  page. The endpoint also rejects submissions containing links and caps lengths.
- Want stronger protection? Add [Cloudflare Turnstile](https://developers.cloudflare.com/turnstile/)
  (free) in front of the POST — a few lines in `functions/api/suggestions.js`.

Prefer the command line? You can still moderate directly:

```bash
npx wrangler d1 execute hydration --remote \
  --command "UPDATE suggestions SET status='approved' WHERE id=1;"
```

## Custom domain

In the Cloudflare dashboard: **Workers & Pages → hydration → Custom domains**,
add your domain and follow the DNS prompt.

## Making the repo public

The repo is created private by default. To open it up (so others can fork/PR):

```bash
gh repo edit --visibility public
```

Cloudflare Pages can deploy from a private repo too, so this is only about
sharing the source.
