#!/usr/bin/env python3
"""
build_all_images_fast.py — 81 ilin tamamı için:
1) dataset/places_tr.json ve dataset/places_tr_merged.json içindeki eksik mekanları
   (ör. Ayasofya Camii ve Müzesi, Kızlar Manastırı, Kuştul Manastırı vb.) il/ilçe
   doğrulamasıyla data/places/<il>.json dosyalarına birleştirir.
2) Tüm Türkiye genelinde TOPLU (50'şerli batch) API sorgularıyla sadece o mekana ait
   olduğu %100 doğrulanabilen gerçek fotoğrafları eşleştirir:
   - Wikidata P18 (doğrudan mekan görseli)
   - Wikidata P373 / commonswiki (mekanın kendi Wikimedia Commons kategorisindeki fotoğraf)
   - Bağlı Wikipedia makalesi (tr, en, de, fr) ana görseli
   - OSM image / wikimedia_commons etiketi
   - Türkçe Wikipedia başlık eşleşmesi (koordinat <= 15 km VEYA özet/başlıkta il/ilçe adı şartı)
   - İngilizce Wikipedia başlık eşleşmesi (koordinat <= 15 km VEYA özet/başlıkta il/ilçe adı şartı)
"""
import glob
import json
import math
import os
import re
import time
import urllib.parse
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES_DIR = os.path.join(ROOT, "data", "places")
PROV_FILE = os.path.join(ROOT, "assets", "geo", "tr_provinces_simplified.geojson")
DIST_FILE = os.path.join(ROOT, "assets", "geo", "tr_districts_simplified.geojson")

UA = "NereyeGidilir/2.0 (static dataset build; contact: github.com/Oguzhan61-dilmac)"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA})

BAD_IMG = re.compile(
    r"(\.(svg|pdf|djvu|webm|ogv|ogg|gif|tif|tiff)$|map|harita|locator|location|konum|"
    r"flag|bayrak|logo|arma|coat[_ ]of[_ ]arms|seal|mühür|icon|signature|imza|diagram|"
    r"plan[_ .]|blank|silhouette|milliyet|cumhuriyet|vakit|gazete|newspaper|stamp|pullu|"
    r"placeholder|default|no[_ -]?image)",
    re.I,
)

GENERIC_NAMES = {
    "şehitlik", "atatürk anıtı", "atatürk heykeli", "atatürk büstü", "kilise kalıntısı",
    "cami", "camii", "çeşme", "köprü", "kale", "tepe", "anıt", "heykel", "müze",
    "yeniçeri", "yunus balıkları", "meçhul asker anıtı", "büyük sanayi sitesi",
    "seyir terası", "piknik alanı", "mesire alanı", "plaj", "halk plajı", "türbe",
    "hamam", "medrese", "han", "kervansaray", "su kemeri", "antik kent", "ören yeri",
}

STRIP_SUFFIXES = [
    " tabiat parkı", " millî parkı", " milli parkı", " seyir terası",
    " seyir noktası", " ören yeri", " antik kenti", " aile plajı",
]

NON_LATIN = re.compile(r"[\u0600-\u06FF\u0400-\u04FF\u4E00-\u9FFF\u3040-\u30FF\uFF00-\uFFEF]")
ONLY_DIGITS = re.compile(r"^[\d\s.,\-]+$")


def http_json(url, params=None, tries=5):
    for i in range(tries):
        try:
            r = SESSION.get(url, params=params, timeout=30)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After") or 0) or 8 * (i + 1)
                print(f"  … hız sınırı ({url.split('/')[2]}), {min(wait, 45)} sn bekleniyor", flush=True)
                time.sleep(min(wait, 45))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i == tries - 1:
                print(f"  ! istek başarısız ({url.split('/')[2]}): {e}", flush=True)
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
    clean = urllib.parse.unquote(name)
    return not BAD_IMG.search(clean) and bool(re.search(r"\.(jpe?g|png|webp)(?:\?|$)", clean, re.I))


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
    raw = (place_name or "").strip()
    out = [raw]
    low = raw.replace("İ", "i").replace("I", "ı").lower()
    for suf in STRIP_SUFFIXES:
        if low.endswith(suf) and len(raw) > len(suf) + 3:
            out.append(raw[: len(raw) - len(suf)].strip())
    if low.startswith("trabzonspor ") and len(raw) > 15:
        out.append(raw[12:].strip())
    return out


