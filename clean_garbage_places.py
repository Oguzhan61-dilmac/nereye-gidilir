# -*- coding: utf-8 -*-
"""
clean_garbage_places.py
data/places/ klasöründeki il JSON dosyalarında Wikipedia'dan yanlışlıkla çekilmiş
ülke isimleri ("Türkiye"), salgın/pandemi maddeleri ("COVID-19"), siyasi/tarihsel olaylar
ve konsiller, ille uyumsuz koordinat/görseller ve genel ansiklopedik maddeleri temizleyen script.
"""

import os
import glob
import json
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLACES_DIR = os.path.join(BASE_DIR, 'data', 'places')
INDEX_FILE = os.path.join(PLACES_DIR, 'index.json')
IMAGES_DONE_FILE = os.path.join(PLACES_DIR, '_images_done.json')


def tr_lower(text: str) -> str:
    """Türkçe karakterleri doğru küçük harfe çevirir."""
    if not text:
        return ""
    return str(text).replace("İ", "i").replace("I", "ı").lower().strip()


# 1. Ülke veya makro bölge adları (tam eşleşme veya genel kavram)
COUNTRY_OR_REGION_EXACT = {
    'türkiye', 'turkey', 'türkiye cumhuriyeti', 'osmanlı imparatorluğu',
    'kuzey kıbrıs türk cumhuriyeti', 'balkans', 'balkanlar'
}

# 2. Pandemi ve salgın regex kalıbı
PANDEMIC_REGEX = re.compile(
    r'\b(covid|covid-19|pandemi|pandemisi|koronavirüs|korona|salgını)\b',
    re.IGNORECASE
)

# 3. Tarihsel olay, konsil, katliam, ayaklanma (fiziki mekan/müze/anıt olmayanlar)
EVENT_REGEX = re.compile(
    r'\b(konsili|katliamı|olayları|isyanı|ayaklanması|darbesi|ihtilali)\b',
    re.IGNORECASE
)

# 4. Soyut mekan/olay ifadeleri ("... gerçekleştiği yer", "... doğduğu yer")
ABSTRACT_PHRASE_REGEX = re.compile(
    r'\b(gerçekleştiği yer|doğduğu yer|yaşandığı yer|öldüğü yer)\b',
    re.IGNORECASE
)

# 5. İdari kurum, federasyon, ülke sınırı (fiziki turistik alan olmayanlar)
ADMIN_BOUNDARY_REGEX = re.compile(
    r'\b(federasyonu|konfederasyonu|sınırı|başkonsolosluğu|büyükelçiliği)\b',
    re.IGNORECASE
)

# 6. Başlık ve görsel uyumsuzluğu / genel ansiklopedi görselleri
BAD_IMAGE_KEYWORDS = [
    'herzog', 'flag_of', 'coat_of_arms', 'emblem_of', 'seal_of',
    'rise_of_ottoman', 'protester_wearing_gas_mask', 'council_of_nicea',
    'karte_suedosteuropa'
]

# 7. Korunması gereken meşru mekan terimleri (yanlışlıkla silinmeyi önler)
PROTECTED_TERMS_REGEX = re.compile(
    r'\b(müze|müzesi|anıt|anıtı|şehitlik|şehitliği|abide|abidesi|millî park|milli park|'
    r'tarihî alan|tarihi alan|parkı|bahçesi|meydanı|köprüsü|çarşısı|çeşmesi|cami|camii|'
    r'kilise|kilisesi|hamam|hamamı|sarayı|köşkü|konağı|kalesi|külliyesi|medresesi|'
    r'kitaplığı|kütüphanesi|kampı|plajı|koyu|şelalesi|mağarası|gölü|dağı|tepesi|vadisi)\b',
    re.IGNORECASE
)


