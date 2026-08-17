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

### 3. Deploy

```bash
npx wrangler pages deploy . --project-name hydration
```

Because `wrangler.toml` contains the `[[d1_databases]]` binding, the Pages
Function is deployed with `env.DB` bound to your database. Verify:

```bash
curl https://hydration.pages.dev/api/suggestions        # → []  (empty list)
```

Submitting the on-map form now writes rows with `status = 'new'`.

## Moderating suggestions

Suggestions are shown immediately as an **unverified "Community"** layer. To keep
things clean you approve or reject them by flipping the `status` column:

```bash
# see what's pending
npx wrangler d1 execute hydration --remote \
  --command "SELECT id, cat, name, note, created FROM suggestions WHERE status='new';"

# approve one
npx wrangler d1 execute hydration --remote \
  --command "UPDATE suggestions SET status='approved' WHERE id=1;"

# reject (hides it from the map)
npx wrangler d1 execute hydration --remote \
  --command "UPDATE suggestions SET status='rejected' WHERE id=2;"
```

Only `new` and `approved` rows are returned to the map. (If you'd rather *not*
show suggestions until you approve them, change the `WHERE status IN (...)` clause
in `functions/api/suggestions.js` to `WHERE status = 'approved'`.)

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
