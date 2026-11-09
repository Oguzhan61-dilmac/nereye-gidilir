#!/usr/bin/env python3
"""
build_wikidata_enrich.py — data/places/*.json dosyalarını Wikidata + Wikipedia ile zenginleştirir.

Ne yapar?
  1) Wikidata SPARQL ile Türkiye'deki gezilecek yer türlerini çeker
     (plaj, koy, göl, yayla, kanyon, şelale, mağara, kale, antik kent, müze,
      kervansaray, köprü, manastır, cami, türbe, milli park, tabiat parkı, ada ...).
  2) Her yeri il/ilçe sınırlarına (tr_districts_simplified.geojson) nokta-poligon testiyle yerleştirir.
  3) Mevcut kayıtlarla Wikidata kimliği (QID) veya "aynı ad + 300 m" ile birleştirir (kopya yok).
  4) Türkçe Wikipedia maddelerinin son 12 aylık görüntülenme sayısını "pop" alanına yazar.
     Site bu alanla sıralar → en meşhur yerler en üstte.

Yalnızca standart kütüphane kullanır. Kullanım:
  python scripts/build_wikidata_enrich.py              # tüm iller
  python scripts/build_wikidata_enrich.py --no-views   # görüntülenme sayılarını atla (hızlı)
"""
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_FILE = os.path.join(ROOT, "assets", "geo", "tr_districts_simplified.geojson")
OUT_DIR = os.path.join(ROOT, "data", "places")
UA = "GeziAtlasi-DataBuilder/2.0 (https://geziatlasi.com.tr)"
SPARQL = "https://query.wikidata.org/sparql"

# Wikidata sınıfı -> site kategorisi. (P31/P279* ile alt sınıflar da gelir)
# need_article=True: yalnızca Türkçe Wikipedia maddesi olanlar (binlerce sıradan cami/köprü gelmesin)
CLASSES = [
    ("Q40080", "Plaj / Koy", False),        # plaj
    ("Q31615", "Plaj / Koy", False),        # koy (cove)
    ("Q39594", "Plaj / Koy", True),         # koy / körfez (bay)
    ("Q23397", "Göl / Nehir", False),       # göl
    ("Q75520", "Yayla", False),             # plato / yayla
    ("Q8050526", "Yayla", False),           # yayla (TR)
    ("Q11959973", "Plaj / Koy", False),     # halk plajı
    ("Q150784", "Kanyon", False),           # kanyon
    ("Q1668451", "Kanyon", False),          # boğaz (gorge)
    ("Q39816", "Vadi", True),               # vadi
    ("Q34038", "Şelale", False),            # şelale
    ("Q35509", "Mağara", False),            # mağara
    ("Q177380", "Kaplıca", False),          # kaplıca
    ("Q23442", "Ada", True),                # ada
    ("Q46169", "Milli Park", False),        # milli park
    ("Q728904", "Doğa Parkı", False),       # tabiat parkı
    ("Q179049", "Doğa Parkı", False),       # doğa koruma alanı
    ("Q23413", "Kale / Hisar", False),      # kale
    ("Q57821", "Kale / Hisar", False),      # tahkimat
    ("Q839954", "Antik Kent", False),       # arkeolojik sit
    ("Q15661340", "Antik Kent", False),     # antik kent
    ("Q33506", "Müze", False),              # müze
    ("Q16560", "Saray / Köşk", False),      # saray
    ("Q186347", "Kervansaray / Han", False),# kervansaray
    ("Q841985", "Kervansaray / Han", True), # han
    ("Q221673", "Tarihi Konak", True),      # konak
    ("Q853854", "Saat Kulesi", True),       # saat kulesi
    ("Q39715", "Deniz Feneri", True),       # deniz feneri
    ("Q12280", "Tarihi Köprü", True),       # köprü
    ("Q44613", "Tarihi Kilise", False),     # manastır
    ("Q16970", "Tarihi Kilise", True),      # kilise
    ("Q32815", "Tarihi Camii", True),       # cami
    ("Q838159", "Türbe / Külliye", True),   # türbe
    ("Q132834", "Medrese", True),           # medrese
    ("Q28077", "Tarihi Hamam", True),       # hamam
    ("Q4989906", "Anıt", True),             # anıt
    ("Q570116", "Turistik Alan", True),     # turistik yer
    ("Q177305", "Seyir Noktası", False),    # seyir terası
    ("Q8502", "Dağ Zirvesi", True),         # dağ
]