def names_match(place_name, title, il="", ilce=""):
    t_clean = re.sub(r"\s*\(.*?\)\s*$", "", title or "")
    if "," in t_clean:
        parts = [p.strip() for p in t_clean.split(",", 1)]
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


# ---------- Geometri / İlçe bulucu ----------
def map_cat(raw_cat, tags):
    t = tags or {}
    c = (raw_cat or "").lower()
    if "museum" in c or t.get("tourism") == "museum": return "Müze"
    if "castle" in c or "fort" in c or t.get("historic") in ("castle", "fort"): return "Kale / Hisar"
    if "ruins" in c or "archaeological" in c or t.get("historic") in ("ruins", "archaeological_site"): return "Antik Kent"
    if "waterfall" in c or t.get("natural") == "waterfall": return "Şelale"
    if "cave" in c or t.get("natural") == "cave_entrance": return "Mağara"
    if "beach" in c or t.get("natural") == "beach": return "Plaj / Koy"
    if "hot_spring" in c or t.get("natural") == "hot_spring": return "Kaplıca"
    if "nature_reserve" in c or t.get("leisure") == "nature_reserve": return "Doğa Parkı"
    if "viewpoint" in c or t.get("tourism") == "viewpoint": return "Seyir Noktası"
    if "mosque" in c or t.get("historic") == "mosque" or (t.get("amenity") == "place_of_worship" and t.get("religion") == "muslim"): return "Tarihi Camii"
    if "church" in c or "monastery" in c or t.get("historic") in ("church", "monastery") or (t.get("amenity") == "place_of_worship" and t.get("religion") == "christian"): return "Tarihi Kilise"
    if "monument" in c or "memorial" in c or "tomb" in c or t.get("historic") in ("monument", "memorial", "tomb"): return "Anıt"
    if "peak" in c or t.get("natural") == "peak": return "Dağ Zirvesi"
    return "Turistik Alan"


def merge_existing_datasets(by_prov, prov_by_name, districts_by_prov):
    """dataset/places_tr.json ve places_tr_merged.json içindeki gerçek mekanları ekler."""
    added = 0
    for fn in ["dataset/places_tr.json", "dataset/places_tr_merged.json"]:
        path = os.path.join(ROOT, fn)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
        for r in rows:
            il = (r.get("il") or "").strip()
            if il not in by_prov:
                continue
            ad = (r.get("ad") or "").strip()
            if not ad or NON_LATIN.search(ad) or ONLY_DIGITS.match(ad):
                continue
            raw_cat = str(r.get("kategori") or "")
            # Otel/stadyum/spor salonu/zirve ekleme
            if any(x in raw_cat for x in ("hotel", "hostel", "guest_house", "stadium", "pitch", "sports_hall", "peak", "park")):
                continue
            t = r.get("tags") or {}
            lat, lon = r.get("lat"), r.get("lon")
            if not lat or not lon:
                continue
            existing_names = {norm(p["ad"]) for p in by_prov[il]}
            if norm(ad) in existing_names:
                # Varsa wikidata/wiki/image bilgilerini zenginleştir
                for p in by_prov[il]:
                    if norm(p["ad"]) == norm(ad):
                        if t.get("wikidata") and not p.get("wikidata"):
                            p["wikidata"] = t["wikidata"]
                        if t.get("wikipedia") and not p.get("wiki"):
                            p["wiki"] = t["wikipedia"]
                        img_u = r.get("image_url") or ""
                        if img_u.startswith("https://upload.wikimedia.org/") and good_file(img_u):
                            p["image"] = img_u
                continue

            ilce = t.get("ilce") or t.get("addr:district") or ""
            if not ilce and il in districts_by_prov:
                best_d, best_name = 1e9, ""
                for d_name, (cx, cy) in districts_by_prov[il]:
                    dd = (cx - lon) ** 2 + (cy - lat) ** 2
                    if dd < best_d:
                        best_d, best_name = dd, d_name
                ilce = best_name

            rec = {
                "id": r.get("id") or f"node:{abs(hash(ad))}",
                "ad": ad,
                "il": il,
                "ilce": ilce,
                "lat": round(float(lat), 6),
                "lon": round(float(lon), 6),
                "kategori": map_cat(raw_cat, t),
            }
            if t.get("wikipedia"):
                rec["wiki"] = t["wikipedia"]
            if t.get("wikidata"):
                rec["wikidata"] = t["wikidata"]
            img_u = r.get("image_url") or t.get("image") or ""
            if img_u.startswith("https://upload.wikimedia.org/") and good_file(img_u):
                rec["image"] = img_u
            by_prov[il].append(rec)
            added += 1
    print(f"Eski veri setlerinden {added} yeni mekan eklendi/zenginleştirildi.", flush=True)


