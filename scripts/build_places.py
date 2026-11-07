#!/usr/bin/env python3
"""
build_places.py — 81 il için turistik mekan verisini Overpass'tan BİR KEZ çeker
ve site için il başına küçük, hazır JSON dosyaları üretir.

Çıktı:
  data/places/<il-slug>.json   -> [ {id, ad, il, ilce, lat, lon, kategori, wiki, wikidata, image}, ... ]
  data/places/index.json       -> { "<il>": {"slug": ..., "count": ...}, ... }

Özellikler:
  - app.js ile aynı Overpass sorgusu ve aynı Türkçe/kategori filtreleri
  - İl sınırı + ilçe ataması tr_*_simplified.geojson ile çevrimdışı (nokta-poligon)
  - Kaldığı yerden devam eder (hazır dosyası olan illeri atlar; --force ile yeniden)
  - Sadece standart kütüphane kullanır

Kullanım:
  python scripts/build_places.py               # eksik illeri çek
  python scripts/build_places.py --force       # hepsini yeniden çek
  python scripts/build_places.py --only trabzon kilis
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROV_FILE = os.path.join(ROOT, "assets", "geo", "tr_provinces_simplified.geojson")
DIST_FILE = os.path.join(ROOT, "assets", "geo", "tr_districts_simplified.geojson")
OUT_DIR = os.path.join(ROOT, "data", "places")

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
USER_AGENT = "NereyeGidilir-DataBuilder/1.0 (static dataset build)"

# app.js ile aynı etiketler (sıradan "park" bilinçli olarak çıkarıldı)
SELECTORS = [
    ('node', 'tourism', 'museum'), ('way', 'tourism', 'museum'),
    ('node', 'tourism', 'attraction'), ('way', 'tourism', 'attraction'),
    ('node', 'tourism', 'artwork'), ('node', 'tourism', 'viewpoint'),
    ('node', 'tourism', 'theme_park'),
    ('node', 'historic', 'castle'), ('way', 'historic', 'castle'),
    ('node', 'historic', 'ruins'), ('way', 'historic', 'ruins'),
    ('node', 'historic', 'archaeological_site'), ('way', 'historic', 'archaeological_site'),
    ('node', 'historic', 'monument'), ('way', 'historic', 'monument'),
    ('node', 'historic', 'memorial'),
    ('node', 'historic', 'fort'), ('way', 'historic', 'fort'),
    ('node', 'historic', 'city_gate'), ('way', 'historic', 'city_gate'),
    ('node', 'historic', 'mosque'), ('way', 'historic', 'mosque'),
    ('node', 'historic', 'church'), ('way', 'historic', 'church'),
    ('node', 'natural', 'waterfall'), ('node', 'natural', 'cave_entrance'),
    ('node', 'natural', 'peak'),
    ('node', 'natural', 'beach'), ('way', 'natural', 'beach'),
    ('node', 'natural', 'hot_spring'),
    ('node', 'leisure', 'nature_reserve'), ('way', 'leisure', 'nature_reserve'),
]

NON_LATIN = re.compile(r"[\u0600-\u06FF\u0400-\u04FF\u4E00-\u9FFF\u3040-\u30FF\uFF00-\uFFEF]")
TR_CHARS = re.compile(r"[ğşıçöüĞŞİÇÖÜ]")
PURE_ASCII = re.compile(r"^[a-zA-Z0-9 \-\.,/()'\"]+$")
ENG_WORDS = re.compile(
    r"\b(statue|lake|river|mountain|mount|peak|ruins|cave|beach|bay|island|valley|forest|church|"
    r"temple|bridge|gate|road|ancient|national|reserve|nature|hill|spring|tower|wall|palace|shrine)\b",
    re.I,
)
ONLY_DIGITS = re.compile(r"^[\d\s.,\-]+$")


# ---------------- Geometri ----------------
def _rings(geom):
    """Polygon/MultiPolygon -> [ [outer, hole1, ...], ... ]"""
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def _bbox(polys):
    xs, ys = [], []
    for poly in polys:
        for x, y in poly[0]:
            xs.append(x)
            ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys))


def _in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def _in_polys(x, y, polys):
    for poly in polys:
        if _in_ring(x, y, poly[0]) and not any(_in_ring(x, y, h) for h in poly[1:]):
            return True
    return False


class Region:
    def __init__(self, name, province, geom):
        self.name = name
        self.province = province
        self.polys = _rings(geom)
        self.bbox = _bbox(self.polys)
        bx = self.bbox
        self.center = ((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2)

    def contains(self, lon, lat):
        b = self.bbox
        if lon < b[0] or lon > b[2] or lat < b[1] or lat > b[3]:
            return False
        return _in_polys(lon, lat, self.polys)


def load_geo():
    with open(PROV_FILE, encoding="utf-8") as f:
        prov = json.load(f)
    with open(DIST_FILE, encoding="utf-8") as f:
        dist = json.load(f)
    provinces = []
    for ft in prov["features"]:
        p = ft["properties"]
        r = Region(p["name_tr"], p["name_tr"], ft["geometry"])
        r.slug = p["slug"]
        provinces.append(r)
    districts = [
        Region(ft["properties"]["name_tr"], ft["properties"]["province_tr"], ft["geometry"])
        for ft in dist["features"]
    ]
    return provinces, districts


def locate(lon, lat, province, districts):
    """Mekanın ilçesini bul. Bu ile ait değilse None döner."""
    for d in districts:
        if d.contains(lon, lat):
            return d.name if d.province == province.name else None
    # Sadeleştirilmiş sınır boşlukları (kıyı, sınır çizgisi):
    # il poligonu içindeyse o ilin en yakın ilçesi; değilse çok yakınsa en yakın ilçe
    in_prov = province.contains(lon, lat)
    best, best_d = None, 1e9
    for d in districts:
        if in_prov and d.province != province.name:
            continue
        dd = (d.center[0] - lon) ** 2 + (d.center[1] - lat) ** 2
        if dd < best_d:
            best, best_d = d, dd
    if best and best.province == province.name and (in_prov or best_d < 0.05):
        return best.name
    return None


# ---------------- Overpass ----------------
def build_query(bbox):
    minlon, minlat, maxlon, maxlat = bbox
    body = "\n".join(f'  {t}["{k}"="{v}"];' for t, k, v in SELECTORS)
    body += '\n  node["amenity"="place_of_worship"]["historic"];'
    body += '\n  way["amenity"="place_of_worship"]["historic"];'
    return (
        f"[out:json][timeout:120][bbox:{minlat},{minlon},{maxlat},{maxlon}];\n"
        f"(\n{body}\n);\nout center tags;"
    )


def fetch_overpass(query):
    data = urllib.parse.urlencode({"data": query}).encode()
    last_err = None
    for attempt in range(3):
        for url in ENDPOINTS:
            try:
                req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=180) as res:
                    return json.loads(res.read().decode("utf-8"))
            except Exception as e:  # noqa: BLE001
                last_err = e
                print(f"    ! {url.split('/')[2]} başarısız: {e}")
                time.sleep(3)
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Tüm sunucular başarısız: {last_err}")


# ---------------- Dönüştürme (app.js ile aynı mantık) ----------------
def category(t):
    tour, hist, nat, lei, am, rel = (t.get(k) for k in ("tourism", "historic", "natural", "leisure", "amenity", "religion"))
    if tour == "museum": return "Müze"
    if tour == "attraction": return "Turistik Alan"
    if tour == "viewpoint": return "Seyir Noktası"
    if tour == "artwork": return "Sanat Eseri"
    if tour == "theme_park": return "Eğlence Parkı"
    if hist in ("castle", "fort"): return "Kale / Hisar"
    if hist in ("ruins", "archaeological_site"): return "Antik Kent"
    if hist in ("monument", "memorial"): return "Anıt"
    if hist == "city_gate": return "Tarihi Kapı"
    if hist == "mosque" or (am == "place_of_worship" and rel == "muslim"): return "Tarihi Camii"
    if hist == "church" or (am == "place_of_worship" and rel == "christian"): return "Tarihi Kilise"
    if nat == "waterfall": return "Şelale"
    if nat == "cave_entrance": return "Mağara"
    if nat == "peak": return "Dağ Zirvesi"
    if nat == "beach": return "Plaj / Koy"
    if nat == "hot_spring": return "Kaplıca"
    if lei == "nature_reserve": return "Doğa Parkı"
    return "Diğer"


def pick_name(t):
    name_tr, name_gen, name_en = t.get("name:tr"), t.get("name"), t.get("name:en")
    name = (name_tr or name_gen or "").strip()
    if not name or NON_LATIN.search(name) or ONLY_DIGITS.match(name):
        return None
    if not name_tr:
        if name_en and name_gen == name_en:
            return None
        if not TR_CHARS.search(name_gen or "") and PURE_ASCII.match(name_gen or ""):
            return None
        if ENG_WORDS.search(name_gen or ""):
            return None
    return name


def convert(elements, province, districts):
    out, seen = [], set()
    for el in elements:
        t = el.get("tags") or {}
        name = pick_name(t)
        if not name:
            continue
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if not lat or not lon:
            continue
        ilce = locate(lon, lat, province, districts)
        if ilce is None:  # bbox içinde ama komşu ilde
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        rec = {
            "id": f"{el['type']}:{el['id']}",
            "ad": name,
            "il": province.name,
            "ilce": ilce,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "kategori": category(t),
        }
        if t.get("wikipedia"): rec["wiki"] = t["wikipedia"]
        if t.get("wikidata"): rec["wikidata"] = t["wikidata"]
        img = t.get("image") or t.get("image:0")
        if img: rec["image"] = img
        out.append(rec)
    # Wikipedia/Wikidata bağlantısı olanlar (genelde daha önemli) önce gelsin
    out.sort(key=lambda r: (0 if ("wiki" in r or "wikidata" in r) else 1, r["ad"]))
    return out


def main():
    args = sys.argv[1:]
    force = "--force" in args
    only = None
    if "--only" in args:
        only = set(args[args.index("--only") + 1:])

    os.makedirs(OUT_DIR, exist_ok=True)
    provinces, districts = load_geo()
    provinces.sort(key=lambda p: p.slug)
    failed = []

    for i, prov in enumerate(provinces, 1):
        if only and prov.slug not in only:
            continue
        path = os.path.join(OUT_DIR, f"{prov.slug}.json")
        if os.path.exists(path) and not force:
            print(f"[{i:02d}/81] {prov.name}: zaten hazır, atlanıyor")
            continue
        print(f"[{i:02d}/81] {prov.name}: Overpass sorgulanıyor...", flush=True)
        t0 = time.time()
        try:
            raw = fetch_overpass(build_query(prov.bbox))
            places = convert(raw.get("elements", []), prov, districts)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(places, f, ensure_ascii=False, separators=(",", ":"))
            print(f"    ✓ {len(places)} mekan ({time.time() - t0:.1f} sn)", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"    ✗ HATA: {e}", flush=True)
            failed.append(prov.name)
        time.sleep(2)

    # index.json
    index = {}
    for prov in provinces:
        path = os.path.join(OUT_DIR, f"{prov.slug}.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                index[prov.name] = {"slug": prov.slug, "count": len(json.load(f))}
    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)

    total = sum(v["count"] for v in index.values())
    print(f"\nTamamlandı: {len(index)}/81 il, toplam {total} mekan.")
    if failed:
        print("Başarısız iller (tekrar çalıştırın):", ", ".join(failed))


if __name__ == "__main__":
    main()
