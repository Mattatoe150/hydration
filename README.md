# 💧 Hydration Map — Belgium

### 🔗 Live at **[ikhebdorst.be](https://ikhebdorst.be)**

An interactive map of places to **refill water** or **buy a cold drink** in
Belgium/Flanders — for anyone who's thirsty (walking, cycling, running, or just
out and about). Built from open [OpenStreetMap](https://www.openstreetmap.org)
data, it combines four things that no existing map puts together:

| Layer | What it is | Count (2026-08) |
|-------|------------|-----------------|
| 💧 **Free water** | drinking-water points, public taps, drinkable springs & fountains | ~1,319 |
| 🥤 **Drinks vending** | drink vending machines (coffee/soft drinks) | ~445 |
| 🍫 **Snacks vending** | snack/sweets/ice-cream machines (optional layer, off by default) | ~402 |
| 🏪 **Shop** | convenience stores, supermarkets & kiosks | ~6,992 |
| ⛽ **Fuel-station shop** | fuel stations that *likely* have a shop (heuristic, see below) | ~323 |
| 📍 **Community** | spots suggested by users, once approved (optional backend) | grows over time |

**Why it exists:** vending machines alone are too sparse and rarely tagged as
24/7, so for a guaranteed cold drink you want shops and fuel stations — but those
close, especially on Sundays. This map shows **open/closed right now** (including
Sunday and Belgian public holidays) so you can plan ahead on a hot day.

**Deliberately excluded:** bread machines and farm-only automats (potatoes, milk,
eggs…) — this is a drinks/hydration map, not a groceries map.

**The fuel-station heuristic:** most petrol stations are pump-only with no shop,
and OSM almost never tags the shop directly (only ~1% do). So a station is shown
as a "fuel-station shop" only if it has an explicit shop tag, **or** it has
opening hours *and* isn't tagged automated/self-service *and* isn't an unmanned
sub-brand (Express/Easy/…). That cuts ~3,020 raw fuel nodes down to ~320 that
plausibly sell a drink. It's a best guess — users can **report** any that are wrong.

## Features

- Colour-coded, labelled layers you can toggle on/off
- **Open-now** evaluation of `opening_hours` (via [opening_hours.js](https://github.com/opening-hours/opening_hours.js)), with an "only show open right now" filter
- **Find me** — geolocation button
- **Add / fix** — a guided form to add a spot (drinks machine, shop, petrol-with-shop, or water) or to **report** a problem on an existing one ("no shop here", "doesn't exist anymore", "wrong hours")
- **Maintainer moderation & upstreaming** — everything submitted stays an unverified "Community" pin (or, for reports, invisible) until you approve it at [`/admin.html`](admin.html); nothing a user or bot submits can alter the base map. From the admin page, one click (**✎ Add to OSM**) opens the OpenStreetMap editor at the spot so you can push a verified pin *upstream* into OSM — where every map benefits and your own map picks it up on the next data refresh. Submitters consent to ODbL, so this stays licence-clean.
- Marker clustering, so ~9.5k points stay fast and legible
- Single self-contained `index.html` (data embedded) — trivially hostable

## Tech

- **Front-end:** one static `index.html` — [Leaflet](https://leafletjs.com) + MarkerCluster + opening_hours.js (from CDN), OSM raster tiles. All ~9,500 POIs are embedded in the file.
- **Suggestions backend (optional):** [Cloudflare Pages Functions](functions/api/) backed by [D1](https://developers.cloudflare.com/d1/) — `api/suggestions` (public add/report) and `api/moderate` (token-protected approve/reject, used by `admin.html`). Hardened with parameterised queries, strict validation, a honeypot, per-IP rate limiting (hashed IPs, never stored raw), and a constant-time token check. Without a backend the map still works fully and the form falls back to opening an OpenStreetMap note. Details in [docs/DATABASE.md](docs/DATABASE.md).
- **Data refresh:** [`tools/refresh_data.py`](tools/refresh_data.py) re-pulls OSM via the Overpass API and rebuilds `index.html` — standard-library Python, no dependencies. Runs **daily** via [GitHub Actions](.github/workflows/refresh-data.yml) so the base map stays current; the community database is untouched by it.

## Run locally

It's a static file — open `index.html` in a browser, or serve the folder:

```bash
python3 -m http.server 8000
# then visit http://localhost:8000
```

The suggest form's `/api/suggestions` calls only work once deployed to Cloudflare
Pages (see below); locally it falls back to the OpenStreetMap-note link.

## Deploy (Cloudflare Pages)

See **[docs/DEPLOY.md](docs/DEPLOY.md)** for the full walkthrough, including
setting up the D1 database for community suggestions.

## Refresh the data

See **[docs/DATA.md](docs/DATA.md)** for the data sources and how to rebuild.

```bash
python3 tools/refresh_data.py
```

## Support

The map carries a **☕ Buy me a coffee** button to help cover running costs (the
domain and the time spent approving submissions). **Anything collected above those
costs is donated to [Join For Water](https://joinforwater.ngo/en/)** — a Belgian
charity working on clean water.

To wire up the button: create a free page at [buymeacoffee.com](https://www.buymeacoffee.com/),
then replace `YOUR_HANDLE` in the `☕ Buy me a coffee` link inside
[`tools/index_template.html`](tools/index_template.html) and rebuild
(`python3 tools/refresh_data.py`).

## Data & licence

Map data © OpenStreetMap contributors, licensed [ODbL](https://opendatacommons.org/licenses/odbl/).
Coverage is crowd-sourced and **incomplete** — absence of a point doesn't mean
there's nothing there, and a machine tagged without hours isn't necessarily closed.
Always check for a "no drinking water" sign before drinking from a tap or spring.

The best way to improve the map is to add spots directly to OpenStreetMap (e.g.
with the [StreetComplete](https://streetcomplete.app/) app) — everyone's maps benefit.