def batch_wikidata(qids):
    """QID -> (img_url, wp_ref, commons_cat)"""
    out = {}
    qids = sorted(set(q for q in qids if re.match(r"^Q\d+$", str(q))))
    print(f"1) Wikidata sorgulanıyor: {len(qids)} tekil QID ({math.ceil(len(qids)/50)} istek)...", flush=True)
    for i in range(0, len(qids), 50):
        chunk = qids[i:i + 50]
        d = http_json(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbgetentities",
                "format": "json",
                "props": "claims|sitelinks",
                "sitefilter": "trwiki|enwiki|dewiki|frwiki|commonswiki",
                "ids": "|".join(chunk),
            },
        ) or {}
        for qid, ent in (d.get("entities") or {}).items():
            claims = ent.get("claims") or {}
            img = None
            for c in claims.get("P18", []):
                v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
                if good_file(v):
                    img = commons_url(v)
                    break
            cat = None
            for c in claims.get("P373", []):
                v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
                if v and isinstance(v, str):
                    cat = f"Category:{v}"
                    break
            sitelinks = ent.get("sitelinks") or {}
            if not cat and "commonswiki" in sitelinks:
                cw = sitelinks["commonswiki"].get("title") or ""
                if cw.startswith("Category:"):
                    cat = cw
            wp = None
            for lang in ("tr", "en", "de", "fr"):
                t = sitelinks.get(f"{lang}wiki", {}).get("title")
                if t:
                    wp = f"{lang}:{t}"
                    break
            out[qid] = (img, wp, cat)
        time.sleep(0.1)
    return out


def batch_wikipedia_images(refs):
    """{"tr:Başlık", "en:Title"} -> {ref: img_url}"""
    out = {}
    by_lang = {}
    for ref in refs:
        if not ref or ":" not in ref:
            continue
        lang, title = ref.split(":", 1)
        if re.match(r"^[a-z]{2,3}$", lang) and title:
            by_lang.setdefault(lang, []).append(title)
    total_reqs = sum(math.ceil(len(set(v)) / 40) for v in by_lang.values())
    print(f"2) Bağlı Wikipedia makaleleri sorgulanıyor ({total_reqs} istek)...", flush=True)
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
            time.sleep(0.1)
    return out


def batch_commons_categories(cats):
    """Commons Category -> ilk geçerli fotoğraf URL"""
    out = {}
    cats = sorted(set(c for c in cats if c and c.startswith("Category:")))
    print(f"3) Wikidata Commons kategorileri sorgulanıyor ({len(cats)} kategori)...", flush=True)
    for cat in cats:
        d = http_json(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "generator": "categorymembers",
                "gcmtitle": cat,
                "gcmtype": "file",
                "gcmlimit": 8,
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 700,
            },
        ) or {}
        pages = (d.get("query") or {}).get("pages") or {}
        for pg in pages.values():
            title = pg.get("title") or ""
            if good_file(title):
                ii = (pg.get("imageinfo") or [{}])[0]
                u = ii.get("thumburl") or ii.get("url")
                if u:
                    out[cat] = u
                    break
        time.sleep(0.08)
    return out


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


