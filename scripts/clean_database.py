# -*- coding: utf-8 -*-
"""
scripts/clean_database.py
Cleans places and food databases:
1. Fixes misspelled place names and replaces generic English/corrupted labels.
2. Removes meaningless/garbage entries ('1', '?', 'small forest', 'ruins', single generic words).
3. Deduplicates places (exact IDs, identical names, and near-duplicate landmarks within 300m).
4. Cleans food database: removes closed restaurants, filters/prioritizes 3.5+ and 4.0+ score items, sorts descending.
5. Updates data/places/index.json counts.
"""

import os
import glob
import json
import re
import math
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES_DIR = os.path.join(BASE_DIR, 'data', 'places')
FOOD_DIR = os.path.join(BASE_DIR, 'data', 'food')
INDEX_FILE = os.path.join(PLACES_DIR, 'index.json')

# Explicit name corrections for Turkish historical/touristic landmarks
NAME_FIXES = {
    'Kapalı Carşı': 'Kapalı Çarşı',
    'Kapalı Carşi': 'Kapalı Çarşı',
    'Chiesa Sümbüllü Kilise': 'Sümbüllü Kilise',
    'Heroon of Trysa': 'Trysa Heroon Anıt Mezarı',
    'Heroon of Diodoros Pasparos': 'Diodoros Pasparos Heroon Anıtı',
    'Antiphellos Ancient Theatre': 'Antiphellos Antik Tiyatrosu',
    'Perge Theatre': 'Perge Antik Tiyatrosu',
    'Patara Theater': 'Patara Antik Tiyatrosu',
    'Amphitheater of Ancient Anabarzos': 'Anazarbos Antik Tiyatrosu',
    'Stadium of Ancient Anazarbos': 'Anazarbos Antik Stadyumu',
    'Theater at Ancient Anazarbos': 'Anazarbos Antik Tiyatro',
    'Courtyard bath and mosque': 'Avlu Hamamı ve Camii',
    'Arapsu bridge': 'Arapsu Köprüsü',
    'Ehmedek Castle': 'Ehmedek Kalesi',
    'Gedelme Castle': 'Gedelme Kalesi',
    'Gebedere Roman Bridge': 'Gebedere Roma Köprüsü',
    'Byzantian Church': 'Bizans Kilisesi',
    'Side Crown Palace Beach': 'Side Crown Palace Plajı',
    'Old Church / antik kilise': 'Antik Kilise',
    'KALE': 'Ankara Kalesi',
    'Perre Antik Kent': 'Perre Antik Kenti',
    'Perre': 'Perre Antik Kenti',
    'Ancyra': 'Ankara Ancyra Antik Kenti',
    'Monumentum Ancyranum': 'Augustus Tapınağı (Monumentum Ancyranum)',
}

# Generic / garbage / closed names to discard completely
GENERIC_DISCARD = {
    '1', '?', '45-180', 'small forest', 'tumulus', 'ruins', 'castle', 'church', 'mosque', 'bridge',
    'ruins and terraces', 'castle ruins', 'ruins (fountain?)', 'ancient house', 'theatre', 'church 1',
    'hephaistos temple ruins (lycian)', 'free viewpoint to waterfall', 'demircikara waterfall',
    'çeşme', 'hamam', 'köprü', 'türbe', 'harabeler', 'harabe', 'yıkık evler', 'yıkık yel değirmeni',
    'harabe hamam', 'isimsiz', 'adsız', 'bilinmeyen', 'han', 'kale', 'cami', 'camii', 'mescit',
    'closed for renovation'
}

