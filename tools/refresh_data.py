#!/usr/bin/env python3
"""
Refresh the map data from OpenStreetMap (via the Overpass API) and rebuild
../index.html from index_template.html.

Usage:
    python3 tools/refresh_data.py

No third-party dependencies — standard library only. Run it from the repo root
or from tools/; paths are resolved relative to this file.

Data © OpenStreetMap contributors, ODbL. Coverage is crowd-sourced and partial.
"""
import json, time, urllib.parse, urllib.request, collections, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
ENDPOINT = "https://overpass-api.de/api/interpreter"

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

# Vending machine value → simplified category. Anything in EXCL is dropped
# (parking/transit tickets, dog-poo bags, condoms, etc. — not "hydration").
DRINK = {'drinks','coffee','water','drinks;sweets','drinks;food','coffee;drinks','drinks;coffee','beer','wine','soft_drinks','juice'}
FOOD  = {'food','pizza','bread','ice_cream','potatoes','strawberries','fruit','milk','farm_products','sweets','food;drinks','eggs','vegetables','cheese','meat','honey','snacks','fries','pasta'}
EXCL  = {'parking_tickets','public_transport_tickets','excrement_bags','bicycle_tube','condoms','chemist','newspapers','fuel','flowers','stamps','gas','cigarettes','tickets','parking','elongated_coin','lockers'}


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


def coord(e):
    if 'lat' in e:   return e['lat'], e['lon']
    if 'center' in e: return e['center']['lat'], e['center']['lon']
    return None


def name_of(t):
    return (t.get('name') or t.get('brand') or t.get('operator') or '')[:60]


def vcat(v):
    parts = set(p.strip() for p in (v or '').replace('/', ';').split(';'))
    if parts & DRINK: return 'drinks'
    if parts & FOOD:  return 'food'
    if parts & EXCL:  return None
    return 'other'


def build():
    pois = []

    print("Fetching water points…")
    for e in overpass(WATER_Q)['elements']:
        c = coord(e)
        if not c: continue
        t = e.get('tags', {})
        sub = ('drinking_water' if t.get('amenity') == 'drinking_water'
               else 'water_tap' if t.get('man_made') == 'water_tap'
               else 'spring' if t.get('natural') == 'spring'
               else 'fountain' if t.get('amenity') == 'fountain'
               else 'drinking_water')
        pois.append([round(c[0], 5), round(c[1], 5), 'water', sub, name_of(t), t.get('opening_hours', '')])

    print("Fetching vending machines…")
    for e in overpass(VENDING_Q)['elements']:
        if 'lat' not in e: continue
        t = e.get('tags', {}); cat = vcat(t.get('vending', ''))
        if cat is None: continue
        pois.append([round(e['lat'], 5), round(e['lon'], 5), 'vending', cat, name_of(t), t.get('opening_hours', '')])

    print("Fetching shops & fuel stations…")
    for e in overpass(SHOPS_Q)['elements']:
        c = coord(e)
        if not c: continue
        t = e.get('tags', {})
        if t.get('amenity') == 'fuel':
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
