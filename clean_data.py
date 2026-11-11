# -*- coding: utf-8 -*-
"""
clean_data.py
data/places/ klasöründeki il JSON dosyalarını tarayarak yabancı dilli (Kiril/Rusça,
Yunanca, Arapça vb.) ve hatalı/boş/anlamsız mekan kayıtlarını temizleyen script.
"""

import os
import glob
import json
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLACES_DIR = os.path.join(BASE_DIR, 'data', 'places')
INDEX_FILE = os.path.join(PLACES_DIR, 'index.json')

# Yabancı alfabe regex kalıpları
CYRILLIC_REGEX = re.compile(r'[\u0400-\u04FF]')
GREEK_REGEX    = re.compile(r'[\u0370-\u03FF]')
ARABIC_REGEX   = re.compile(r'[\u0600-\u06FF]')
GEORGIAN_REGEX = re.compile(r'[\u10A0-\u10FF]')

# Yabancı Wikipedia/Wikidata ön ekleri (Türkçe/İngilizce dışındaki dillerden özet çekilmesini engeller)
FOREIGN_WIKI_PREFIX = re.compile(r'^(ru|el|ar|uk|bg|sr|fa|he|hy|ka):', re.IGNORECASE)


def has_foreign_alphabet(text: str) -> bool:
    """Metin Kiril, Yunanca, Arapça veya Gürcüce gibi yabancı alfabe içeriyor mu?"""
    if not text or not isinstance(text, str):
        return False
    return bool(
        CYRILLIC_REGEX.search(text) or
        GREEK_REGEX.search(text) or
        ARABIC_REGEX.search(text) or
        GEORGIAN_REGEX.search(text)
    )


def is_problematic_place(item: dict) -> tuple[bool, str]:
    """
    Bir mekan kaydının hatalı veya yabancı dilli olup olmadığını kontrol eder.
    (Hatalı ise True ve silinme nedenini döner).
    """
    if not isinstance(item, dict):
        return True, "Geçersiz veri objesi"

    # 1. 'description' (açıklama) alanının kontrolü
    if "description" in item:
        desc = item.get("description")
        if desc is None:
            return True, "description alanı None"
        desc_str = str(desc).strip()
        if not desc_str:
            return True, "description alanı tamamen boş"
        words = desc_str.split()
        if len(words) <= 2:
            return True, f"description alanı çok kısa ({len(words)} kelime)"
        if has_foreign_alphabet(desc_str):
            return True, "description alanı yabancı alfabe içeriyor"

    # 2. 'ad' (isim) alanının kontrolü
    ad = str(item.get("ad") or "").strip()
    if not ad:
        return True, "Mekan adı boş"
    if has_foreign_alphabet(ad):
        return True, f"Mekan adı yabancı alfabe içeriyor ({ad})"

    # 3. 'wiki' ve 'wp' (Vikipedi özet/bağlantı) alanlarının kontrolü
    for field in ("wp", "wiki"):
        val = str(item.get(field) or "").strip()
        if val:
            if has_foreign_alphabet(val):
                return True, f"{field} alanı yabancı alfabe içeriyor ({val})"
            if FOREIGN_WIKI_PREFIX.match(val):
                return True, f"{field} alanı yabancı dil ön eki içeriyor ({val})"

    # 4. Diğer metin alanlarında yabancı alfabe taraması (kategori, ilce vb.)
    for k, v in item.items():
        if isinstance(v, str) and k not in ("description", "ad", "wp", "wiki", "id", "img", "image"):
            if has_foreign_alphabet(v):
                return True, f"{k} alanı yabancı alfabe içeriyor ({v})"

    return False, ""


def clean_places_database():
    json_pattern = os.path.join(PLACES_DIR, "*.json")
    files = sorted(glob.glob(json_pattern))

    total_deleted = 0
    total_remaining = 0
    modified_files = 0
    stats_per_province = {}

    for file_path in files:
        file_name = os.path.basename(file_path)
        # Özel dosyaları atla
        if file_name in ("index.json", "_images_done.json") or file_name.startswith("_"):
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except Exception as e:
            print(f"Hata: {file_name} okunamadı: {e}")
            continue

        if not isinstance(data, list):
            continue

        original_count = len(data)
        clean_data = []
        deleted_in_file = 0

        for item in data:
            problematic, reason = is_problematic_place(item)
            if problematic:
                deleted_in_file += 1
            else:
                clean_data.append(item)

        if deleted_in_file > 0:
            modified_files += 1
            # Temizlenmiş listeyi aynı dosyanın üzerine UTF-8 olarak kaydet
            with open(file_path, "w", encoding="utf-8") as fp:
                json.dump(clean_data, fp, ensure_ascii=False, separators=(',', ':'))

        total_deleted += deleted_in_file
        total_remaining += len(clean_data)
        stats_per_province[file_name] = len(clean_data)

    # index.json dosyasını da güncel sayılarla eşitle
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as fp:
                index_data = json.load(fp)
            
            for prov_name, prov_info in index_data.items():
                if isinstance(prov_info, dict) and "slug" in prov_info:
                    slug_file = f"{prov_info['slug']}.json"
                    if slug_file in stats_per_province:
                        prov_info["total"] = stats_per_province[slug_file]

            with open(INDEX_FILE, "w", encoding="utf-8") as fp:
                json.dump(index_data, fp, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Uyarı: index.json güncellenirken hata: {e}")

    # 4. Raporlama
    print(f"Toplam {total_deleted} adet yabancı dilli/hatalı mekan silindi. Kalan toplam temiz mekan sayısı: {total_remaining}")
    if modified_files > 0:
        print(f"Toplam {modified_files} ilin JSON dosyası başarıyla güncellendi.")


if __name__ == "__main__":
    clean_places_database()
