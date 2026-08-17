# Data sources & refreshing

All map data comes from **OpenStreetMap** via the
[Overpass API](https://overpass-api.de/). Snapshot embedded in `index.html`:
**2026-08-17**, whole of Belgium.

## What's included

| Layer | OSM tags queried |
|-------|------------------|
| 💧 water | `amenity=drinking_water`; `man_made=water_tap` (unless `drinking_water=no`); `natural=spring` + `drinking_water=yes`; `amenity=fountain` + `drinking_water=yes` |
| 🥤 vending | `amenity=vending_machine`, then filtered to food/drink values (see below) |
| 🏪 shop | `shop=convenience`, `shop=supermarket`, `shop=kiosk` |
| ⛽ fuel | `amenity=fuel` |

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
[ lat, lon, cat, sub, name, opening_hours ]
```

- `cat` — `water` | `vdrinks` | `vsnacks` | `shop` | `fuel`
- `sub` — subtype (e.g. `drinking_water`, `supermarket`, `drinks`)
- `opening_hours` — raw OSM `opening_hours` string, or `""` if untagged

Only ~39% of shops carry `opening_hours`, and only ~12% of vending machines. An
empty value renders as **"hours unknown"**, not "closed".

## Refreshing

```bash
python3 tools/refresh_data.py
```

This re-runs the three Overpass queries, rebuilds `index.html` from
`tools/index_template.html`, and prints the new counts. Standard-library Python
only — no dependencies. Overpass can be rate-limited; the script retries.

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
