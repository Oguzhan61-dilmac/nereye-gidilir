#!/usr/bin/env python3
"""
build_images.py — data/places/*.json içindeki her mekan için SADECE o mekana ait
olduğu doğrulanabilen fotoğrafı bulur ve "img" alanına yazar. Wikipedia makalesi
bulunursa "wp" alanına (ör. "tr:Sümela Manastırı") yazar (açıklama için).

Kabul edilen kaynaklar (öncelik sırasıyla):
  1. OSM'de mekana bağlı Wikidata kaydının P18 (resim) özelliği veya P373 Commons kategorisi
  2. OSM'de veya Wikidata'da mekana bağlı Wikipedia makalesinin ana görseli
  3. OSM image etiketi (doğrudan Wikimedia Commons resim dosyası ise)
  4. Türkçe Wikipedia'da başlık eşleşmesi (KOORDİNAT <= 15 km VEYA makale özeti/başlığında
     aynı il/ilçe adı geçiyorsa doğrulanır; başka ildeki benzer isimli yerler reddedilir)
  5. Türkçe Wikipedia'da mekanın koordinatına yakın (<= 8 km) VE adı mekan adıyla
     eşleşen makalenin ana görseli
  6. Wikimedia Commons'ta dosya başlığında (intitle) bizzat mekanın tam adı ve il/ilçe
     adı geçen gerçek fotoğraf dosyaları (.jpg/.png/.webp)
Bunların hiçbiri yoksa mekana fotoğraf KONMAZ (yanlış fotoğraf yerine fotoğrafsız).
Harita, bayrak, logo, arma, plan, PDF/gazete kupürü gibi görseller elenir.
"""
import json
import math
import os
import re
import sys
import time
import urllib.parse
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES_DIR = os.path.join(ROOT, "data", "places")
DONE_FILE = os.path.join(PLACES_DIR, "_images_done.json")
UA = "NereyeGidilir/1.0 (static dataset build; contact: github.com/Oguzhan61-dilmac)"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA})

BAD_IMG = re.compile(
    r"(\.(svg|pdf|djvu|webm|ogv|ogg|gif|tif|tiff)$|map|harita|locator|location|konum|"
    r"flag|bayrak|logo|arma|coat[_ ]of[_ ]arms|seal|mühür|icon|signature|imza|diagram|"
    r"plan[_ .]|blank|silhouette|milliyet|cumhuriyet|vakit|gazete|newspaper|stamp|pullu)",
    re.I,
)

GENERIC_NAMES = {
    "şehitlik", "atatürk anıtı", "atatürk heykeli", "atatürk büstü", "kilise kalıntısı",
    "cami", "camii", "çeşme", "köprü", "kale", "tepe", "anıt", "heykel", "müze",
    "yeniçeri", "yunus balıkları", "meçhul asker anıtı", "büyük sanayi sitesi",
    "seyir terası", "piknik alanı", "mesire alanı", "plaj", "halk plajı",
}

STRIP_SUFFIXES = [
    " tabiat parkı", " millî parkı", " milli parkı", " seyir terası",
    " seyir noktası", " ören yeri", " antik kenti", " aile plajı",
]


def http_json(url, params=None, tries=5):
    for i in range(tries):
        try:
            r = SESSION.get(url, params=params, timeout=30)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After") or 0) or 10 * (i + 1)
                print(f"    … hız sınırı, {min(wait, 60)} sn bekleniyor", flush=True)
                time.sleep(min(wait, 60))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                print(f"    ! istek başarısız: {e}", flush=True)
                return None
            time.sleep(1.5 * (i + 1))
    return None


def commons_url(filename):
    fn = filename.strip()
    fn = re.sub(r"^(?:File|Dosya):", "", fn, flags=re.I).replace(" ", "_")
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(fn)}?width=700"


def good_file(name):
    if not name:
        return False
    return not BAD_IMG.search(name) and bool(re.search(r"\.(jpe?g|png|webp)$", name, re.I))