def global_wikipedia_title_match(all_places):
    """
    Fotoğrafı henüz olmayan gerçek mekanlar için (Dağ Zirvesi 'Tepe' hariç)
    Türkçe Wikipedia'dan 40'arlı toplu başlık sorgusu yapar.
    """
    cand_to_places = {}
    for p in all_places:
        if p.get("img"):
            continue
        if p["kategori"] == "Dağ Zirvesi" and "tepe" in norm(p["ad"]):
            continue
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
    print(f"4) Türkçe Wikipedia başlık eşleşmesi: {len(all_titles)} aday ({math.ceil(len(all_titles)/40)} istek)...", flush=True)
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
        if (i // 40) % 25 == 0 and i > 0:
            print(f"   … {i}/{len(all_titles)} başlık tarandı", flush=True)
        time.sleep(0.1)


def main():
    t_start = time.time()
    with open(PROV_FILE, encoding="utf-8") as f:
        prov_geo = json.load(f)
    with open(DIST_FILE, encoding="utf-8") as f:
        dist_geo = json.load(f)

    prov_by_name = {ft["properties"]["name_tr"]: ft["properties"]["slug"] for ft in prov_geo["features"]}
    slug_to_prov = {v: k for k, v in prov_by_name.items()}

    districts_by_prov = {}
    for ft in dist_geo["features"]:
        pr = ft["properties"]["province_tr"]
        nm = ft["properties"]["name_tr"]
        coords = ft["geometry"]["coordinates"]
        ring = coords[0] if ft["geometry"]["type"] == "Polygon" else coords[0][0]
        cx = sum(pt[0] for pt in ring) / len(ring)
        cy = sum(pt[1] for pt in ring) / len(ring)
        districts_by_prov.setdefault(pr, []).append((nm, (cx, cy)))

    by_prov = {}
    for slug, pname in slug_to_prov.items():
        path = os.path.join(PLACES_DIR, f"{slug}.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                by_prov[pname] = json.load(f)

    merge_existing_datasets(by_prov, prov_by_name, districts_by_prov)

    all_places = [p for plist in by_prov.values() for p in plist]
    for p in all_places:
        p.pop("img", None)
        p.pop("wp", None)

    # 1) Wikidata toplu sorgu
    wd_map = batch_wikidata([p["wikidata"] for p in all_places if p.get("wikidata")])
    cats_needed = set()
    for p in all_places:
        qid = p.get("wikidata")
        if qid and qid in wd_map:
            img, wp, cat = wd_map[qid]
            if img:
                p["img"] = img
            if wp:
                p["wp"] = wp
            if not img and cat:
                p["_cat"] = cat
                cats_needed.add(cat)

    # 2) Bağlı Wikipedia makaleleri
    for p in all_places:
        if p.get("wiki"):
            p.setdefault("wp", p["wiki"])
    wp_refs = {p["wp"] for p in all_places if p.get("wp") and not p.get("img")}
    wp_imgs = batch_wikipedia_images(wp_refs)
    for p in all_places:
        if not p.get("img") and p.get("wp") in wp_imgs:
            p["img"] = wp_imgs[p["wp"]]

    # 3) Wikidata Commons kategorileri (henüz resmi olmayanlar için)
    cats_still_needed = {p["_cat"] for p in all_places if p.get("_cat") and not p.get("img")}
    cat_imgs = batch_commons_categories(cats_still_needed)
    for p in all_places:
        cat = p.pop("_cat", None)
        if not p.get("img") and cat and cat in cat_imgs:
            p["img"] = cat_imgs[cat]

    # 4) OSM image etiketi
    for p in all_places:
        if not p.get("img"):
            o = osm_image(p.get("image"))
            if o:
                p["img"] = o

    # 5) Türkçe Wikipedia toplu başlık eşleşmesi
    global_wikipedia_title_match(all_places)

    # Kaydet
    total_places = 0
    total_with_img = 0
    index = {}
    done = {}
    for pname, plist in sorted(by_prov.items()):
        slug = prov_by_name[pname]
        for p in plist:
            p["img"] = p.get("img") or ""
        plist.sort(key=lambda r: (0 if r.get("img") else 1, 0 if r.get("wp") else 1, r["ad"]))
        path = os.path.join(PLACES_DIR, f"{slug}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(plist, f, ensure_ascii=False, separators=(",", ":"))
        k = sum(1 for p in plist if p.get("img"))
        total_places += len(plist)
        total_with_img += k
        index[pname] = {"slug": slug, "count": len(plist), "with_img": k}
        done[slug] = {"places": len(plist), "with_img": k}

    with open(os.path.join(PLACES_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    with open(os.path.join(PLACES_DIR, "_images_done.json"), "w", encoding="utf-8") as f:
        json.dump(done, f, ensure_ascii=False, indent=1)

    print(f"\nTAMAMLANDI ({time.time() - t_start:.1f} sn): 81 ilde toplam {total_places} mekan, {total_with_img} doğrulanmış fotoğraflı mekan!", flush=True)


if __name__ == "__main__":
    main()