# Ad içinde geçerse yer büyük olasılıkla gezilecek yer değildir (idari birim vb.)
JUNK_NAME = re.compile(r"\b(mahallesi|köyü|ilçesi|belediyesi|okulu|lisesi|hastanesi|havalimanı|havaalanı|airport|avm)\b", re.I)


def http_json(url, data=None, headers=None, retries=4):
    h = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        h.update(headers)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            wait = 5 * (attempt + 1) if e.code in (429, 500, 502, 503, 504) else 2
            time.sleep(wait)
        except Exception:
            time.sleep(3 * (attempt + 1))
    return None


def sparql(query):
    body = urllib.parse.urlencode({"query": query}).encode()
    return http_json(SPARQL, data=body, headers={
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded",
    })


def fetch_class(qid, need_article):
    article_clause = "?article schema:about ?item; schema:isPartOf <https://tr.wikipedia.org/>; schema:name ?title ." \
        if need_article else \
        "OPTIONAL { ?article schema:about ?item; schema:isPartOf <https://tr.wikipedia.org/>; schema:name ?title . }"
    q = f"""
SELECT ?item ?label ?coord ?image ?title ?sl WHERE {{
  ?item wdt:P31/wdt:P279* wd:{qid}; wdt:P17 wd:Q43; wdt:P625 ?coord .
  ?item rdfs:label ?label . FILTER(LANG(?label) = "tr")
  ?item wikibase:sitelinks ?sl .
  OPTIONAL {{ ?item wdt:P18 ?image . }}
  {article_clause}
}}"""
    res = sparql(q)
    if not res:
        print(f"  ! {qid} sorgusu başarısız", file=sys.stderr)
        return []
    out = {}
    for b in res["results"]["bindings"]:
        item = b["item"]["value"].rsplit("/", 1)[-1]
        m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", b["coord"]["value"])
        if not m:
            continue
        if item in out:
            continue
        out[item] = {
            "qid": item,
            "ad": b["label"]["value"],
            "lon": float(m.group(1)),
            "lat": float(m.group(2)),
            "image": b.get("image", {}).get("value", ""),
            "title": b.get("title", {}).get("value", ""),
            "sl": int(b["sl"]["value"]),
        }
    return list(out.values())


# ---------------- Nokta-poligon (il/ilçe ataması) ----------------
def load_districts():
    d = json.load(open(DIST_FILE, encoding="utf-8"))
    polys = []
    for f in d["features"]:
        g = f["geometry"]
        rings = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poly in rings:
            xs = [p[0] for p in poly[0]]
            ys = [p[1] for p in poly[0]]
            polys.append((min(xs), min(ys), max(xs), max(ys), poly,
                          f["properties"]["province_tr"], f["properties"]["province_slug"],
                          f["properties"]["name_tr"]))
    return polys


def in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def locate(polys, lon, lat):
    for minx, miny, maxx, maxy, poly, il, slug, ilce in polys:
        if minx <= lon <= maxx and miny <= lat <= maxy and in_ring(lon, lat, poly[0]):
            if any(in_ring(lon, lat, hole) for hole in poly[1:]):
                continue
            return il, slug, ilce
    return None


def haversine_m(a, b):
    r = 6371000
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def norm(s):
    return re.sub(r"\s+", " ", (s or "").lower().replace("i̇", "i")).strip()


def commons_url(image_value):
    # http://commons.wikimedia.org/wiki/Special:FilePath/Foo.jpg -> https ... ?width=700
    if not image_value:
        return ""
    fn = urllib.parse.unquote(image_value.rsplit("/", 1)[-1])
    if re.search(r"\.(svg|tif|tiff|pdf)$", fn, re.I) or re.search(r"map|harita|flag|logo|locator", fn, re.I):
        return ""
    return "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(fn.replace(" ", "_")) + "?width=700"


# ---------------- Wikipedia görüntülenme (popülerlik) ----------------
def pageviews(title):
    end = date.today().replace(day=1)
    start = date(end.year - 1, end.month, 1)
    t = urllib.parse.quote(title.replace(" ", "_"), safe="")
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/tr.wikipedia/all-access/user/"
           f"{t}/monthly/{start:%Y%m%d}00/{end:%Y%m%d}00")
    d = http_json(url, retries=2)
    if not d:
        return 0
    return sum(i.get("views", 0) for i in d.get("items", []))


