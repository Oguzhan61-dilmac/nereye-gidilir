#!/usr/bin/env python3
"""
apply_commons_images.py — Commons konum aramasıyla bulunan görselleri data/places/*.json'a işler.

Girdi: her satırı "il-slug<TAB>mekan-id<TAB>Commons dosya adı" olan bir metin dosyası.
(Arama, yerin 0,8–1,5 km çevresinde çekilmiş ve dosya adında yerin ayırt edici adı geçen
 Commons fotoğraflarıyla yapılır; bu script ikinci bir süzgeç uygular.)

Kullanım:  python scripts/apply_commons_images.py sonuc.tsv
"""
import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES_DIR = os.path.join(ROOT, "data", "places")

STOP = set("""yaylasi yayla plaji plaj mesire alani parki park millet bahcesi kalesi kale camii cami muzesi muze
tabiat selalesi selale magarasi magara kanyonu kanyon koprusu kopru antik kenti kent aile halk mahallesi mahalle
seyir terasi noktasi tepesi tepe golu gol koyu koy sahil kordon botanik orman ormani kamp piknik buyuk kucuk eski
yeni tarihi harabeleri kalintilari hoyuk hoyugu kilisesi kilise manastiri turbesi turbe kervansarayi hani han
hamami kemeri kapisi dinlenme tesisleri the turkey turkiye museum castle beach plateau merkez merkezi sehir
belediye belediyesi cumhuriyet hukumet istasyon caddesi sokak meydani meydan""".split())
BAD = re.compile(r"(map|harita|logo|flag|bayrak|locator|location|plan|coat|arma|icon|signature|imza|portrait|portre|"
                 r"hotel|otel|resort|holiday|club|apart|pansiyon|bungalow|shop|leather|worker|işçi|cemetery|mezarlık|"
                 r"yangın|fire|accident|kaza|stadyum|stadium|station|istasyon|university|üniversite|faculty|fakülte|"
                 r"enstitü|boulevard|bulvar|street|caddesi|mahallesi|panoramik görünümü|tbmm|konser|maquette|maket|"
                 r"selfie|wedding|düğün|car |bus |train)", re.I)


def admin_tokens():
    """İl ve ilçe adları ayırt edici sayılmaz (ör. 'ADANA - panoramio' hiçbir yerin fotoğrafı değildir)."""
    toks = set()
    d = json.load(open(os.path.join(ROOT, "assets", "geo", "tr_districts_simplified.geojson"), encoding="utf-8"))
    for f in d["features"]:
        for k in ("name_tr", "province_tr"):
            for t in fold(f["properties"].get(k, "")).split():
                toks.add(t)
    return toks


def fold(s):
    s = (s or "").lower().replace("İ", "i").replace("I", "ı")
    for a, b in (("ı", "i"), ("ş", "s"), ("ğ", "g"), ("ü", "u"), ("ö", "o"), ("ç", "c"), ("â", "a"), ("î", "i")):
        s = s.replace(a, b)
    return re.sub(r"[_\-.,()'’\"]", " ", s)


def main():
    rows = [l.rstrip("\n").split("\t") for l in open(sys.argv[1], encoding="utf-8") if l.count("\t") == 2]
    admin = admin_tokens()
    # Aynı fotoğraf 2'den fazla yere atanmışsa hiçbirinin özgün fotoğrafı değildir
    usage = {}
    for _, _, fn in rows:
        usage[fn] = usage.get(fn, 0) + 1
    by_slug = {}
    for slug, pid, fn in rows:
        if usage[fn] > 2:
            continue
        by_slug.setdefault(slug, {})[pid] = fn
    applied = rejected = 0
    for slug, m in by_slug.items():
        path = os.path.join(PLACES_DIR, slug + ".json")
        if not os.path.exists(path):
            continue
        lst = json.load(open(path, encoding="utf-8"))
        for p in lst:
            fn = m.get(p["id"])
            if not fn or p.get("img"):
                continue
            toks = [t for t in fold(p["ad"]).split() if len(t) >= 4 and t not in STOP and t not in admin]
            ft = fold(fn)
            if not toks or not any(t in ft for t in toks) or BAD.search(fn) \
                    or not re.search(r"\.(jpe?g|png|webp)$", fn, re.I):
                rejected += 1
                continue
            p["img"] = "https://commons.wikimedia.org/wiki/Special:FilePath/" + \
                urllib.parse.quote(fn.replace(" ", "_")) + "?width=700"
            applied += 1
        with open(path, "w", encoding="utf-8") as f:
            json.dump(lst, f, ensure_ascii=False, separators=(",", ":"))
    idx_path = os.path.join(PLACES_DIR, "index.json")
    idx = json.load(open(idx_path, encoding="utf-8"))
    for v in idx.values():
        lst = json.load(open(os.path.join(PLACES_DIR, v["slug"] + ".json"), encoding="utf-8"))
        v["count"] = len(lst)
        v["with_img"] = sum(1 for x in lst if (x.get("img") or "").strip())
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)
    print(f"Uygulanan görsel: {applied}, elenen: {rejected}")


if __name__ == "__main__":
    main()
