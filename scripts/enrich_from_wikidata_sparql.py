#!/usr/bin/env python3
"""
enrich_from_wikidata_sparql.py — Wikidata SPARQL üzerinden Türkiye'deki koordinatlı,
Türkçe başlıklı ve doğrulanmış P18 fotoğraflı tüm turistik/tarihi/doğal mekanları
çeker, il ve ilçe sınır poligonlarıyla (GeoJSON) eşleştirir ve data/places/<il>.json
dosyalarına ekler.
"""
import json
import os
import re
import sys
import urllib.parse
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from build_places import load_geo, locate  # noqa: E402

PLACES_DIR = os.path.join(ROOT, "data", "places")
UA = "NereyeGidilir/2.0 (https://github.com/Oguzhan61-dilmac)"

BAD_IMG = re.compile(
    r"(\.(svg|pdf|djvu|webm|ogv|ogg|gif|tif|tiff)$|map|harita|locator|location|konum|"
    r"flag|bayrak|logo|arma|coat[_ ]of[_ ]arms|seal|mühür|icon|signature|imza|diagram|"
    r"plan[_ .]|blank|silhouette|milliyet|cumhuriyet|vakit|gazete|newspaper|stamp|pullu|"
    r"placeholder|default|no[_ -]?image|districts)",
    re.I,
)

# İdari birimler, yerleşimler, okullar, stadyumlar, olaylar, kişiler vb. hariç tutulur
EXCLUDE_TYPES = re.compile(
    r"\b(il|ili|ilçe|ilçesi|belediye|köy|köyü|mahalle|belde|bucak|kent|şehir|kasaba|"
    r"yerleşim|bölge|ülke|devlet|imparatorluk|eyalet|sancak|vilayet|"
    r"üniversite|fakülte|lise|okul|kolej|enstitü|hastane|klinik|"
    r"stadyum|spor salonu|arena|hipodrom|antrenman|"
    r"havalimanı|havaalanı|istasyon|gar|metro|otogar|liman|iskele|kavşak|otoyol|karayolu|tünel|"
    r"baraj|hidroelektrik|termik|santral|fabrika|maden|organize sanayi|"
    r"mezarlık|askeri|kışla|hapishane|cezaevi|alışveriş merkezi|"
    r"seçim|deprem|muharebe|savaş|kuşatma|antlaşma|katliam|isyan|olay|festival|turnuva|yarışma|"
    r"insan|futbol|kulüp|takım|şirket|kurum|dernek|vakıf|parti|gazete|dergi|film|dizi|şarkı)\b",
    re.I,
)

INCLUDE_TYPES = re.compile(
    r"\b(müze\w*|kale|kalesi|kaleleri|hisar\w*|burç|burcu|kule|kulesi|surlar\w*|saray\w*|köşk\w*|kasır|kasrı|konak|konağı|yalı\w*|"
    r"cami\w*|mescit|mescidi|kilise\w*|katedral\w*|manastır\w*|sinagog\w*|tapınak|tapınağı|külliye\w*|medrese\w*|türbe\w*|kümbet\w*|tekke\w*|zaviye\w*|dergah\w*|"
    r"antik|ören|höyük|höyüğü|tümülüs\w*|nekropol\w*|tiyatro\w*|amfitiyatro\w*|agora|bazilika\w*|harabe\w*|kalıntı\w*|sit alanı|kaya mezarı|yazıt\w*|kabartma\w*|"
    r"anıt\w*|abide\w*|heykel\w*|dikilitaş\w*|zafer takı|sütun\w*|"
    r"köprü\w*|su kemeri|çeşme\w*|sebil\w*|şadırvan\w*|hamam\w*|kaplıca\w*|ılıca\w*|han|hanı|kervansaray\w*|bedesten\w*|çarşı\w*|arasta\w*|saat kulesi|deniz feneri|feneri|"
    r"şelale\w*|çağlayan\w*|mağara\w*|ini|kanyon\w*|vadi\w*|boğaz\w*|göl|gölü|lagün\w*|krater\w*|obruk|obruğu|peri bacaları|traverten\w*|"
    r"plaj\w*|koy|koyu|sahil\w*|ada|adası|yarımada\w*|burun|burnu|delta\w*|"
    r"milli park\w*|millî park\w*|tabiat park\w*|doğa park\w*|tabiatı koruma|tabiat anıtı|botanik|arboretum|koru|korusu|"
    r"dağ|dağı|dağları|yanardağ\w*|volkan\w*|zirve\w*|yayla\w*|"
    r"turistik|seyir|miras|kültürel varlık|korunan alan|arkeolojik)\b",
    re.I,
)