# ---------- Ad normalizasyonu ----------
def norm(s):
    if not s:
        return ""
    s = s.replace("İ", "i").replace("I", "ı").lower()
    s = s.replace("â", "a").replace("î", "i").replace("û", "u")
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^\wçğıöşü ]", " ", s)
    s = re.sub(r"\bcamisi\b", "camii", s)
    s = re.sub(r"\bcami\b", "camii", s)
    return re.sub(r"\s+", " ", s).strip()


def base_variants(place_name):
    """Mekan adının kendisi ve varsa 'Tabiat Parkı' vb. sonekleri atılmış kök adı."""
    raw = place_name.strip()
    out = [raw]
    low = raw.replace("İ", "i").replace("I", "ı").lower()
    for suf in STRIP_SUFFIXES:
        if low.endswith(suf) and len(raw) > len(suf) + 3:
            out.append(raw[: len(raw) - len(suf)].strip())
    if low.startswith("trabzonspor ") and len(raw) > 15:
        out.append(raw[12:].strip())
    return out


def names_match(place_name, title, il="", ilce=""):
    # Wikipedia başlığındaki ", İlçe" veya "(İl)" kısmını ayır
    t_clean = re.sub(r"\s*\(.*?\)\s*$", "", title or "")
    if "," in t_clean:
        parts = [p.strip() for p in t_clean.split(",", 1)]
        # Eğer virgülden sonrası il veya ilçe ise başlığın kök kısmını al
        if norm(parts[1]) in {norm(il), norm(ilce)} and norm(parts[1]):
            t_clean = parts[0]

    b = norm(t_clean)
    if not b or b in GENERIC_NAMES:
        return False

    for cand in base_variants(place_name):
        a = norm(cand)
        if not a or a in GENERIC_NAMES:
            continue
        if a == b:
            return True
        # İl adıyla başlayan/biten tam eşleşme: "Trabzon Ayasofya Camii" ~ "Ayasofya Camii"
        il_n = norm(il)
        if il_n and (b == f"{il_n} {a}" or b == f"{a} {il_n}" or a == f"{il_n} {b}"):
            return True
        if len(a.split()) >= 2 and (b.endswith(" " + a) or b.startswith(a + " ")):
            return True
        if len(b.split()) >= 2 and (a.endswith(" " + b) or a.startswith(b + " ")):
            return True
    return False


def _dist_m(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------- 1) Wikidata P18 (toplu) ----------
def wikidata_images(qids):
    out = {}
    qids = sorted(set(q for q in qids if re.match(r"^Q\d+$", str(q))))
    for i in range(0, len(qids), 50):
        chunk = qids[i:i + 50]
        d = http_json(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbgetentities",
                "format": "json",
                "props": "claims|sitelinks",
                "sitefilter": "trwiki|enwiki",
                "ids": "|".join(chunk),
            },
        ) or {}
        for qid, ent in (d.get("entities") or {}).items():
            img = None
            for c in (ent.get("claims") or {}).get("P18", []):
                v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
                if good_file(v):
                    img = commons_url(v)
                    break
            sitelinks = ent.get("sitelinks") or {}
            tr = sitelinks.get("trwiki", {}).get("title")
            en = sitelinks.get("enwiki", {}).get("title")
            wp = f"tr:{tr}" if tr else (f"en:{en}" if en else None)
            out[qid] = (img, wp)
        time.sleep(0.15)
    return out


