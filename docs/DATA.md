# Data sources & refreshing

All map data comes from **OpenStreetMap** via the
[Overpass API](https://overpass-api.de/). Snapshot generated in `data/pois.js`
and loaded by both language pages:
**2026-08-20**, whole of Belgium (~10,000 points).

## What's included

| Layer | OSM tags queried |
|-------|------------------|
| 💧 water | `amenity=drinking_water`; `man_made=water_tap` (unless `drinking_water=no`); `natural=spring` + `drinking_water=yes`; `amenity=fountain` + `drinking_water=yes`; `amenity=water_point`; `drinking_water:refill=yes`; `amenity=toilets` + `drinking_water=yes`; `man_made=water_well` + `drinking_water=yes` |
| 🥤 vending | `amenity=vending_machine`, then filtered to food/drink values (see below) |
| 🏪 shop | `shop=convenience`, `shop=supermarket`, `shop=kiosk`, `shop=beverages` |
| ⛽ fuel | `amenity=fuel` |

### Cemetery taps

Most Belgian cemeteries have an outdoor tap for grave flowers, and they're a
well-known refill spot. **306 of them are on the map** — they were always picked
up by the `man_made=water_tap` / `amenity=drinking_water` queries; a separate
cemetery-polygon query now identifies them so they're labelled *"Cemetery tap"*
rather than a generic tap.

Taps a mapper has tagged `drinking_water=no` (15 in cemeteries) stay excluded —
that's someone's on-the-ground observation that the water is not potable, usually
matching a *"geen drinkwater"* sign, and the map shouldn't override it.

### Deliberately excluded from water

`drinking_water=yes` also appears on camp sites, camp pitches, caravan sites,
showers, pubs and cinemas. The water is real, but it sits inside a private or
paying facility — this map only promises spots you can actually walk up to, so
those are left out.

### Vending filter

`amenity=vending_machine` in Belgium is dominated by **parking-ticket** and
**public-transport-ticket** machines (~4,400 of ~6,700). The refresh script keeps
only *drinks* and *snacks*, and **drops bread and farm produce entirely** (this is
a hydration map, not a groceries map):

- **vdrinks** (primary) — `drinks`, `coffee`, `water`, `soft_drinks`, `juice`, …
- **vsnacks** (optional, off by default) — `sweets`, `ice_cream`, `food`, `pizza`, `snacks`, `chocolate`, …
- dropped — `bread`, `potatoes`, `farm_products`, `milk`, `eggs`, `fruit`, `vegetables`, `strawberries`, `cheese`, `parking_tickets`, `public_transport_tickets`, `excrement_bags`, `condoms`, …

Exact lists live in `tools/refresh_data.py` (`DRINK` / `SNACK`).

### Fuel-station "has a shop" heuristic

Most petrol stations are pump-only, and OSM tags the shop directly on only ~1% of
them — so showing all ~3,020 `amenity=fuel` nodes floods the map with places you
*can't* actually buy a drink. Instead a fuel node is kept only if:

- it has an explicit `shop=convenience|kiosk|supermarket|yes` tag, **or**
- it has `opening_hours` **and** is *not* `automated=yes`/`self_service=yes`
  **and** its brand/name doesn't match an unmanned pattern
  (`express|easy|automat|self|24/7|g&v|octa|maes`).

This keeps ~320 stations, dominated by full-service brands (TotalEnergies, Q8,
Shell, Esso). It's a heuristic — the map invites users to **report** any without
a shop. See `fuel_has_shop()` in `tools/refresh_data.py`.

## Data model

Each POI is stored as a compact array to keep the file small:

```
[ lat, lon, cat, sub, name, opening_hours, indoor ]
```

- `cat` — `water` | `vdrinks` | `vsnacks` | `shop` | `fuel`
- `sub` — subtype (e.g. `drinking_water`, `supermarket`, `drinks`)
- `opening_hours` — raw OSM `opening_hours` string, or `""` if untagged
- `indoor` — `1` when the spot is indoors or customers-only, so you'd have to walk
  into a venue to reach it (`indoor=yes|room`, `access=customers|private|permit|no`,
  or a refill tap hosted inside a shop). Powers the **walk-up only** filter.
  Building-polygon containment was tried and rejected: Belgium has too many
  buildings and the Overpass query runs out of memory.

Only ~39% of shops carry `opening_hours`, and only ~12% of vending machines. An
empty value renders as **"hours unknown"**, not "closed".

## Safety guards on the daily rebuild

The refresh runs unattended, so it refuses to write a bad generated payload:

- **Partial-result detection** — Overpass answers `200` with a `remark` field when a
  query times out or runs out of memory, and the payload is then silently
  incomplete. Any `remark` aborts the build.
- **Absolute floors** — each category has a minimum plausible count
  (`MIN_EXPECTED` in `tools/refresh_data.py`).
- **Shrink guard** — a category dropping below 85% of what's currently live also
  aborts, so a flaky response can't quietly delete thousands of points.
- **Provider fallback** — the official and an independent public Overpass
  instance are tried before the job gives up.
- **Atomic output** — both languages are fully rendered and validated first, then
  each public file is replaced atomically. The workflow commits the payload, both
  pages, and the sitemap together.
- **Script-safe data** — unsafe JSON characters are escaped before untrusted OSM
  labels are written into the generated JavaScript payload.

On failure the script exits non-zero, the workflow fails, and the previous
payload and pages stay deployed.

## Refreshing

```bash
python3 tools/refresh_data.py
```

This re-runs the Overpass queries, rebuilds the shared `data/pois.js` payload and
both HTML pages from `tools/index_template.html`, and prints the new counts.
Standard-library Python only — no dependencies. Overpass can be rate-limited;
the script retries.

## Explore the raw data yourself

Paste into [overpass-turbo.eu](https://overpass-turbo.eu/) and Run:

```
[out:json][timeout:60];
area["ISO3166-1"="BE"][admin_level=2]->.be;
node["amenity"="drinking_water"](area.be);
out geom;
```

## Attribution

Map data © OpenStreetMap contributors, [ODbL](https://opendatacommons.org/licenses/odbl/).
Any public redistribution of the data must keep this attribution.
