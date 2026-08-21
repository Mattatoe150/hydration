#!/usr/bin/env python3
"""
Refresh the map data from OpenStreetMap (via the Overpass API), rebuild the
shared ../data/pois.js payload, and render both language pages.

    python3 tools/refresh_data.py            # fetch fresh data, then rebuild
    python3 tools/refresh_data.py --cached   # rebuild from tools/*.json snapshots

Standard library only. Data © OpenStreetMap contributors, ODbL. Coverage is
crowd-sourced and partial.
"""
import json, time, re, urllib.error, urllib.parse, urllib.request, collections, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
CACHED = "--cached" in sys.argv

WATER_Q = """[out:json][timeout:180];
area["ISO3166-1"="BE"][admin_level=2]->.be;
(
  node["amenity"="drinking_water"](area.be);
  node["man_made"="water_tap"]["drinking_water"!="no"](area.be);
  node["natural"="spring"]["drinking_water"="yes"](area.be);
  nwr["amenity"="fountain"]["drinking_water"="yes"](area.be);
  nwr["amenity"="water_point"](area.be);
  nwr["drinking_water:refill"="yes"](area.be);
  nwr["amenity"="toilets"]["drinking_water"="yes"](area.be);
  nwr["man_made"="water_well"]["drinking_water"="yes"](area.be);
);
out center;"""
# Deliberately NOT included: drinking_water=yes on camp_site / camp_pitch /
# caravan_site / shower / pub / cinema. The water is real but it sits inside a
# private or paying facility, and this map only promises publicly reachable spots.

# Water features that sit inside a cemetery. These are already picked up by the
# queries above (most Flemish cemeteries have an outdoor tap for grave flowers,
# and they're a well-known refill spot) — this query only tells us WHICH ones they
# are, so they can be labelled as such. Taps a mapper marked drinking_water=no are
# still excluded by the main query and stay excluded.
CEMETERY_Q = """[out:json][timeout:180];
area["ISO3166-1"="BE"][admin_level=2]->.be;
(way["landuse"="cemetery"](area.be); relation["landuse"="cemetery"](area.be);
 way["amenity"="grave_yard"](area.be); relation["amenity"="grave_yard"](area.be);)->.cem;
.cem map_to_area->.ca;
(
  node["man_made"="water_tap"](area.ca);
  node["amenity"="drinking_water"](area.ca);
  node["amenity"="water_point"](area.ca);
);
out ids center;"""

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
  nwr["shop"="beverages"](area.be);
  nwr["amenity"="fuel"](area.be);
);
out center;"""

# --- Vending: keep only DRINKS (primary) and SNACKS (optional). Bread & farm
#     produce are intentionally excluded — this map is about drinks, not groceries.
DRINK = {'drinks', 'coffee', 'water', 'soft_drinks', 'juice', 'cold_drinks', 'hot_drinks', 'milk_coffee'}
SNACK = {'sweets', 'ice_cream', 'food', 'pizza', 'snacks', 'chocolate', 'chips', 'confectionery', 'crisps'}
# everything else (bread, potatoes, farm_products, milk, eggs, fruit, vegetables,
# strawberries, cheese, meat, honey, flowers, parking_tickets, …) is dropped.


def overpass(query, rounds=3):
    """Try independent public Overpass instances without trusting partial data."""
    body = urllib.parse.urlencode({"data": query}).encode()
    for attempt in range(1, rounds + 1):
        for endpoint in ENDPOINTS:
            try:
                req = urllib.request.Request(
                    endpoint, data=body,
                    headers={"User-Agent": "ikhebdorst.be hydration map data refresh"})
                with urllib.request.urlopen(req, timeout=200) as response:
                    return json.loads(response.read().decode())
            except Exception as exc:
                host = urllib.parse.urlparse(endpoint).netloc
                print(f"  {host} attempt {attempt} failed ({exc})", file=sys.stderr)
        if attempt < rounds:
            print("  all Overpass endpoints failed; retrying in 30s…", file=sys.stderr)
            time.sleep(30)
    raise SystemExit("All Overpass API endpoints remained unavailable; existing pages were left untouched.")


def atomic_write(path, text):
    """Replace a generated file only after its complete contents are on disk."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def inline_json(value):
    """JSON safe inside an HTML script element, including hostile OSM labels."""
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'))
            .replace('&', r'\u0026').replace('<', r'\u003c').replace('>', r'\u003e')
            .replace('\u2028', r'\u2028').replace('\u2029', r'\u2029'))


def load(name, query):
    """Fetch from Overpass (and cache), or reuse tools/<name>.json with --cached."""
    cache = HERE / f"{name}.json"
    if CACHED and cache.exists():
        print(f"Using cached {cache.name}")
        return json.loads(cache.read_text())
    print(f"Fetching {name}…")
    data = overpass(query)
    # Overpass answers 200 with a "remark" when a query times out or runs out of
    # memory — the payload is then silently PARTIAL. Never build from that.
    remark = data.get('remark')
    if remark:
        raise SystemExit(f"Overpass returned a partial/failed result for {name}: {remark}")
    atomic_write(cache, json.dumps(data))
    return data