# Kesinlikle gezilecek yer olmayan türler: durak/istasyon, sıradağ, piskoposluk unvanı, abdest teknesi ...
WD_DROP_ALWAYS = {"Q2175765", "Q22808404", "Q15217609", "Q46831", "Q135476985", "Q135404256", "Q119168232", "Q5107",
                  "Q43229", "Q4830453", "Q783794", "Q891723", "Q1616075", "Q15265344", "Q1126006",  # kurum/şirket/TV
                  "Q178561", "Q188055", "Q1361229", "Q1190554"}  # savaş/kuşatma/olay
# Bölge / yarımada / tarihi şehir: kıta ölçekli olanlar (Anadolu, Balkanlar) atılır, Kapadokya/Haliç kalır
WD_REGION = {"Q34763", "Q82794", "Q1620908", "Q123705", "Q56061", "Q515"}
# Yerleşim: yalnızca antik kent / kale olarak kayıtlıysa kalır (Sardes, Hasankeyf Kalesi)
WD_SETTLEMENT = {"Q486972", "Q3957", "Q532", "Q1549591"}


def clean_wrong_links(existing, by_qid):
    qids = sorted(q for q in by_qid if re.match(r"^Q\d+$", q))
    types = {}
    for i in range(0, len(qids), 400):
        chunk = qids[i:i + 400]
        res = sparql("SELECT ?item ?c WHERE { VALUES ?item { %s } ?item wdt:P31 ?c . }"
                     % " ".join("wd:" + q for q in chunk))
        for row in (res or {}).get("results", {}).get("bindings", []):
            types.setdefault(row["item"]["value"].rsplit("/", 1)[-1], set()).add(row["c"]["value"].rsplit("/", 1)[-1])
        time.sleep(0.3)
    dropped = fixed = 0
    for slug, lst in existing.items():
        keep = []
        for p in lst:
            q = p.get("wikidata") or ""
            t = types.get(q, set())
            sl = p.get("_sl") or p.get("sl") or 0
            if "Q5" in t:
                # Türbe kaydı kişinin Wikidata kaydına bağlanmış → bağlantıyı kopar (puan şişmesin)
                for k in ("wikidata", "_sl", "sl", "pop"):
                    p.pop(k, None)
                p["img"] = ""  # görsel kişinin portresiydi, mekanın değil
                if str(p.get("id", "")).startswith("wd:"):
                    p["id"] = "tb:" + p["id"][3:]
                fixed += 1
            elif t & WD_DROP_ALWAYS:
                dropped += 1
                continue
            elif t & WD_REGION and sl >= 120:
                dropped += 1
                continue
            elif t & WD_SETTLEMENT and p.get("kategori") not in ("Antik Kent", "Kale / Hisar"):
                dropped += 1
                continue
            keep.append(p)
        lst[:] = keep
    print(f"Temizlik: {dropped} kayıt atıldı, {fixed} yanlış kişi bağlantısı düzeltildi")