# ---------- 2) Wikipedia makale görseli (toplu) ----------
def wikipedia_images(refs):
    """refs: {"tr:Başlık", "en:Title"} -> {ref: img}"""
    out = {}
    by_lang = {}
    for ref in refs:
        if not ref or ":" not in ref:
            continue
        lang, title = ref.split(":", 1)
        if re.match(r"^[a-z]{2,3}$", lang) and title:
            by_lang.setdefault(lang, []).append(title)
    for lang, titles in by_lang.items():
        titles = sorted(set(titles))
        for i in range(0, len(titles), 40):
            chunk = titles[i:i + 40]
            d = http_json(
                f"https://{lang}.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "format": "json",
                    "redirects": 1,
                    "prop": "pageimages",
                    "piprop": "thumbnail|name",
                    "pithumbsize": 700,
                    "titles": "|".join(chunk),
                },
            ) or {}
            q = d.get("query") or {}
            mapping = {t: t for t in chunk}
            for n in q.get("normalized", []) + q.get("redirects", []):
                for k, v in list(mapping.items()):
                    if v == n["from"]:
                        mapping[k] = n["to"]
            by_title = {p.get("title"): p for p in (q.get("pages") or {}).values()}
            for orig, final in mapping.items():
                p = by_title.get(final) or {}
                if good_file(p.get("pageimage")) and p.get("thumbnail"):
                    out[f"{lang}:{orig}"] = p["thumbnail"]["source"]
            time.sleep(0.15)
    return out


# ---------- 3) OSM image etiketi ----------
def osm_image(val):
    if not val:
        return None
    v = val.strip()
    m = re.match(r"^(?:File|Dosya):(.+)$", v, re.I)
    if m:
        return commons_url(m.group(1)) if good_file(m.group(1)) else None
    m = re.search(r"commons\.wikimedia\.org/wiki/(?:File|Dosya):([^?#]+)", v, re.I)
    if m:
        fn = urllib.parse.unquote(m.group(1))
        return commons_url(fn) if good_file(fn) else None
    if re.match(r"^https://upload\.wikimedia\.org/.+\.(jpe?g|png|webp)$", v, re.I) and good_file(v.rsplit("/", 1)[-1]):
        return v
    return None


# ---------- 4) Türkçe Wikipedia toplu başlık eşleşmesi (konum/il doğrulamalı) ----------
def wikipedia_title_batch(places):
    """
    Fotoğrafı olmayan mekanlar için aday başlıkları 40'arlı gruplar halinde tr.wikipedia'dan
    sorgular. Bir makalenin kabul edilmesi için:
      - Anlam ayrımı sayfası olmamalı
      - Koordinatı varsa mekana <= 15 km olmalı (başka ildeki benzer isimli yerleri eler)
      - Koordinatı yoksa makale başlığı veya giriş özetinde mekanın ili veya ilçesi geçmeli
    """
    cand_to_places = {}
    for p in places:
        if norm(p["ad"]) in GENERIC_NAMES:
            continue
        for base in base_variants(p["ad"]):
            if norm(base) in GENERIC_NAMES:
                continue
            cands = [base, f"{p['il']} {base}"]
            if p.get("ilce"):
                cands.append(f"{base}, {p['ilce']}")
            for c in cands:
                cand_to_places.setdefault(c, []).append(p)

    all_titles = sorted(cand_to_places.keys())
    for i in range(0, len(all_titles), 40):
        chunk = all_titles[i:i + 40]
        d = http_json(
            "https://tr.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "redirects": 1,
                "prop": "pageimages|coordinates|extracts|pageprops",
                "piprop": "thumbnail|name",
                "pithumbsize": 700,
                "exintro": 1,
                "explaintext": 1,
                "titles": "|".join(chunk),
            },
        ) or {}
        q = d.get("query") or {}
        mapping = {t: t for t in chunk}
        for n in q.get("normalized", []) + q.get("redirects", []):
            for k, v in list(mapping.items()):
                if v == n["from"]:
                    mapping[k] = n["to"]
        by_title = {pg.get("title"): pg for pg in (q.get("pages") or {}).values() if "missing" not in pg}

        for orig, final in mapping.items():
            pg = by_title.get(final)
            if not pg:
                continue
            if "disambiguation" in (pg.get("pageprops") or {}):
                continue
            title = pg.get("title") or ""
            if "anlam ayrımı" in title.lower():
                continue

            coords = pg.get("coordinates") or []
            extract_norm = norm(f"{title} {pg.get('pageimage', '')} {pg.get('extract', '')}")
            img = pg["thumbnail"]["source"] if (good_file(pg.get("pageimage")) and pg.get("thumbnail")) else None

            for p in cand_to_places.get(orig, []):
                if p.get("img"):
                    continue
                if not names_match(p["ad"], title, p["il"], p.get("ilce", "")):
                    continue
                # Konum / İl doğrulaması
                if coords:
                    c0 = coords[0]
                    if _dist_m(p["lat"], p["lon"], c0["lat"], c0["lon"]) > 15000:
                        continue
                else:
                    il_n = norm(p["il"])
                    ilce_n = norm(p.get("ilce", ""))
                    has_loc = (il_n and il_n in extract_norm) or (len(ilce_n) >= 3 and ilce_n in extract_norm)
                    if not has_loc:
                        continue

                p.setdefault("wp", f"tr:{title}")
                if img:
                    p["img"] = img
        time.sleep(0.15)