def is_garbage_place(item: dict, province_slug: str) -> tuple[bool, str]:
    """
    Bir mekan kaydının çöp/hatalı genel madde olup olmadığını denetler.
    Silinmesi gerekiyorsa (True, gerekçe) döner.
    """
    if not isinstance(item, dict):
        return True, "Geçersiz obje"

    ad = str(item.get("ad") or item.get("name") or "").strip()
    wp = str(item.get("wp") or item.get("wiki") or "").strip()
    img = str(item.get("img") or item.get("image") or "").strip()
    lat = item.get("lat")
    lon = item.get("lon")

    ad_clean = ad.strip(" '\"„“«»")
    ad_low = tr_lower(ad_clean)
    wp_low = tr_lower(wp)
    img_low = tr_lower(img)

    # A. Ülke / Bölge / Siyasi kavramlar
    if ad_low in COUNTRY_OR_REGION_EXACT:
        return True, f"Ülke/bölge kavramı: '{ad}'"

    if (ad_low.startswith("türkiye'de ") or ad_low.startswith("türkiye’de ") or ad_low == "türkiye cumhuriyeti") and not PROTECTED_TERMS_REGEX.search(ad):
        return True, f"Genel Türkiye maddesi: '{ad}'"

    # B. Pandemi ve salgın maddeleri
    if PANDEMIC_REGEX.search(ad_low) or PANDEMIC_REGEX.search(wp_low):
        return True, f"Pandemi/salgın maddesi: '{ad}'"

    # C. Tarihsel olaylar, konsiller, katliamlar
    if EVENT_REGEX.search(ad_low) and not PROTECTED_TERMS_REGEX.search(ad):
        return True, f"Tarihsel olay/konsil/katliam: '{ad}'"

    # D. Soyut mekan/olay ifadeleri
    if ABSTRACT_PHRASE_REGEX.search(ad_low):
        return True, f"Soyut mekan/olay kaydı: '{ad}'"

    # E. İdari federasyon / sınır hatları
    if ADMIN_BOUNDARY_REGEX.search(ad_low) and not PROTECTED_TERMS_REGEX.search(ad):
        return True, f"İdari kurum/sınır çizgisi: '{ad}'"

    # F. Genel ansiklopedik taşıt/araç maddesi
    if "douglas dc-3" in ad_low and "müze" not in ad_low:
        return True, f"Genel uçak/araç maddesi: '{ad}'"

    # G. Coğrafi koordinat eşleşmesi Türkiye sınırları dışında olanlar
    if lat is not None and lon is not None:
        try:
            lat_f, lon_f = float(lat), float(lon)
            if not (35.0 <= lat_f <= 43.0 and 25.0 <= lon_f <= 45.0):
                return True, f"Türkiye dışı koordinat: lat={lat_f}, lon={lon_f}"
        except (ValueError, TypeError):
            return True, "Geçersiz koordinat verisi"

    # H. Başlık ve görsel uyumsuzluğu (ansiklopedik/siyasi fotoğraflar)
    for bad_kw in BAD_IMAGE_KEYWORDS:
        if bad_kw in img_low:
            return True, f"Hatalı/uyumsuz görsel ({bad_kw})"

    # İstanbul tarihi yarımada/silüet görseli başka ilin kaydında ise
    if ("skyline_of_istanbul" in img_low or "historical_peninsula" in img_low) and province_slug != "istanbul":
        return True, f"İstanbul silüeti başka ilde ({province_slug})"

    # I. 'description' alanı kontrolü (varsa)
    if "description" in item:
        desc = item.get("description")
        if desc is None:
            return True, "description alanı None"
        desc_str = str(desc).strip()
        if not desc_str:
            return True, "description alanı boş"
        if len(desc_str.split()) <= 2:
            return True, f"description alanı çok kısa ({len(desc_str.split())} kelime)"

    return False, ""


def clean_garbage_places():
    json_pattern = os.path.join(PLACES_DIR, "*.json")
    files = sorted(glob.glob(json_pattern))

    total_deleted = 0
    total_remaining = 0
    modified_files = 0
    deleted_items_summary = []
    stats_per_province = {}

    for file_path in files:
        file_name = os.path.basename(file_path)
        if file_name in ("index.json", "_images_done.json") or file_name.startswith("_"):
            continue

        prov_slug = file_name.replace(".json", "")

        try:
            with open(file_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except Exception as e:
            print(f"Hata: {file_name} okunamadı: {e}")
            continue

        if not isinstance(data, list):
            continue

        clean_list = []
        deleted_in_this_file = 0

        for item in data:
            is_bad, reason = is_garbage_place(item, prov_slug)
            if is_bad:
                deleted_in_this_file += 1
                ad = str(item.get("ad") or item.get("name") or "İsimsiz")
                pid = str(item.get("id") or "")
                deleted_items_summary.append((prov_slug, pid, ad, reason))
            else:
                clean_list.append(item)

        if deleted_in_this_file > 0:
            modified_files += 1
            with open(file_path, "w", encoding="utf-8") as fp:
                json.dump(clean_list, fp, ensure_ascii=False, separators=(',', ':'))

        total_deleted += deleted_in_this_file
        total_remaining += len(clean_list)
        stats_per_province[file_name] = len(clean_list)

    # index.json dosyasını güncelle
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as fp:
                index_data = json.load(fp)

            for prov_name, prov_info in index_data.items():
                if isinstance(prov_info, dict) and "slug" in prov_info:
                    slug_file = f"{prov_info['slug']}.json"
                    if slug_file in stats_per_province:
                        prov_info["total"] = stats_per_province[slug_file]
                        if "count" in prov_info:
                            prov_info["count"] = stats_per_province[slug_file]

            with open(INDEX_FILE, "w", encoding="utf-8") as fp:
                json.dump(index_data, fp, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Uyarı: index.json güncellenirken hata: {e}")

    # _images_done.json dosyasını da güncelle (varsa)
    if os.path.exists(IMAGES_DONE_FILE):
        try:
            with open(IMAGES_DONE_FILE, "r", encoding="utf-8") as fp:
                done_data = json.load(fp)

            for slug, info in done_data.items():
                slug_file = f"{slug}.json"
                if slug_file in stats_per_province and isinstance(info, dict):
                    info["places"] = stats_per_province[slug_file]

            with open(IMAGES_DONE_FILE, "w", encoding="utf-8") as fp:
                json.dump(done_data, fp, ensure_ascii=False, indent=1)
        except Exception as e:
            print(f"Uyarı: _images_done.json güncellenirken hata: {e}")

    # Raporlama
    print(f"\nToplam {total_deleted} adet hatalı genel madde (Türkiye, pandemi vb.) veritabanından temizlendi.")
    print(f"Temizlenen {modified_files} ilin dosyası güncellendi. Kalan toplam temiz mekan sayısı: {total_remaining}\n")

    if deleted_items_summary:
        print("Temizlenen hatalı kayıtlar:")
        for prov, pid, name, reason in deleted_items_summary:
            print(f"  • [{prov}] ({pid}) {name} -> Neden: {reason}")


if __name__ == "__main__":
    clean_garbage_places()
