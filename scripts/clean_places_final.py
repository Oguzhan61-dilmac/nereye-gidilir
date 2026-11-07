#!/usr/bin/env python3
"""
clean_places_final.py — 81 ilin data/places/*.json dosyalarında:
1) İlçe adlarını temizler ('Prince Islands' -> 'Adalar', 'Giresun District' -> 'Merkez',
   'Kilis (merkez)' / 'Elazığ merkez' -> 'Merkez').
2) Mekan adlarındaki gereksiz tırnakları, görünmez karakterleri ve sonda tekrarlanan
   ', Trabzon' / '(Trabzon)' gibi il/ilçe eklerini temizler.
3) Tarihsel olayları (muharebe, saldırı, kaza, deprem vb.), modern kamu/sanayi binalarını
   (adalet sarayı, hizmet binası, büyükelçilik, rafineri, sınır kapısı vb.) ve il/ilçe
   adının kendisi olan yerleşim kayıtlarını eler.
"""
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES_DIR = os.path.join(ROOT, "data", "places")

BAD_PLACE_NAME = re.compile(
    r"(\b(kazası|saldırısı|darbe|girişimi|muharebesi|savaşı|kuşatması|depremi|patlaması|"
    r"yangını|çatışması|katliamı|suikastı|ayaklanması|isyanı|olayı|baskını|harekatı|harekâtı|"
    r"adalet sarayı|adliyesi|hizmet binası|belediye binası|valiliği|kaymakamlığı|"
    r"büyükelçiliği|konsolosluğu|rafineri\w*|sınır kapısı|barajı|santrali|havalimanı|havaalanı|"
    r"stadyumu|stadyum|spor salonu|üniversitesi|fakültesi|lisesi|ilkokulu|ortaokulu|"
    r"hastanesi|cezaevi|hapishanesi|mezarlığı|organize sanayi|otogarı|istasyonu|garı)\b"
    r"|^(1\d{3}|20\d{2})\s+(?!yıl))",
    re.I,
)


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


def clean_district(ilce, il):
    d = (ilce or "").strip()
    if not d:
        return "Merkez"
    if d == "Prince Islands":
        return "Adalar"
    if d == "Giresun District":
        return "Merkez"
    if d == "Gediz Merkez":
        return "Gediz"
    if d == "Merkezefendi":
        return "Merkezefendi"
    low = d.replace("İ", "i").replace("I", "ı").lower()
    if "merkez" in low:
        return "Merkez"
    return d


def clean_name(ad, il, ilce):
    s = (ad or "").replace("\u200b", "").strip().strip('"').strip("'").strip()
    # Sonda "(Trabzon)" veya ", Trabzon" veya ", Ortahisar" varsa temizle
    for loc in (il, ilce):
        if not loc:
            continue
        s = re.sub(rf"\s*\(\s*{re.escape(loc)}\s*\)\s*$", "", s, flags=re.I)
        s = re.sub(rf"\s*,\s*{re.escape(loc)}\s*$", "", s, flags=re.I)
    return s.strip()


def main():
    index_path = os.path.join(PLACES_DIR, "index.json")
    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)

    slug_to_il = {v["slug"]: k for k, v in index.items()}
    done = {}
    tot_all, tot_img = 0, 0
    removed = 0

    for slug, il in sorted(slug_to_il.items()):
        path = os.path.join(PLACES_DIR, f"{slug}.json")
        with open(path, encoding="utf-8") as f:
            places = json.load(f)

        cleaned = []
        seen = set()
        for p in places:
            ilce = clean_district(p.get("ilce", ""), il)
            ad = clean_name(p.get("ad", ""), il, ilce)
            if not ad or len(ad) < 3:
                removed += 1
                continue
            if BAD_PLACE_NAME.search(ad):
                removed += 1
                continue
            ad_n = norm(ad)
            # İl veya ilçe adının birebir kendisi olan yerleşim maddelerini çıkar
            if ad_n in {norm(il), norm(ilce)}:
                removed += 1
                continue
            if ad_n in seen:
                # Eğer önceki kayıtta img yok ama bunda varsa güncelle
                for prev in cleaned:
                    if norm(prev["ad"]) == ad_n and not prev.get("img") and p.get("img"):
                        prev["img"] = p["img"]
                        if p.get("wp") and not prev.get("wp"):
                            prev["wp"] = p["wp"]
                continue
            seen.add(ad_n)
            p["ad"] = ad
            p["ilce"] = ilce
            p["img"] = p.get("img") or ""
            cleaned.append(p)

        # Sadece o mekana ait olduğu doğrulanmış fotoğrafı olan kayıtları tut
        cleaned = [p for p in cleaned if p.get("img") and p["img"].strip()]
        cleaned.sort(key=lambda r: (0 if r.get("wp") else 1, r["ad"]))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, separators=(",", ":"))

        k = sum(1 for item in cleaned if item.get("img"))
        tot_all += len(cleaned)
        tot_img += k
        index[il] = {"slug": slug, "count": len(cleaned), "with_img": k}
        done[slug] = {"places": len(cleaned), "with_img": k}

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    with open(os.path.join(PLACES_DIR, "_images_done.json"), "w", encoding="utf-8") as f:
        json.dump(done, f, ensure_ascii=False, indent=1)

    print(f"Temizlendi ({removed} uygunsuz/tekrar kayıt çıkarıldı).")
    print(f"GÜNCEL TOPLAM: 81 ilde {tot_all} mekan, {tot_img} doğrulanmış fotoğraflı mekan!")


if __name__ == "__main__":
    main()