def distance_meters(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def clean_name(name):
    if not name: return ""
    name = str(name).strip()
    if name in NAME_FIXES:
        return NAME_FIXES[name]
    # Remove surrounding quotes
    name = re.sub(r'^[\"\'\s]+|[\"\'\s]+$', '', name)
    # Fix multiple whitespaces
    name = re.sub(r'\s+', ' ', name)
    return name

def is_garbage_or_closed_place(p):
    raw_name = p.get('ad', '')
    name = clean_name(raw_name)
    lower = name.lower().strip()
    
    if len(name) <= 2:
        return True
    if re.match(r'^[\?\.\-\_\d\s]+$', name):
        return True
    if lower in GENERIC_DISCARD:
        return True
    if re.match(r'^(node|way|relation)/\d+$', lower):
        return True
    # Discard non-named single words or urls
    if lower.startswith('http://') or lower.startswith('https://'):
        return True
    if lower in ('small forest', 'tumulus', 'ruins', 'ancient theatre', 'castle', 'church', 'mosque'):
        return True
    return False

def place_score(p):
    score = 0
    img = p.get('img', '')
    if img and str(img).startswith('http'):
        score += 30
    if p.get('wiki'):
        score += 15
    if p.get('wikidata'):
        score += 10
    score += int(p.get('sl') or 0)
    if str(p.get('id', '')).startswith('wd:'):
        score += 5
    if p.get('ilce'):
        score += 2
    if p.get('kategori'):
        score += 1
    return score

def clean_places_database():
    print("=== TEMİZLİK 1: MEKANLAR VERİ TABANI (data/places/*.json) ===")
    total_before = 0
    total_after = 0
    total_discarded = 0
    total_merged = 0
    
    index_data = {}
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            index_data = json.load(f)
            
    files = glob.glob(os.path.join(PLACES_DIR, '*.json'))
    for fpath in files:
        fname = os.path.basename(fpath)
        if fname.startswith('_') or fname == 'index.json':
            continue
        slug = fname.replace('.json', '')
        
        with open(fpath, 'r', encoding='utf-8') as f:
            places = json.load(f)
        if not isinstance(places, list):
            continue
            
        total_before += len(places)
        
        # 1. Filtrele ve isim düzelt
        valid = []
        for p in places:
            if not isinstance(p, dict):
                continue
            if is_garbage_or_closed_place(p):
                total_discarded += 1
                continue
            p['ad'] = clean_name(p.get('ad', ''))
            valid.append(p)
            
        # 2. İsme ve Coğrafi Konuma Göre Tekilleştirme (Deduplication)
        # Önce isim grupları oluştur
        name_groups = defaultdict(list)
        for p in valid:
            norm_key = re.sub(r'[\s\-_]+', ' ', p['ad'].lower().strip())
            name_groups[norm_key].append(p)
            
        first_pass = []
        seen_ids = set()
        
        for norm_key, plist in name_groups.items():
            if len(plist) == 1:
                p = plist[0]
                if p['id'] not in seen_ids:
                    seen_ids.add(p['id'])
                    first_pass.append(p)
                else:
                    total_merged += 1
            else:
                # Birden fazla aynı isimli kayıt varsa en zenginini seç
                plist.sort(key=lambda x: place_score(x), reverse=True)
                primary = plist[0]
                for other in plist[1:]:
                    total_merged += 1
                    # Eksik verileri birleştir
                    if not primary.get('img') and other.get('img'):
                        primary['img'] = other['img']
                    if not primary.get('wiki') and other.get('wiki'):
                        primary['wiki'] = other['wiki']
                        primary['wp'] = other.get('wp', other['wiki'])
                    if not primary.get('wikidata') and other.get('wikidata'):
                        primary['wikidata'] = other['wikidata']
                    if not primary.get('ilce') and other.get('ilce'):
                        primary['ilce'] = other['ilce']
                if primary['id'] not in seen_ids:
                    seen_ids.add(primary['id'])
                    first_pass.append(primary)

        # 3. Yakın Mesafe Tekilleştirme (<200 metre mesafe ve çok benzer isim)
        final_list = []
        skip_indices = set()
        n = len(first_pass)
        
        for i in range(n):
            if i in skip_indices: continue
            p1 = first_pass[i]
            lat1, lon1 = p1.get('lat', 0), p1.get('lon', 0)
            n1 = p1.get('ad', '').lower()
            
            for j in range(i + 1, n):
                if j in skip_indices: continue
                p2 = first_pass[j]
                lat2, lon2 = p2.get('lat', 0), p2.get('lon', 0)
                n2 = p2.get('ad', '').lower()
                
                # İsimlerden biri diğerini içeriyorsa veya ilk 6 harfi aynıysa
                is_similar = (n1 in n2 or n2 in n1 or (len(n1) >= 6 and len(n2) >= 6 and n1[:6] == n2[:6]))
                if is_similar:
                    dist = distance_meters(lat1, lon1, lat2, lon2)
                    if dist < 200: # 200 metreden yakın aynı anıt/mekan
                        # Birleştir
                        total_merged += 1
                        skip_indices.add(j)
                        if place_score(p2) > place_score(p1):
                            # p2 daha iyi, p1'e p2'nin verilerini aktar
                            if p2.get('img'): p1['img'] = p2['img']
                            if p2.get('wiki'): p1['wiki'] = p2['wiki']; p1['wp'] = p2.get('wp', p2['wiki'])
                            if p2.get('wikidata'): p1['wikidata'] = p2['wikidata']
                            p1['ad'] = p2['ad'] # daha iyi ismi al
                        else:
                            if not p1.get('img') and p2.get('img'): p1['img'] = p2['img']
                            if not p1.get('wiki') and p2.get('wiki'): p1['wiki'] = p2['wiki']; p1['wp'] = p2.get('wp', p2['wiki'])
                            if not p1.get('wikidata') and p2.get('wikidata'): p1['wikidata'] = p2['wikidata']
            final_list.append(p1)
            
        total_after += len(final_list)
        
        # Dosyayı kaydet
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(final_list, f, ensure_ascii=False, separators=(',', ':'))
            
        # index_data güncelle
        for prov_name, pinfo in index_data.items():
            if pinfo.get('slug') == slug:
                pinfo['total'] = len(final_list)
                pinfo['with_img'] = sum(1 for p in final_list if (p.get('img') or '').strip().startswith('http'))
                
    if index_data:
        with open(INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
            
    print(f"Mekanlar Temizlendi:")
    print(f" - Toplam Mekan (Önce): {total_before}")
    print(f" - Çöpler / Anlamsız İsimler Silindi: {total_discarded}")
    print(f" - Mükerrer / Tekrarlanan Kayıtlar Birleştirildi: {total_merged}")
    print(f" - Kalan Temiz Mekan (Sonra): {total_after}")

def clean_food_database():
    print("\n=== TEMİZLİK 2: RESTORANLAR VERİ TABANI (data/food/*.json) ===")
    total_food_before = 0
    total_food_after = 0
    total_closed_removed = 0
    total_low_score_removed = 0
    total_duplicates_removed = 0
    
    files = glob.glob(os.path.join(FOOD_DIR, '*.json'))
    for fpath in files:
        with open(fpath, 'r', encoding='utf-8') as f:
            d = json.load(f)
        items = d.get('items', [])
        total_food_before += len(items)
        
        # 1. Kapalı veya geçersiz mekanları ele
        open_items = []
        for r in items:
            name = str(r.get('n', '')).strip()
            lower = name.lower()
            if any(w in lower for w in ['closed', 'kapatıldı', 'kapalı', 'disused', 'abandoned', 'renovation', 'yıkık']):
                total_closed_removed += 1
                continue
            if len(name) < 2 or re.match(r'^[\d\.\-\_]+$', name):
                total_closed_removed += 1
                continue
            open_items.append(r)
            
        # 2. Mükerrer restoranları birleştir / tekilleştir
        seen_names = set()
        deduped = []
        for r in open_items:
            norm = re.sub(r'\s+', ' ', r.get('n', '').lower().strip())
            # Aynı ilçe ve aynı isimse mükerrerdir
            key = f"{norm}|{r.get('i', '')}"
            if key in seen_names:
                total_duplicates_removed += 1
                continue
            seen_names.add(key)
            deduped.append(r)
            
        # 3. 3.5 ve 4.0 Üstü Mekanları Sırala ve Önceliklendir
        # Kullanıcı isteği: 3.5 ve 4 üstü mekanlar sıralansın
        # sc >= 3.5 olanları al; eğer ilde 3.5 üstü mekan azsa (örneğin < 5), en yüksek puanlıları koru
        high_score = [r for r in deduped if r.get('sc', 0) >= 3.5]
        if len(high_score) >= 5:
            filtered = high_score
            total_low_score_removed += (len(deduped) - len(high_score))
        else:
            # En az 5-10 mekan kalacak şekilde en yüksek skorluları tut
            deduped.sort(key=lambda x: x.get('sc', 0), reverse=True)
            filtered = deduped[:max(5, len(high_score))]
            total_low_score_removed += (len(deduped) - len(filtered))
            
        # 4. Kesin sıralama: En yüksek puanlı (sc) en üstte!
        filtered.sort(key=lambda x: (x.get('sc', 0), x.get('n', '')), reverse=True)
        total_food_after += len(filtered)
        
        # İlçe sayılarını yeniden hesapla
        counts = defaultdict(int)
        for r in filtered:
            ilce = r.get('i')
            if ilce:
                counts[ilce] += 1
                
        out = {
            "counts": dict(counts),
            "items": filtered
        }
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

    print(f"Restoranlar Temizlendi:")
    print(f" - Toplam Restoran (Önce): {total_food_before}")
    print(f" - Kapalı / Geçersiz Mekanlar Silindi: {total_closed_removed}")
    print(f" - Mükerrer Restoranlar Birleştirildi: {total_duplicates_removed}")
    print(f" - Düşük Puanlı (<3.5) Mekanlar Ayıklandı: {total_low_score_removed}")
    print(f" - Kalan 3.5+ ve 4.0+ Sıralı Restoran (Sonra): {total_food_after}")

if __name__ == '__main__':
    clean_places_database()
    clean_food_database()