# Minimum plausible counts per category. The daily job runs unattended, so if a
# flaky Overpass response would shrink the map, fail loudly instead of shipping it.
MIN_EXPECTED = {'water': 900, 'vdrinks': 300, 'vsnacks': 250, 'shop': 5000, 'fuel': 200}
MAX_SHRINK = 0.85   # also fail if any category drops below 85% of what's live now


def previous_counts():
    """Category counts in the currently generated payload (empty on first build)."""
    generated = ROOT / "data" / "pois.js"
    # Backward-compatible fallback for the first build after the payload split.
    source = generated if generated.exists() else ROOT / "index.html"
    if not source.exists():
        return {}
    m = re.search(r'const POIS = (\[.*?\]);\n', source.read_text(), re.S)
    if not m:
        return {}
    try:
        return collections.Counter(p[2] for p in json.loads(m.group(1)))
    except Exception:
        return {}


def sanity_check(counts):
    prev = previous_counts()
    problems = []
    for cat, floor in MIN_EXPECTED.items():
        got = counts.get(cat, 0)
        if got < floor:
            problems.append(f"{cat}: {got} < absolute minimum {floor}")
        was = prev.get(cat, 0)
        if was and got < was * MAX_SHRINK:
            problems.append(f"{cat}: {got} is under {int(MAX_SHRINK*100)}% of the previous {was}")
    if problems:
        raise SystemExit("Refusing to write generated map files — the new data looks wrong:\n  - "
                         + "\n  - ".join(problems)
                         + "\n(Overpass may have returned partial data. Re-run later.)")
    if prev:
        print("Sanity check passed (previous: " + ", ".join(f"{k}={v}" for k, v in sorted(prev.items())) + ")")


def coord(e):
    if 'lat' in e:   return e['lat'], e['lon']
    if 'center' in e: return e['center']['lat'], e['center']['lon']
    return None


def name_of(t):
    return (t.get('name') or t.get('brand') or t.get('operator') or '')[:60]


# --- "do I have to walk into somewhere?" ---------------------------------
# Cycling kit + someone's restaurant is an awkward combination, so flag the spots
# that sit indoors or behind a customers-only door. Belgium has millions of
# building polygons, so testing containment against them blows Overpass's memory
# limit; these tags are what can actually be relied on.
RESTRICTED_ACCESS = {'customers', 'private', 'permit', 'no'}

def needs_entry(t):
    if t.get('indoor') in ('yes', 'room'):
        return True
    if t.get('access') in RESTRICTED_ACCESS:
        return True
    if t.get('drinking_water:refill') == 'yes':
        host = t.get('shop') or t.get('amenity') or t.get('tourism')
        if host and host not in ('drinking_water', 'water_point', 'fountain'):
            return True          # the refill tap lives inside that venue
    return False


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


EN = {
    "__LANG__": "en", "__CANONICAL__": "https://ikhebdorst.be/",
    "__OGLOCALE__": "en_GB", "__OGALT__": "nl_BE",
    "__OTHERURL__": "/nl/", "__OTHERLANG__": "nl",
    "__LANGSWLABEL__": "NL", "__LANGSWTITLE__": "Lees deze pagina in het Nederlands",
    "__SITENAME__": "I'm thirsty", "__ALTNAME__": "Hydration Map Belgium",
    "__LDDESC__": "Map of free drinking water, public taps, fountains, drinks machines and open shops across Belgium.",
    "__FEATURES__": ["Free drinking water and public taps", "Drinks vending machines",
                      "Open shops and fuel stations with a shop", "Shows what is open right now",
                      "Works on mobile and finds your location"],
    "__ABOUTH__": "About this map",
    "__ABOUT1__": "<b>I'm thirsty</b> shows where to find <b>free drinking water</b> in Belgium, "
                  "or somewhere to buy a drink: public <b>drinking fountains</b> and <b>taps</b> "
                  "(including ones run by De Watergroep, water-link, Farys and Pidpa), water points in "
                  "NMBS/SNCB stations, cemetery taps, <b>vending machines</b>, night shops, supermarkets "
                  "and fuel stations with a shop. It also shows <b>what is open right now</b>, including "
                  "Sundays and Belgian public holidays — handy in a heatwave, on the bike, or just out and about.",
    "__ABOUT2__": "Free, no ads, no account. The data comes from OpenStreetMap and is refreshed every day. "
                  "Missing a spot? Add it yourself with <b>➕ Add / fix</b>.",
}


def render(template, placeholders, pairs=()):
    """Render one language and fail if its translation has drifted."""
    out = template
    # Longest source first because shorter phrases may be substrings of longer ones.
    for find, repl in sorted(pairs, key=lambda pair: -len(pair[0])):
        if find not in out:
            raise SystemExit(f"Translation out of date — this text is no longer in the template:\n  {find[:90]}")
        out = out.replace(find, repl)
    for key, value in placeholders.items():
        out = out.replace(key, json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value)
    left = re.findall(r'__[A-Z0-9]+__', out)
    if left:
        raise SystemExit(f"Unfilled placeholders: {sorted(set(left))}")
    return out