NON_LATIN = re.compile(r"[\u0600-\u06FF\u0400-\u04FF\u4E00-\u9FFF\u3040-\u30FF\uFF00-\uFFEF]")


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


def commons_url(url_or_name):
    fn = urllib.parse.unquote(url_or_name.rsplit("/", 1)[-1]).replace(" ", "_")
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(fn)}?width=700"


def good_file(url_or_name):
    clean = urllib.parse.unquote(url_or_name)
    return not BAD_IMG.search(clean) and bool(re.search(r"\.(jpe?g|png|webp)(?:\?|$)", clean, re.I))


def classify(type_label, item_label):
    tl = f"{type_label} {item_label}".replace("İ", "i").replace("I", "ı").lower()
    if "müze" in tl:
        return "Müze"
    if re.search(r"\b(kale|kalesi|kaleleri|hisar\w*|burç|burcu|surlar\w*|tahkimat|gözetleme kulesi)\b", tl):
        return "Kale / Hisar"
    if any(w in tl for w in ("antik", "ören", "höyük", "tümülüs", "nekropol", "harabe", "kalıntı", "arkeolojik", "kaya mezarı")):
        return "Antik Kent"
    if any(w in tl for w in ("cami", "mescit", "külliye")):
        return "Tarihi Camii"
    if any(w in tl for w in ("kilise", "katedral", "manastır", "şapel")):
        return "Tarihi Kilise"
    if any(w in tl for w in ("şelale", "çağlayan")):
        return "Şelale"
    if any(w in tl for w in ("mağara", "obruk")):
        return "Mağara"
    if any(w in tl for w in ("plaj", "koy", "sahil")):
        return "Plaj / Koy"
    if any(w in tl for w in ("kaplıca", "ılıca", "termal")):
        return "Kaplıca"
    if any(w in tl for w in ("milli park", "millî park", "tabiat parkı", "doğa parkı", "tabiatı koruma", "tabiat anıtı", "kanyon", "vadi", "göl")):
        return "Doğa Parkı"
    if any(w in tl for w in ("anıt", "abide", "heykel", "türbe", "kümbet", "şehitlik")):
        return "Anıt"
    if any(w in tl for w in ("dağ", "yanardağ", "volkan", "zirve")):
        return "Dağ Zirvesi"
    return "Turistik Alan"


SPARQL_1 = """
SELECT ?item ?itemLabel ?typeLabel ?coord ?img ?article WHERE {
  ?item wdt:P17 wd:Q43 ;
        wdt:P31 ?type ;
        wdt:P625 ?coord .
  OPTIONAL { ?item wdt:P18 ?img . }
  ?article schema:about ?item ;
           schema:isPartOf <https://tr.wikipedia.org/> .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "tr". }
}
"""

SPARQL_2 = """
SELECT ?item ?itemLabel ?coord ?img WHERE {
  ?item wdt:P17 wd:Q43 ;
        wdt:P625 ?coord ;
        wdt:P18 ?img ;
        rdfs:label ?itemLabel .
  FILTER(LANG(?itemLabel) = "tr")
}
"""


def run_sparql(query):
    r = requests.get(
        "https://query.wikidata.org/sparql",
        params={"query": query, "format": "json"},
        headers={"User-Agent": UA},
        timeout=90,
    )
    r.raise_for_status()
    return json.loads(r.text, strict=False)["results"]["bindings"]


