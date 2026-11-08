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
import urllib.parse

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
# Restoran olmayan yerler: adında bu kelimeler geçip restoran kelimesi geçmiyorsa elenir
NOT_RESTAURANT = re.compile(r"(wedding|düğün|dugun|nikah|balo salonu|davet salonu|organizasyon|çay bahçe|çay evi|"
                            r"çay ocağı|kahve|kahvehane|kıraathane|\bcafe\b|café|\bkafe|coffee|pastane|patisserie|"
                            r"fırın|unlu mamul|nargile|\bbar\b|\bpub\b|büfe|dondurma|tatlıcı|tatlı evi|baklava|künefe|"
                            r"lokum|şekerci|kuruyemiş|market|akaryakıt|petrol|\botel\b|hotel|pansiyon|kantin|yemekhane|"
                            r"yurdu|kafeterya)", re.I)
IS_RESTAURANT = re.compile(r"(rest[ao]?u?r?a?n?t|restoran|resto\b|lokanta|kebap|kebab|pide|lahmacun|balık|balik|"
                           r"ocakbaşı|ev yemek|sofra|mangal|köfte|kofte|döner|doner|mantı|ızgara|izgara|çorba|kokoreç|"
                           r"tantuni|hamsi|alabalık|kuymak|kahvaltı|yemek|aşevi|konağı|kebapçı|iskender|bistro)", re.I)
NON_FOOD_CUISINE = {"coffee_shop", "cafe", "ice_cream", "tea", "dessert", "cake", "donut", "bubble_tea",
                    "juice", "pastry", "bakery", "hookah"}
SHORE_PARK = re.compile(r"(sahil|kordon|rıhtım|iskele|marina|plaj|kumsal)", re.I)
PICNIC = re.compile(r"(mesire|piknik|orman parkı|kent ormanı|tabiat parkı|dinlenme alanı|rekreasyon)", re.I)
NATION_GARDEN = re.compile(r"(millet bahçesi|millet bahcesi)", re.I)
BOTANIC = re.compile(r"(botanik|arboretum)", re.I)
YAYLA = re.compile(r"\byayla(sı|si)?$|\byaylası\b", re.I)
CANYON = re.compile(r"kanyon", re.I)
GENERIC_NAME = re.compile(r"^(park|parkı|bahçe|piknik alanı|mesire alanı|seyir terası|kamp alanı|çocuk parkı|plaj|halk plajı|"
                          r"kale|kalesi|cami|camii|köprü|müze|mağara|şelale|yayla|kilise|türbe|höyük|ören yeri|harabe|kalıntı)$", re.I)
GENERIC_FOOD = re.compile(r"^(restaurant|restoran|restorant|lokanta|lokantası|kebap|kebapçı|pide|pideci|sofra|"
                          r"yemek|cafe restaurant|balık|balıkçı|ada|migros)$", re.I)


def is_real_restaurant(t, name):
    if GENERIC_FOOD.match(name.strip()) or len(name.strip()) < 3:
        return False
    cuis = {c.strip() for c in re.split(r"[;,]", (t.get("cuisine") or "").lower()) if c.strip()}
    if NOT_RESTAURANT.search(name) and not IS_RESTAURANT.search(name):
        return False
    if cuis and cuis <= NON_FOOD_CUISINE and not IS_RESTAURANT.search(name):
        return False
    return True


