#!/usr/bin/env python3
"""
build_osm_extras.py — Türkiye OpenStreetMap dosyasından (turkey-latest.osm.pbf) iki şey üretir:

  1) data/food/{il-slug}.json   → "Yöre Sofrası" restoran listeleri (il/ilçe bazında, öne çıkanlar)
  2) data/places/*.json eklemeleri → Wikidata'da olmayan plaj, sahil parkı/kordon, seyir noktası,
                                      şelale, mağara, kaplıca kayıtları (ör. Of sahili)

Canlı Overpass sunucuları sık sık aşırı yüklü olduğu için veri derleme anında bir kez çıkarılır;
site çalışırken OSM'e istek atılmaz. Veri © OpenStreetMap katkıcıları (ODbL).

Kullanım:
  pip install osmium
  curl -L -o turkey.osm.pbf https://download.openstreetmap.fr/extracts/europe/turkey-latest.osm.pbf
  python scripts/build_osm_extras.py turkey.osm.pbf
"""
import json
import os
import re
import sys

import osmium

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_wikidata_enrich import load_districts, locate, haversine_m, norm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES_DIR = os.path.join(ROOT, "data", "places")
FOOD_DIR = os.path.join(ROOT, "data", "food")
FOOD_PER_DISTRICT = 25

REGIONAL_CUISINES = {"regional", "local", "turkish", "kebab", "pide", "lahmacun", "fish", "seafood", "meat",
                     "grill", "barbecue", "kofte", "köfte", "homestyle", "home_cooking", "ottoman",
                     "breakfast", "soup", "doner", "döner", "steak_house"}
REGIONAL_NAME = re.compile(r"(lokanta|kebap|kebab|pide|balık|balik|ocakbaşı|köfte|kofte|sofra|konağı|konak|mantı|"
                           r"hamsi|kuymak|muhlama|kahvaltı|ev yemek|etli ekmek|tantuni|çorba|pilav|kokoreç|iskender)", re.I)
NOT_RESTAURANT = re.compile(r"(wedding|düğün|dugun|nikah|balo salonu|davet salonu|organizasyon)", re.I)
SHORE_PARK = re.compile(r"(sahil|kordon|rıhtım|iskele|marina|plaj|kumsal|mesire)", re.I)


def food_score(t):
    s = 0.0
    if t.get("wikidata") or t.get("wikipedia"):
        s += 8
    cuis = [c.strip() for c in re.split(r"[;,]", (t.get("cuisine") or "").lower()) if c.strip()]
    if any(c in REGIONAL_CUISINES for c in cuis):
        s += 3
    if REGIONAL_NAME.search(t.get("name") or ""):
        s += 2
    for k, w in (("opening_hours", 1), ("website", 1), ("contact:website", 1), ("phone", 0.5),
                 ("contact:phone", 0.5), ("addr:street", 0.5)):
        if t.get(k):
            s += w
    if t.get("brand") or t.get("brand:wikidata"):
        s -= 3
    return s


def place_category(t):
    name = t.get("name:tr") or t.get("name") or ""
    if t.get("natural") == "beach" or t.get("leisure") == "beach_resort":
        return "Plaj / Koy"
    if t.get("leisure") == "park" and SHORE_PARK.search(name):
        return "Sahil / Kordon"
    if t.get("tourism") == "viewpoint":
        return "Seyir Noktası"
    if t.get("natural") == "waterfall" or t.get("waterway") == "waterfall":
        return "Şelale"
    if t.get("natural") == "cave_entrance":
        return "Mağara"
    if t.get("natural") == "hot_spring" or t.get("amenity") == "public_bath" and "kaplıca" in name.lower():
        return "Kaplıca"
    return None


