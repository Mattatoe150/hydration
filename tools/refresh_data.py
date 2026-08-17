#!/usr/bin/env python3
"""
Refresh the map data from OpenStreetMap (via the Overpass API) and rebuild
../index.html from index_template.html.

    python3 tools/refresh_data.py            # fetch fresh data, then rebuild
    python3 tools/refresh_data.py --cached   # rebuild from tools/*.json snapshots

Standard library only. Data © OpenStreetMap contributors, ODbL. Coverage is
crowd-sourced and partial.
"""
import json, time, re, urllib.parse, urllib.request, collections, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
ENDPOINT = "https://overpass-api.de/api/interpreter"
CACHED = "--cached" in sys.argv

WATER_Q = """[out:json][timeout:180];
area["ISO3166-1"="BE"][admin_level=2]->.be;
(
  node["amenity"="drinking_water"](area.be);
  node["man_made"="water_tap"]["drinking_water"!="no"](area.be);
  node["natural"="spring"]["drinking_water"="yes"](area.be);
  nwr["amenity"="fountain"]["drinking_water"="yes"](area.be);
);
out center;"""

VENDING_Q = """[out:json][timeout:180];
area["ISO3166-1"="BE"][admin_level=2]->.be;
node["amenity"="vending_machine"](area.be);
out geom;"""

SHOPS_Q = """[out:json][timeout:180];
area["ISO3166-1"="BE"][admin_level=2]->.be;
(
  nwr["shop"="convenience"](area.be);
  nwr["shop"="supermarket"](area.be);
  nwr["shop"="kiosk"](area.be);
  nwr["amenity"="fuel"](area.be);
);
out center;"""

# --- Vending: keep only DRINKS (primary) and SNACKS (optional). Bread & farm
#     produce are intentionally excluded — this map is about drinks, not groceries.
DRINK = {'drinks', 'coffee', 'water', 'soft_drinks', 'juice', 'cold_drinks', 'hot_drinks', 'milk_coffee'}
SNACK = {'sweets', 'ice_cream', 'food', 'pizza', 'snacks', 'chocolate', 'chips', 'confectionery', 'crisps'}
# everything else (bread, potatoes, farm_products, milk, eggs, fruit, vegetables,
# strawberries, cheese, meat, honey, flowers, parking_tickets, …) is dropped.


def overpass(query, tries=5):
    for i in range(1, tries + 1):
        try:
            req = urllib.request.Request(
                ENDPOINT, data=urllib.parse.urlencode({"data": query}).encode(),
                headers={"User-Agent": "hydration-map/1.0 (OSM data refresh)"})
            with urllib.request.urlopen(req, timeout=200) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            print(f"  attempt {i} failed ({e}); retrying in 20s…", file=sys.stderr)
            time.sleep(20)
    raise SystemExit("Overpass API unavailable after several retries.")


def load(name, query):
    """Fetch from Overpass (and cache), or reuse tools/<name>.json with --cached."""
    cache = HERE / f"{name}.json"
    if CACHED and cache.exists():
        print(f"Using cached {cache.name}")
        return json.loads(cache.read_text())
    print(f"Fetching {name}…")
    data = overpass(query)
    cache.write_text(json.dumps(data))
    return data


def coord(e):
    if 'lat' in e:   return e['lat'], e['lon']
    if 'center' in e: return e['center']['lat'], e['center']['lon']
    return None


def name_of(t):
    return (t.get('name') or t.get('brand') or t.get('operator') or '')[:60]


def vcat(v):
    parts = set(p.strip() for p in (v or '').replace('/', ';').split(';'))
    if parts & DRINK: return 'vdrinks'
    if parts & SNACK: return 'vsnacks'
    return None


# --- Fuel: "likely has a shop" heuristic (most stations are pump-only). ---
# Kept if it has an explicit shop tag, OR it has opening_hours AND is not tagged
# automated/self-service AND its brand/name isn't an unmanned sub-brand.
UNMANNED = re.compile(r'express|easy|automat|self|24/7|g&v|octa|maes\b', re.I)

def fuel_has_shop(t):
    if t.get('shop') in ('convenience', 'kiosk', 'supermarket') or t.get('shop') == 'yes':
        return True
    if not t.get('opening_hours'):
        return False
    if t.get('automated') == 'yes' or t.get('self_service') == 'yes':
        return False
    if UNMANNED.search((t.get('brand', '') + ' ' + t.get('name', ''))):
        return False
    return True


def build():
    pois = []

    for e in load('water', WATER_Q)['elements']:
        c = coord(e)
        if not c: continue
        t = e.get('tags', {})
        sub = ('drinking_water' if t.get('amenity') == 'drinking_water'
               else 'water_tap' if t.get('man_made') == 'water_tap'
               else 'spring' if t.get('natural') == 'spring'
               else 'fountain' if t.get('amenity') == 'fountain' else 'drinking_water')
        pois.append([round(c[0], 5), round(c[1], 5), 'water', sub, name_of(t), t.get('opening_hours', '')])

    for e in load('vending', VENDING_Q)['elements']:
        if 'lat' not in e: continue
        t = e.get('tags', {}); cat = vcat(t.get('vending', ''))
        if cat is None: continue
        sub = 'drinks' if cat == 'vdrinks' else 'snacks'
        pois.append([round(e['lat'], 5), round(e['lon'], 5), cat, sub, name_of(t), t.get('opening_hours', '')])

    for e in load('shops', SHOPS_Q)['elements']:
        c = coord(e)
        if not c: continue
        t = e.get('tags', {})
        if t.get('amenity') == 'fuel':
            if not fuel_has_shop(t):
                continue
            cat, sub = 'fuel', 'fuel'
        elif t.get('shop') in ('convenience', 'supermarket', 'kiosk'):
            cat, sub = 'shop', t['shop']
        else:
            continue
        pois.append([round(c[0], 5), round(c[1], 5), cat, sub, name_of(t), t.get('opening_hours', '')])

    print(f"\nTOTAL POIs: {len(pois)}")
    print(dict(collections.Counter(p[2] for p in pois)))

    data = json.dumps(pois, ensure_ascii=False, separators=(',', ':'))
    tpl = (HERE / "index_template.html").read_text()
    (ROOT / "index.html").write_text(tpl.replace("__DATA__", data))
    print(f"Wrote {ROOT / 'index.html'} ({round(len(data)/1024)} KB of data).")


if __name__ == "__main__":
    build()