def build():
    pois = []

    # Coordinates of water features that lie inside a cemetery, for labelling.
    cemetery = set()
    for e in load('cemetery', CEMETERY_Q)['elements']:
        c = coord(e)
        if c: cemetery.add((round(c[0], 5), round(c[1], 5)))
    print(f"  ({len(cemetery)} of them are cemetery taps)")

    for e in load('water', WATER_Q)['elements']:
        c = coord(e)
        if not c: continue
        t = e.get('tags', {})
        sub = ('drinking_water' if t.get('amenity') == 'drinking_water'
               else 'water_tap' if t.get('man_made') == 'water_tap'
               else 'spring' if t.get('natural') == 'spring'
               else 'fountain' if t.get('amenity') == 'fountain'
               else 'water_point' if t.get('amenity') == 'water_point'
               else 'toilets' if t.get('amenity') == 'toilets'
               else 'well' if t.get('man_made') == 'water_well'
               else 'refill' if t.get('drinking_water:refill') == 'yes'
               else 'drinking_water')
        # A refill point is the notable thing about a venue, whatever it also is.
        if t.get('drinking_water:refill') == 'yes' and sub in ('drinking_water', 'toilets'):
            sub = 'refill'
        # Being in a cemetery is the useful thing to know — say so.
        if sub in ('drinking_water', 'water_tap', 'water_point') and (round(c[0], 5), round(c[1], 5)) in cemetery:
            sub = 'cemetery'
        pois.append([round(c[0], 5), round(c[1], 5), 'water', sub, name_of(t), t.get('opening_hours', ''), int(needs_entry(t))])

    for e in load('vending', VENDING_Q)['elements']:
        if 'lat' not in e: continue
        t = e.get('tags', {}); cat = vcat(t.get('vending', ''))
        if cat is None: continue
        sub = 'drinks' if cat == 'vdrinks' else 'snacks'
        pois.append([round(e['lat'], 5), round(e['lon'], 5), cat, sub, name_of(t), t.get('opening_hours', ''), int(needs_entry(t))])

    for e in load('shops', SHOPS_Q)['elements']:
        c = coord(e)
        if not c: continue
        t = e.get('tags', {})
        if t.get('amenity') == 'fuel':
            if not fuel_has_shop(t):
                continue
            cat, sub = 'fuel', 'fuel'
        elif t.get('shop') in ('convenience', 'supermarket', 'kiosk', 'beverages'):
            cat, sub = 'shop', t['shop']
        else:
            continue
        pois.append([round(c[0], 5), round(c[1], 5), cat, sub, name_of(t), t.get('opening_hours', ''), int(needs_entry(t))])

    # A feature can match more than one query (e.g. a refill point that is also a
    # tagged drinking-water node) — keep one pin per place+category.
    seen, unique = set(), []
    for p in pois:
        key = (p[0], p[1], p[2])
        if key in seen: continue
        seen.add(key); unique.append(p)
    if len(unique) != len(pois):
        print(f"Deduplicated {len(pois)-len(unique)} overlapping points.")
    pois = unique

    counts = collections.Counter(p[2] for p in pois)
    print(f"\nTOTAL POIs: {len(pois)}")
    print(dict(counts))
    sanity_check(counts)

    data = inline_json(pois)
    tpl = (HERE / "index_template.html").read_text()

    nl = json.loads((HERE / "i18n_nl.json").read_text())
    nl_dir = ROOT / "nl"; nl_dir.mkdir(exist_ok=True)
    data_dir = ROOT / "data"; data_dir.mkdir(exist_ok=True)
    # Render and validate every language before replacing any public file.
    rendered_en = render(tpl, EN)
    rendered_nl = render(tpl, nl["placeholders"], nl["pairs"])

    # keep the sitemap's lastmod honest — the data really did change today
    sm = ROOT / "sitemap.xml"
    rendered_sitemap = None
    if sm.exists():
        today = time.strftime("%Y-%m-%d", time.gmtime())
        rendered_sitemap = re.sub(r"<lastmod>[^<]*</lastmod>", f"<lastmod>{today}</lastmod>", sm.read_text())

    # Write the shared payload first. Existing pages can safely use either the
    # previous or new payload because its compact schema is stable.
    atomic_write(data_dir / "pois.js", "/* Generated from OpenStreetMap; do not edit. */\nconst POIS = " + data + ";\n")
    atomic_write(ROOT / "index.html", rendered_en)
    atomic_write(nl_dir / "index.html", rendered_nl)
    if rendered_sitemap is not None:
        atomic_write(sm, rendered_sitemap)
    print(f"Wrote {ROOT / 'index.html'} ({round(len(data)/1024)} KB of data).")
    print(f"Wrote {data_dir / 'pois.js'} (shared by both languages).")
    print(f"Wrote {nl_dir / 'index.html'} (Dutch, {len(nl['pairs'])} strings translated).")
    if rendered_sitemap is not None:
        print(f"Updated sitemap lastmod to {today}.")


if __name__ == "__main__":
    build()