class Handler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.food = []
        self.places = []

    def _emit(self, kind, oid, tags, lat, lon):
        name = tags.get("name:tr") or tags.get("name")
        if not name or lat is None:
            return
        if tags.get("amenity") == "restaurant":
            if NOT_RESTAURANT.search(name):
                return
            self.food.append({
                "n": name, "lat": round(lat, 5), "lon": round(lon, 5),
                "c": tags.get("cuisine", ""), "s": " ".join(x for x in (tags.get("addr:street"), tags.get("addr:housenumber")) if x),
                "p": tags.get("phone") or tags.get("contact:phone") or "",
                "_score": food_score(tags),
            })
            return
        cat = place_category(tags)
        if cat:
            self.places.append({
                "id": f"{kind}:{oid}", "ad": name, "lat": round(lat, 6), "lon": round(lon, 6),
                "kategori": cat, "wikidata": tags.get("wikidata", ""), "wp": tags.get("wikipedia", ""),
            })

    def node(self, n):
        if n.tags:
            t = {k: v for k, v in n.tags}
            if "amenity" in t or "natural" in t or "tourism" in t or "leisure" in t or "waterway" in t:
                self._emit("node", n.id, t, n.location.lat, n.location.lon)

    def way(self, w):
        t = {k: v for k, v in w.tags}
        if not ("amenity" in t or "natural" in t or "tourism" in t or "leisure" in t):
            return
        if not (t.get("amenity") == "restaurant" or place_category(t)):
            return
        pts = [(nd.lat, nd.lon) for nd in w.nodes if nd.location.valid()]
        if not pts:
            return
        lat = sum(p[0] for p in pts) / len(pts)
        lon = sum(p[1] for p in pts) / len(pts)
        self._emit("way", w.id, t, lat, lon)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    h = Handler()
    h.apply_file(sys.argv[1], locations=True, idx="flex_mem")
    print(f"OSM: {len(h.food)} restoran, {len(h.places)} doğa/sahil kaydı")
    polys = load_districts()

    # ---- 1) Restoranlar ----
    os.makedirs(FOOD_DIR, exist_ok=True)
    by_prov = {}
    for r in h.food:
        loc = locate(polys, r["lon"], r["lat"])
        if not loc:
            continue
        il, slug, ilce = loc
        r["i"] = ilce
        by_prov.setdefault(slug, {}).setdefault(ilce, []).append(r)
    total = 0
    for slug, districts in by_prov.items():
        out = []
        for ilce, lst in districts.items():
            seen = set()
            lst.sort(key=lambda r: (-r["_score"], r["n"]))
            picked = []
            for r in lst:
                k = norm(r["n"])
                if k in seen:
                    continue
                seen.add(k)
                picked.append(r)
                if len(picked) >= FOOD_PER_DISTRICT:
                    break
            for r in picked:
                r["sc"] = round(r.pop("_score"), 1)
                for k in ("c", "s", "p"):
                    if not r[k]:
                        r.pop(k)
            out.extend(picked)
            for r in lst:
                r.pop("_score", None)
        out.sort(key=lambda r: (-r["sc"], r["n"]))
        counts = {ilce: len(lst) for ilce, lst in districts.items()}
        with open(os.path.join(FOOD_DIR, slug + ".json"), "w", encoding="utf-8") as f:
            json.dump({"counts": counts, "items": out}, f, ensure_ascii=False, separators=(",", ":"))
        total += len(out)
    print(f"Restoran dosyaları: {len(by_prov)} il, {total} öne çıkan restoran")

    # ---- 2) Eksik doğa / sahil yerleri ----
    existing = {}
    for fn in os.listdir(PLACES_DIR):
        if fn.endswith(".json") and not fn.startswith(("index", "_")):
            existing[fn[:-5]] = json.load(open(os.path.join(PLACES_DIR, fn), encoding="utf-8"))
    known_ids = {p["id"] for lst in existing.values() for p in lst}
    known_qids = {p.get("wikidata") for lst in existing.values() for p in lst if p.get("wikidata")}
    added = 0
    for p in h.places:
        if p["id"] in known_ids or (p["wikidata"] and p["wikidata"] in known_qids):
            continue
        loc = locate(polys, p["lon"], p["lat"])
        if not loc:
            continue
        il, slug, ilce = loc
        lst = existing.setdefault(slug, [])
        n = norm(p["ad"])
        if any(norm(x["ad"]) == n and haversine_m((x["lat"], x["lon"]), (p["lat"], p["lon"])) < 500 for x in lst):
            continue
        rec = {"id": p["id"], "ad": p["ad"], "il": il, "ilce": ilce, "lat": p["lat"], "lon": p["lon"],
               "kategori": p["kategori"], "img": ""}
        if p["wikidata"]:
            rec["wikidata"] = p["wikidata"]
        if re.match(r"^[a-z]{2,3}:.+", p["wp"] or ""):
            rec["wp"] = rec["wiki"] = p["wp"]
        lst.append(rec)
        known_ids.add(p["id"])
        added += 1
    index_path = os.path.join(PLACES_DIR, "index.json")
    index = json.load(open(index_path, encoding="utf-8"))
    for slug, lst in existing.items():
        with open(os.path.join(PLACES_DIR, slug + ".json"), "w", encoding="utf-8") as f:
            json.dump(lst, f, ensure_ascii=False, separators=(",", ":"))
        for il, v in index.items():
            if v.get("slug") == slug:
                v["count"] = len(lst)
                v["with_img"] = sum(1 for x in lst if (x.get("img") or "").strip())
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    print(f"Yeni plaj/sahil/doğa kaydı: {added}")


if __name__ == "__main__":
    main()