def main():
    provinces, districts = load_geo()
    prov_by_name = {p.name: p for p in provinces}

    print("SPARQL 1 (Türkçe Wikipedia makaleli mekanlar) çekiliyor...", flush=True)
    rows1 = run_sparql(SPARQL_1)
    print(f"  -> {len(rows1)} satır geldi", flush=True)
    print("SPARQL 2 (tüm fotoğraflı Türkçe mekanlar) çekiliyor...", flush=True)
    rows2 = run_sparql(SPARQL_2)
    print(f"  -> {len(rows2)} satır geldi", flush=True)

    # QID bazında birleştir
    items = {}
    for b in rows1 + rows2:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        label = b.get("itemLabel", {}).get("value", "").strip()
        if not label or re.match(r"^Q\d+$", label) or NON_LATIN.search(label):
            continue
        tlabel = b.get("typeLabel", {}).get("value", "").strip()
        img_raw = b.get("img", {}).get("value", "")
        img_url = commons_url(img_raw) if (img_raw and good_file(img_raw)) else ""
        m = re.match(r"Point\(([-\d.]+)\s+([-\d.]+)\)", b.get("coord", {}).get("value", ""))
        if not m:
            continue
        lon, lat = float(m.group(1)), float(m.group(2))
        art = b.get("article", {}).get("value", "")
        wp = None
        if "/wiki/" in art:
            wp = "tr:" + urllib.parse.unquote(art.split("/wiki/", 1)[1]).replace("_", " ")

        rec = items.setdefault(
            qid,
            {
                "qid": qid,
                "ad": label,
                "types": set(),
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "img": img_url,
                "wp": wp,
            },
        )
        if img_url and not rec["img"]:
            rec["img"] = img_url
        if tlabel:
            rec["types"].add(tlabel)
        if wp and not rec["wp"]:
            rec["wp"] = wp

    # Tür filtresi
    valid_items = []
    for rec in items.values():
        all_t = " | ".join(rec["types"])
        combined = f"{all_t} {rec['ad']}"
        if EXCLUDE_TYPES.search(all_t) and not INCLUDE_TYPES.search(all_t):
            continue
        if not INCLUDE_TYPES.search(combined):
            continue
        # "X Barajı ve Hidroelektrik Santrali" gibi yapıları ele
        if re.search(r"\b(barajı|santrali|rafineri\w*|sınır kapısı|havalimanı|stadyumu|üniversitesi|lisesi|mezarlığı|cezaevi)\b", rec["ad"], re.I):
            continue
        rec["kategori"] = classify(all_t, rec["ad"])
        valid_items.append(rec)

    # Wikidata P18'i olmayan ama Türkçe Wikipedia makalesi olan mekanların görsellerini çek
    missing_wp = [rec for rec in valid_items if not rec["img"] and rec.get("wp")]
    titles = sorted(set(rec["wp"].split(":", 1)[1] for rec in missing_wp))
    print(f"P18 resmi olmayıp Vikipedi görseli kontrol edilecek mekan: {len(titles)}", flush=True)
    wp_img_map = {}
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    for i in range(0, len(titles), 40):
        chunk = titles[i:i + 40]
        try:
            r = s.get(
                "https://tr.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "format": "json",
                    "redirects": 1,
                    "prop": "pageimages",
                    "piprop": "thumbnail|name",
                    "pithumbsize": 700,
                    "titles": "|".join(chunk),
                },
                timeout=30,
            )
            q = (r.json().get("query") or {})
            mapping = {t: t for t in chunk}
            for n in q.get("normalized", []) + q.get("redirects", []):
                for k, v in list(mapping.items()):
                    if v == n["from"]:
                        mapping[k] = n["to"]
            by_t = {pg.get("title"): pg for pg in (q.get("pages") or {}).values()}
            for orig, final in mapping.items():
                pg = by_t.get(final) or {}
                if good_file(pg.get("pageimage") or "") and pg.get("thumbnail"):
                    wp_img_map[orig] = pg["thumbnail"]["source"]
        except Exception:
            pass
    for rec in missing_wp:
        t = rec["wp"].split(":", 1)[1]
        if t in wp_img_map:
            rec["img"] = wp_img_map[t]

    valid_items = [rec for rec in valid_items if rec.get("img")]
    print(f"Filtre sonrası uygun fotoğraflı mekan: {len(valid_items)}", flush=True)

    # İl ve ilçelere yerleştir
    by_prov = {}
    for p in provinces:
        path = os.path.join(PLACES_DIR, f"{p.slug}.json")
        with open(path, encoding="utf-8") as f:
            by_prov[p.name] = json.load(f)

    added, updated = 0, 0
    for rec in valid_items:
        # Hangi ilde?
        target_prov = None
        ilce = None
        for p in provinces:
            b = p.bbox
            if b[0] - 0.05 <= rec["lon"] <= b[2] + 0.05 and b[1] - 0.05 <= rec["lat"] <= b[3] + 0.05:
                d_name = locate(rec["lon"], rec["lat"], p, districts)
                if d_name:
                    target_prov = p
                    ilce = d_name
                    break
        if not target_prov:
            continue

        plist = by_prov[target_prov.name]
        # Zaten var mı? (QID veya normalize ad ile)
        existing = None
        for ep in plist:
            if ep.get("wikidata") == rec["qid"] or norm(ep["ad"]) == norm(rec["ad"]):
                existing = ep
                break
        if existing:
            if not existing.get("img"):
                existing["img"] = rec["img"]
                updated += 1
            if rec["wp"] and not existing.get("wp"):
                existing["wp"] = rec["wp"]
            if not existing.get("wikidata"):
                existing["wikidata"] = rec["qid"]
        else:
            new_p = {
                "id": f"wd:{rec['qid']}",
                "ad": rec["ad"],
                "il": target_prov.name,
                "ilce": ilce,
                "lat": rec["lat"],
                "lon": rec["lon"],
                "kategori": rec["kategori"],
                "wikidata": rec["qid"],
                "img": rec["img"],
            }
            if rec["wp"]:
                new_p["wp"] = rec["wp"]
                new_p["wiki"] = rec["wp"]
            plist.append(new_p)
            added += 1

    print(f"SPARQL ile {added} yeni fotoğraflı mekan eklendi, {updated} mevcut mekana fotoğraf kazandırıldı.", flush=True)

    # Kaydet
    index = {}
    done = {}
    tot_all, tot_img = 0, 0
    for p in sorted(provinces, key=lambda x: x.name):
        plist = [
            item for item in by_prov[p.name]
            if not re.search(r"\b(barajı|santrali|rafineri\w*|sınır kapısı|havalimanı|stadyumu|üniversitesi|lisesi|mezarlığı|cezaevi)\b", item["ad"], re.I)
        ]
        for item in plist:
            item["img"] = item.get("img") or ""
        plist.sort(key=lambda r: (0 if r.get("img") else 1, 0 if r.get("wp") else 1, r["ad"]))
        path = os.path.join(PLACES_DIR, f"{p.slug}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(plist, f, ensure_ascii=False, separators=(",", ":"))
        k = sum(1 for item in plist if item.get("img"))
        tot_all += len(plist)
        tot_img += k
        index[p.name] = {"slug": p.slug, "count": len(plist), "with_img": k}
        done[p.slug] = {"places": len(plist), "with_img": k}

    with open(os.path.join(PLACES_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    with open(os.path.join(PLACES_DIR, "_images_done.json"), "w", encoding="utf-8") as f:
        json.dump(done, f, ensure_ascii=False, indent=1)

    print(f"TOPLAM: 81 ilde {tot_all} mekan, {tot_img} doğrulanmış fotoğraflı mekan!", flush=True)


if __name__ == "__main__":
    main()
