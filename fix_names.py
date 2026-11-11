# -*- coding: utf-8 -*-
"""
fix_names.py
data/places/ klasöründeki JSON dosyalarında mekanların ana isimleri (ad/name) ile
Wikipedia kaynaklı açıklama ve başlık metinleri arasındaki ufak yazım/harf hatalarını
difflib.SequenceMatcher kullanarak tespit eder ve düzeltir.
"""

import os
import glob
import json
import difflib
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLACES_DIR = os.path.join(BASE_DIR, 'data', 'places')


def extract_target_name_from_desc_or_wiki(place: dict) -> str:
    """
    Mekanın description metninden (veya Wikipedia wp/wiki alanından)
    doğru asıl isim kısmını çıkarır.
    """
    desc = place.get("description") or ""
    if desc and isinstance(desc, str):
        desc = desc.strip()
        # Virgüle, tireye veya ' - ' işaretine kadar olan asıl isim kısmı
        cand = re.split(r'[,–—\-]', desc)[0].strip()
        cand = re.sub(r'^[„"\'«“]+|[”"\'»\.\s]+$', '', cand).strip()
        words = cand.split()
        if len(words) > 4:
            cand = ' '.join(words[:4])
        return cand.strip()

    # Eğer description alanı JSON içinde yoksa, Wikipedia (wp/wiki) başlığından türet
    wp = place.get("wp") or place.get("wiki") or ""
    if wp and isinstance(wp, str):
        if wp.startswith("tr:"):
            wp = wp[3:]
        elif ":" in wp:
            return ""  # Yabancı dil ön eklerini atla
        # Parantez içi açıklama/ayırt ediciyi temizle (örn. 'Taşköprü (Adana)' -> 'Taşköprü')
        wp = re.sub(r'\s*\([^)]*\)', '', wp).strip()
        wp = re.sub(r'^[„"\'«“]+|[”"\'»\.\s]+$', '', wp).strip()
        return wp

    return ""


def fix_place_names():
    json_pattern = os.path.join(PLACES_DIR, "*.json")
    files = sorted(glob.glob(json_pattern))

    total_fixed = 0
    modified_files = 0
    changed_examples = []

    for file_path in files:
        file_name = os.path.basename(file_path)
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

        file_has_changes = False

        for place in data:
            if not isinstance(place, dict):
                continue

            current_name = place.get("ad") or place.get("name") or ""
            current_name = str(current_name).strip()
            if not current_name:
                continue

            target_name = extract_target_name_from_desc_or_wiki(place)
            new_name = None

            # 1. Manuel kural: "Gürlevik Şelalesi" -> "Girlevik Şelalesi"
            if current_name == "Gürlevik Şelalesi":
                new_name = "Girlevik Şelalesi"

            # 2. Akıllı benzerlik kontrolü (difflib SequenceMatcher: %85 - %98 arası)
            elif target_name and current_name != target_name:
                ratio = difflib.SequenceMatcher(
                    None,
                    current_name.lower(),
                    target_name.lower()
                ).ratio()

                if 0.85 <= ratio <= 0.98:
                    new_name = target_name

            # Eğer düzeltme gerekiyorsa güncelle
            if new_name and new_name != current_name:
                if "ad" in place:
                    place["ad"] = new_name
                if "name" in place:
                    place["name"] = new_name

                total_fixed += 1
                file_has_changes = True

                if len(changed_examples) < 20:
                    changed_examples.append((current_name, new_name, file_name))

        if file_has_changes:
            modified_files += 1
            with open(file_path, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, separators=(',', ':'))

    # Raporlama
    print(f"Toplam {total_fixed} adet mekanın ismi Wikipedia açıklamasına göre düzeltildi.\n")
    if changed_examples:
        print("Değiştirilen bazı örnek isimler (Eski -> Yeni):")
        for old_val, new_val, prov in changed_examples:
            print(f"  • [{prov}] {old_val} -> {new_val}")
    print(f"\nToplam {modified_files} ilin JSON dosyası güncellendi.")


if __name__ == "__main__":
    fix_place_names()
