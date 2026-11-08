#!/usr/bin/env python3
"""
enrich_images.py — data/places/*.json içinde fotoğrafı olmayan yerlere Wikimedia Commons görseli bulur.

Kaynaklar (yalnızca o yere ait olduğu bilinen görseller; tahmin yapılmaz):
  1) Wikidata P18 (görsel) — kaydın wikidata kimliği varsa
  2) Wikipedia maddesinin sayfa görseli (pageimages) — kaydın wp/wiki alanı varsa
  3) Wikidata'da aynı adlı ve 1 km yakındaki kayıt — adı birebir eşleşirse (OSM kaynaklı yerler için)

Kullanım:  python scripts/enrich_images.py
"""
import json
import os
import re
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_wikidata_enrich import sparql, http_json, norm, commons_url  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES_DIR = os.path.join(ROOT, "data", "places")
BAD_FILE = re.compile(r"(map|harita|logo|flag|bayrak|locator|location|plan|coat|arma|icon|svg$|tif$|pdf$|signature|imza)", re.I)


def file_url(fn):
    if not fn or BAD_FILE.search(fn) or not re.search(r"\.(jpe?g|png|webp)$", fn, re.I):
        return ""
    return "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(fn.replace(" ", "_")) + "?width=700"


def load_all():
    data = {}
    for fn in os.listdir(PLACES_DIR):
        if fn.endswith(".json") and not fn.startswith(("index", "_")):
            data[fn[:-5]] = json.load(open(os.path.join(PLACES_DIR, fn), encoding="utf-8"))
    return data


def main():
    data = load_all()
    missing = [p for lst in data.values() for p in lst if not (p.get("img") or "").strip()]
    print(f"Fotoğrafsız kayıt: {len(missing)}")
    found = 0

    # 1) Wikidata P18
    by_q = {}
    for p in missing:
        q = p.get("wikidata") or ""
        if re.match(r"^Q\d+$", q):
            by_q.setdefault(q, []).append(p)
    qs = list(by_q)
    for i in range(0, len(qs), 300):
        res = sparql("SELECT ?item ?img WHERE { VALUES ?item { %s } ?item wdt:P18 ?img . }"
                     % " ".join("wd:" + q for q in qs[i:i + 300]))
        for row in (res or {}).get("results", {}).get("bindings", []):
            q = row["item"]["value"].rsplit("/", 1)[-1]
            url = commons_url(row["img"]["value"])
            if url:
                for p in by_q.get(q, []):
                    if not p.get("img"):
                        p["img"] = url
                        found += 1
        time.sleep(0.5)
    print(f"  Wikidata P18: {found}")

    # 2) Wikipedia sayfa görseli (dil başına 50 madde/istek)
    by_lang = {}
    for p in missing:
        if p.get("img"):
            continue
        ref = str(p.get("wp") or p.get("wiki") or "")
        m = re.match(r"^([a-z]{2,3}):(.+)$", ref)
        if m:
            by_lang.setdefault(m.group(1), {}).setdefault(m.group(2), []).append(p)
    before = found
    for lang, titles in by_lang.items():
        tl = list(titles)
        for i in range(0, len(tl), 50):
            chunk = tl[i:i + 50]
            url = (f"https://{lang}.wikipedia.org/w/api.php?action=query&format=json&formatversion=2"
                   f"&prop=pageimages&piprop=name&redirects=1&titles=" + urllib.parse.quote("|".join(chunk)))
            d = http_json(url, retries=3)
            if not d:
                continue
            q = d.get("query", {})
            alias = {}
            for r in q.get("normalized", []) + q.get("redirects", []):
                alias[r["to"]] = alias.get(r["from"], r["from"])
            for page in q.get("pages", []):
                img = file_url(page.get("pageimage", ""))
                if not img:
                    continue
                t = page["title"]
                orig = t
                while orig in alias:
                    orig = alias[orig]
                for key in {t, orig, t.replace(" ", "_"), orig.replace("_", " ")}:
                    for p in titles.get(key, []):
                        if not p.get("img"):
                            p["img"] = img
                            found += 1
            time.sleep(0.3)
    print(f"  Wikipedia sayfa görseli: {found - before}")

    # 3) Aynı ad + 1 km içinde Wikidata kaydı (OSM kaynaklı yerler)
    before = found
    cand = [p for p in missing if not p.get("img") and not p.get("wikidata")
            and str(p.get("id", "")).startswith(("node:", "way:"))]
    print(f"  Ad/konum eşleşmesi denenecek: {len(cand)}")
    for i in range(0, len(cand), 40):
        chunk = cand[i:i + 40]
        values = " ".join(f'("{c["ad"].replace(chr(34), "")}"@tr "Point({c["lon"]} {c["lat"]})"^^geo:wktLiteral {j})'
                          for j, c in enumerate(chunk))
        res = sparql("""SELECT ?j ?item ?img WHERE {
  VALUES (?name ?pt ?j) { %s }
  ?item rdfs:label ?name ; wdt:P625 ?loc ; wdt:P18 ?img .
  FILTER(geof:distance(?loc, ?pt) < 1)
}""" % values)
        for row in (res or {}).get("results", {}).get("bindings", []):
            c = chunk[int(row["j"]["value"])]
            url = commons_url(row["img"]["value"])
            if url and not c.get("img"):
                c["img"] = url
                c["wikidata"] = row["item"]["value"].rsplit("/", 1)[-1]
                found += 1
        time.sleep(0.4)
        if (i // 40) % 50 == 0:
            print(f"    {i}/{len(cand)}  (+{found - before})")
    print(f"  Ad/konum eşleşmesi: {found - before}")

    for slug, lst in data.items():
        with open(os.path.join(PLACES_DIR, slug + ".json"), "w", encoding="utf-8") as f:
            json.dump(lst, f, ensure_ascii=False, separators=(",", ":"))
    idx_path = os.path.join(PLACES_DIR, "index.json")
    idx = json.load(open(idx_path, encoding="utf-8"))
    for il, v in idx.items():
        lst = data.get(v.get("slug"), [])
        v["count"] = len(lst)
        v["with_img"] = sum(1 for x in lst if (x.get("img") or "").strip())
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)
    print(f"Toplam yeni görsel: {found}")


if __name__ == "__main__":
    main()