def commons_image(t):
    """OSM'deki image / wikimedia_commons etiketinden yalnızca Wikimedia Commons görsellerini al."""
    wc = (t.get("wikimedia_commons") or "").strip()
    if wc.lower().startswith("file:"):
        fn = wc[5:]
    else:
        img = (t.get("image") or "").strip()
        m = re.search(r"(?:commons\.wikimedia\.org/wiki/(?:File|Dosya):|upload\.wikimedia\.org/.+/)([^/?#]+\.(?:jpe?g|png|webp))", img, re.I)
        if not m:
            return ""
        fn = urllib.parse.unquote(m.group(1))
    if not re.search(r"\.(jpe?g|png|webp)$", fn, re.I) or re.search(r"(map|harita|logo|flag|locator|plan)", fn, re.I):
        return ""
    return "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(fn.replace(" ", "_")) + "?width=700"


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
    if not name or GENERIC_NAME.match(name.strip()):
        return None
    leisure, tourism, natural, historic = t.get("leisure"), t.get("tourism"), t.get("natural"), t.get("historic")
    if natural == "beach" or leisure == "beach_resort":
        return "Plaj / Koy"
    if t.get("place") and YAYLA.search(name):
        return "Yayla"
    if leisure in ("park", "garden") and NATION_GARDEN.search(name):
        return "Millet Bahçesi"
    if (leisure == "garden" or leisure == "park") and BOTANIC.search(name):
        return "Botanik Bahçesi"
    if tourism == "picnic_site" or (leisure in ("park", "nature_reserve", "recreation_ground") and PICNIC.search(name)):
        return "Mesire Alanı"
    if leisure == "nature_reserve" or t.get("boundary") == "national_park":
        return "Doğa Parkı"
    if leisure == "park" and SHORE_PARK.search(name):
        return "Sahil / Kordon"
    if tourism == "viewpoint":
        return "Seyir Noktası"
    if natural == "waterfall" or t.get("waterway") == "waterfall":
        return "Şelale"
    if natural == "cave_entrance":
        return "Mağara"
    if natural in ("valley", "gorge") and CANYON.search(name):
        return "Kanyon"
    if natural == "hot_spring" or (t.get("amenity") == "public_bath" and "kaplıca" in name.lower()):
        return "Kaplıca"
    if tourism == "museum":
        return "Müze"
    if tourism == "camp_site":
        return "Kamp Alanı"
    if historic in ("castle", "fort", "citadel") or t.get("castle_type"):
        return "Kale / Hisar"
    if historic == "archaeological_site":
        return "Antik Kent"
    if historic == "ruins":
        return "Tarihi Kalıntı"
    if historic == "aqueduct":
        return "Su Kemeri"
    if historic == "city_gate":
        return "Tarihi Kapı"
    if historic == "caravanserai" or t.get("building") == "caravanserai":
        return "Kervansaray / Han"
    if historic == "monastery":
        return "Tarihi Kilise"
    if historic == "bridge" or (t.get("bridge") and historic):
        return "Tarihi Köprü"
    if historic == "tomb" and (t.get("wikidata") or t.get("heritage")):
        return "Türbe / Külliye"
    if t.get("amenity") == "place_of_worship" and (t.get("heritage") or historic):
        return "Tarihi Camii" if t.get("religion") == "muslim" else "Tarihi Kilise"
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
            if not is_real_restaurant(tags, name):
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
                "img": commons_image(tags),
            })

    def node(self, n):
        if n.tags:
            t = {k: v for k, v in n.tags}
            if any(k in t for k in ("amenity", "natural", "tourism", "leisure", "waterway", "historic", "place")):
                self._emit("node", n.id, t, n.location.lat, n.location.lon)

    def way(self, w):
        t = {k: v for k, v in w.tags}
        if not any(k in t for k in ("amenity", "natural", "tourism", "leisure", "historic", "place", "building", "boundary")):
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
            if p["img"]:
                for lst in existing.values():
                    for x in lst:
                        if (x["id"] == p["id"] or (p["wikidata"] and x.get("wikidata") == p["wikidata"])) and not x.get("img"):
                            x["img"] = p["img"]
            continue
        loc = locate(polys, p["lon"], p["lat"])
        if not loc:
            continue
        il, slug, ilce = loc
        lst = existing.setdefault(slug, [])
        n = norm(p["ad"])
        def same(x):
            xn = norm(x["ad"])
            if not (xn == n or (len(n) > 5 and len(xn) > 5 and (n in xn or xn in n))):
                return False
            return haversine_m((x["lat"], x["lon"]), (p["lat"], p["lon"])) < 600
        dup = next((x for x in lst if same(x)), None)
        if dup:
            if p["img"] and not dup.get("img"):
                dup["img"] = p["img"]
            continue
        rec = {"id": p["id"], "ad": p["ad"], "il": il, "ilce": ilce, "lat": p["lat"], "lon": p["lon"],
               "kategori": p["kategori"], "img": p["img"]}
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