def main():
    with_views = "--no-views" not in sys.argv
    polys = load_districts()

    # 1) Mevcut veri
    existing = {}
    for fn in os.listdir(OUT_DIR):
        if fn.endswith(".json") and not fn.startswith(("index", "_")):
            existing[fn[:-5]] = json.load(open(os.path.join(OUT_DIR, fn), encoding="utf-8"))

    # 2) Wikidata
    found = {}
    for qid, cat, need_article in CLASSES:
        rows = fetch_class(qid, need_article)
        added = 0
        for r in rows:
            if r["qid"] in found or JUNK_NAME.search(r["ad"]) or re.match(r"^Q\d+$", r["ad"]):
                continue
            # Maddesi ya da fotoğrafı olmayan, neredeyse hiç bilinmeyen kayıtları alma
            if not r["title"] and not r["image"] and r["sl"] < 2:
                continue
            r["kategori"] = cat
            found[r["qid"]] = r
            added += 1
        print(f"{qid:>10} {cat:<20} {len(rows):>5} kayıt, {added} yeni")
        time.sleep(1.0)

    # 3) Birleştir
    by_qid = {}
    for slug, lst in existing.items():
        for p in lst:
            q = p.get("wikidata") or (p.get("id", "")[3:] if p.get("id", "").startswith("wd:") else "")
            if q:
                by_qid[q] = p
    new_count, outside = 0, 0
    for r in found.values():
        p = by_qid.get(r["qid"])
        if p:
            if r["title"] and not p.get("wp"):
                p["wp"] = "tr:" + r["title"]
            p["_sl"] = r["sl"]
            continue
        loc = locate(polys, r["lon"], r["lat"])
        if not loc:
            outside += 1
            continue
        il, slug, ilce = loc
        lst = existing.setdefault(slug, [])
        n = norm(r["ad"])
        dup = next((x for x in lst if norm(x.get("ad")) == n and
                    haversine_m((x["lat"], x["lon"]), (r["lat"], r["lon"])) < 300), None)
        if dup:
            dup.setdefault("wikidata", r["qid"])
            if r["title"] and not dup.get("wp"):
                dup["wp"] = "tr:" + r["title"]
            dup["_sl"] = r["sl"]
            continue
        rec = {
            "id": "wd:" + r["qid"], "ad": r["ad"], "il": il, "ilce": ilce,
            "lat": round(r["lat"], 6), "lon": round(r["lon"], 6),
            "kategori": r["kategori"], "wikidata": r["qid"],
            "img": commons_url(r["image"]),
        }
        if r["title"]:
            rec["wp"] = rec["wiki"] = "tr:" + r["title"]
        rec["_sl"] = r["sl"]
        lst.append(rec)
        by_qid[r["qid"]] = rec
        new_count += 1
    print(f"Yeni eklenen mekan: {new_count} (Türkiye sınırı dışında kalan: {outside})")

    # 4a) Wikidata'dan gelmeyen eski kayıtların da dil sayısını (sitelinks) al → popülerlik sinyali
    need = [q for q, p in by_qid.items() if "_sl" not in p and re.match(r"^Q\d+$", q)]
    print(f"{len(need)} kaydın Wikipedia dil sayısı alınıyor...")
    for i in range(0, len(need), 250):
        chunk = need[i:i + 250]
        res = sparql("SELECT ?item ?sl ?title WHERE { VALUES ?item { %s } ?item wikibase:sitelinks ?sl . "
                     "OPTIONAL { ?a schema:about ?item; schema:isPartOf <https://tr.wikipedia.org/>; schema:name ?title . } }"
                     % " ".join("wd:" + q for q in chunk))
        for row in (res or {}).get("results", {}).get("bindings", []):
            q = row["item"]["value"].rsplit("/", 1)[-1]
            p = by_qid.get(q)
            if p is not None:
                p["_sl"] = int(row["sl"]["value"])
                if row.get("title") and not p.get("wp"):
                    p["wp"] = "tr:" + row["title"]["value"]
        time.sleep(0.5)

    # 4b) Yanlış bağlanmış kayıtları temizle (Wikidata P31 türüne göre; dil sayıları alındıktan sonra)
    clean_wrong_links(existing, by_qid)

    # 4c) Görüntülenme sayıları (Wikimedia hız sınırı varsa otomatik atlanır)
    if with_views and pageviews("Uzungöl") == 0:
        print("Wikimedia görüntülenme API'si şu an yanıt vermiyor (hız sınırı) — dil sayısı ile sıralanacak.")
        with_views = False
    if with_views:
        titles = {}
        for lst in existing.values():
            for p in lst:
                wp = p.get("wp") or p.get("wiki") or ""
                if isinstance(wp, str) and wp.startswith("tr:"):
                    titles.setdefault(wp[3:], []).append(p)
        print(f"{len(titles)} Wikipedia maddesinin görüntülenmesi alınıyor...")
        done = 0
        def work(t):
            return t, pageviews(t)
        with ThreadPoolExecutor(max_workers=8) as ex:
            for t, v in ex.map(work, list(titles)):
                for p in titles[t]:
                    p["pop"] = v
                done += 1
                if done % 500 == 0:
                    print(f"  {done}/{len(titles)}")

    # 5) Yaz
    index = {}
    total = 0
    for slug, lst in sorted(existing.items()):
        for p in lst:
            sl = p.pop("_sl", None)
            if sl is not None:
                p["sl"] = sl
        lst.sort(key=lambda p: (-(p.get("pop") or 0), -(p.get("sl") or 0), p.get("ad", "")))
        with open(os.path.join(OUT_DIR, slug + ".json"), "w", encoding="utf-8") as f:
            json.dump(lst, f, ensure_ascii=False, separators=(",", ":"))
        il = lst[0]["il"] if lst else slug
        index[il] = {"slug": slug, "count": len(lst),
                     "with_img": sum(1 for p in lst if (p.get("img") or "").strip())}
        total += len(lst)
    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    print(f"Toplam mekan: {total}")


if __name__ == "__main__":
    main()