# ---------- 5) Koordinat + ad eşleşmeli Wikipedia araması (bölge bazında toplu) ----------
MATCH_RADIUS = 8000    # dağ/vadi/tabiat parkı kapsamak için 8 km
SEARCH_RADIUS = 10000  # Wikipedia geosearch üst sınırı


def geo_batch(todo):
    """todo içindeki mekanları bölge bölge tarar. {id: "tr:Başlık"} döner."""
    remaining = [p for p in todo if not (p["kategori"] == "Dağ Zirvesi" and "tepe" in norm(p["ad"]))]
    found = {}
    while remaining:
        c = remaining[0]
        d = http_json(
            "https://tr.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "list": "geosearch",
                "gscoord": f"{c['lat']}|{c['lon']}",
                "gsradius": SEARCH_RADIUS,
                "gslimit": 500,
            },
        ) or {}
        res = (d.get("query") or {}).get("geosearch", [])
        eff = SEARCH_RADIUS if len(res) < 500 else max((r["dist"] for r in res), default=0)
        cover = max(eff - MATCH_RADIUS, 2000)
        covered = [c] + [
            p for p in remaining[1:]
            if _dist_m(c["lat"], c["lon"], p["lat"], p["lon"]) <= cover
        ]
        for p in covered:
            best, best_d = None, 1e9
            for r in res:
                dd = _dist_m(p["lat"], p["lon"], r["lat"], r["lon"])
                if dd <= MATCH_RADIUS and dd < best_d and names_match(p["ad"], r["title"], p["il"], p.get("ilce", "")):
                    best, best_d = r["title"], dd
            if best:
                found[p["id"]] = f"tr:{best}"
        ids = {p["id"] for p in covered}
        remaining = [p for p in remaining if p["id"] not in ids]
        time.sleep(0.15)
    return found


# ---------- 6) Wikimedia Commons dosya başlığı (intitle) eşleşmesi ----------
def commons_strict_match(place):
    """
    Sadece belirgin isimli mekanlar için Wikimedia Commons'ta dosya başlığında
    mekan adı (+ kısa isimlerde il/ilçe adı) geçen gerçek fotoğrafları arar.
    """
    if place["kategori"] == "Dağ Zirvesi" and "tepe" in norm(place["ad"]):
        return None
    ad_n = norm(place["ad"])
    if not ad_n or ad_n in GENERIC_NAMES or len(ad_n) < 5:
        return None

    for cand in base_variants(place["ad"]):
        c_norm = norm(cand)
        tokens = [t for t in c_norm.split() if len(t) >= 3]
        if not tokens:
            continue
        il_n = norm(place["il"])
        ilce_n = norm(place.get("ilce", ""))
        need_loc = len(tokens) < 3 and il_n not in tokens
        q = f'filetype:bitmap intitle:"{cand}"'
        if need_loc:
            q += f' "{place["il"]}"'

        d = http_json(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrnamespace": 6,
                "gsrlimit": 5,
                "gsrsearch": q,
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 700,
            },
        ) or {}
        pages = (d.get("query") or {}).get("pages") or {}
        for pg in sorted(pages.values(), key=lambda x: x.get("index", 99)):
            title = pg.get("title") or ""
            if not good_file(title):
                continue
            t_norm = norm(re.sub(r"^File:", "", title, flags=re.I))
            if not all(tok in t_norm for tok in tokens):
                continue
            if need_loc and il_n not in t_norm and (not ilce_n or ilce_n not in t_norm):
                continue
            ii = (pg.get("imageinfo") or [{}])[0]
            url = ii.get("thumburl") or ii.get("url")
            if url:
                return url
        time.sleep(0.1)
    return None


