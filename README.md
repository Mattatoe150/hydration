# 💧 Hydration Map — Belgium

An interactive map of places to **refill water** or **buy a cold drink** while
cycling in Belgium/Flanders. Built from open [OpenStreetMap](https://www.openstreetmap.org)
data, it combines four things that no existing map puts together:

| Layer | What it is | Count (2026-08) |
|-------|------------|-----------------|
| 💧 **Free water** | drinking-water points, public taps, drinkable springs & fountains | ~1,319 |
| 🥤 **Vending** | food/drink vending machines (parking & transit ticket machines excluded) | ~1,975 |
| 🏪 **Shop** | convenience stores, supermarkets & kiosks | ~6,992 |
| ⛽ **Fuel station** | fuel stations (many have 24/7 shops) | ~3,023 |
| 📍 **Community** | spots suggested by users (optional backend) | grows over time |

**Why it exists:** vending machines alone are too sparse and rarely tagged as
24/7, so for a guaranteed cold drink you want shops and fuel stations — but those
close, especially on Sundays. This map shows **open/closed right now** (including
Sunday and Belgian public holidays) so you can plan a hot-weather ride.

## Features

- Colour-coded, labelled layers you can toggle on/off
- **Open-now** evaluation of `opening_hours` (via [opening_hours.js](https://github.com/opening-hours/opening_hours.js)), with an "only show open right now" filter
- **Find me** — geolocation button
- **Suggest a spot** — click the map to propose a missing water point, machine or shop
- Marker clustering, so 13k+ points stay fast and legible
- Single self-contained `index.html` (data embedded) — trivially hostable

## Tech

- **Front-end:** one static `index.html` — [Leaflet](https://leafletjs.com) + MarkerCluster + opening_hours.js (from CDN), OSM raster tiles. All ~13,300 POIs are embedded in the file.
- **Suggestions backend (optional):** a [Cloudflare Pages Function](functions/api/suggestions.js) backed by [D1](https://developers.cloudflare.com/d1/). Without it, the map still works fully and the suggest form falls back to opening an OpenStreetMap note.
- **Data refresh:** [`tools/refresh_data.py`](tools/refresh_data.py) re-pulls OSM via the Overpass API and rebuilds `index.html`. Standard-library Python, no dependencies.

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

## Data & licence

Map data © OpenStreetMap contributors, licensed [ODbL](https://opendatacommons.org/licenses/odbl/).
Coverage is crowd-sourced and **incomplete** — absence of a point doesn't mean
there's nothing there, and a machine tagged without hours isn't necessarily closed.
Always check for a "no drinking water" sign before drinking from a tap or spring.

The best way to improve the map is to add spots directly to OpenStreetMap (e.g.
with the [StreetComplete](https://streetcomplete.app/) app) — everyone's maps benefit.