def process_file(path):
    with open(path, encoding="utf-8") as f:
        places = json.load(f)
    for p in places:
        p.pop("img", None)
        p.pop("wp", None)

    # 1) Wikidata P18
    wd = wikidata_images([p["wikidata"] for p in places if p.get("wikidata")])
    for p in places:
        img, wp = wd.get(p.get("wikidata"), (None, None))
        if img:
            p["img"] = img
        if wp:
            p["wp"] = wp

    # 2) Bağlı Wikipedia makalesi
    for p in places:
        if p.get("wiki"):
            p.setdefault("wp", p["wiki"])
    wp_refs = {p["wp"] for p in places if p.get("wp") and not p.get("img")}
    wpi = wikipedia_images(wp_refs)
    for p in places:
        if not p.get("img") and p.get("wp") in wpi:
            p["img"] = wpi[p["wp"]]

    # 3) OSM image etiketi
    for p in places:
        if not p.get("img"):
            o = osm_image(p.get("image"))
            if o:
                p["img"] = o

    # 4) Türkçe Wikipedia toplu başlık eşleşmesi (konum/il doğrulamalı)
    todo_title = [p for p in places if not p.get("img")]
    wikipedia_title_batch(todo_title)

    # 5) Koordinat + ad eşleşmeli Wikipedia geosearch
    todo_geo = [p for p in places if not p.get("img") and not p.get("wp")]
    geo = geo_batch(todo_geo)
    geo_imgs = wikipedia_images(set(geo.values()))
    for p in todo_geo:
        ref = geo.get(p["id"])
        if ref:
            p.setdefault("wp", ref)
            if ref in geo_imgs:
                p["img"] = geo_imgs[ref]

    # 6) Wikimedia Commons dosya başlığı eşleşmesi
    for p in places:
        if not p.get("img"):
            c_img = commons_strict_match(p)
            if c_img:
                p["img"] = c_img

    for p in places:
        p["img"] = p.get("img") or ""
    places.sort(key=lambda r: (0 if r.get("img") else 1, 0 if r.get("wp") else 1, r["ad"]))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(places, f, ensure_ascii=False, separators=(",", ":"))
    return len(places), sum(1 for p in places if p.get("img"))


def main():
    args = sys.argv[1:]
    force = "--force" in args
    only = set(args[args.index("--only") + 1:]) if "--only" in args else None
    done = {}
    if os.path.exists(DONE_FILE) and not force:
        with open(DONE_FILE, encoding="utf-8") as f:
            done = json.load(f)

    files = sorted(fn for fn in os.listdir(PLACES_DIR) if fn.endswith(".json") and not fn.startswith(("_", "index")))
    tot, with_img = 0, 0
    for fn in files:
        slug = fn[:-5]
        if only and slug not in only:
            continue
        if slug in done and not force and not only:
            continue
        t0 = time.time()
        n, k = process_file(os.path.join(PLACES_DIR, fn))
        tot += n
        with_img += k
        done[slug] = {"places": n, "with_img": k}
        with open(DONE_FILE, "w", encoding="utf-8") as f:
            json.dump(done, f, ensure_ascii=False, indent=1)
        print(f"{slug}: {k}/{n} mekana doğrulanmış fotoğraf ({time.time() - t0:.1f} sn)", flush=True)
    print(f"\nBu çalıştırmada: {with_img}/{tot} mekana fotoğraf bulundu.")


if __name__ == "__main__":
    main()
