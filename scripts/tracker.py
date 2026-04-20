import json
import os
from pathlib import Path

def main():
    root = Path(__file__).resolve().parents[1]
    dataset_path = root / "dataset" / "places_tr.json"
    images_dir = root / "images" / "places"
    
    if not dataset_path.exists():
        print("Dataset dosyası henüz oluşturulmamış veya okunmuyor...")
        return
        
    try:
        with open(dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            total_places = len(data)
    except Exception as e:
        print("Dataset okunamadı:", e)
        return

    if not images_dir.exists():
        downloaded_count = 0
    else:
        # count files
        downloaded_count = len([f for f in os.listdir(images_dir) if f.endswith('.jpg') or f.endswith('.png')])
        
    if total_places == 0:
        print("Dataset içinde henüz kayıt yok. Veri toplanıyor olabilir...")
        return
        
    percent = (downloaded_count / total_places) * 100
    
    print("========================================")
    print("   NEREYE GİDİLİR - VERİ YÜKLEME DURUMU  ")
    print("========================================")
    print(f"Toplam Hedef Mekan Sayısı : {total_places:,}")
    print(f"Şu Ana Kadar İnen Görsel  : {downloaded_count:,}")
    print(f"Kalan Mekan Sayısı        : {total_places - downloaded_count:,}")
    print(f"Tamamlanma Yüzdesi        : %{percent:.2f}")
    
    # Kalanı görsel progress bar şeklinde göster:
    bar_length = 40
    filled_len = int(bar_length * downloaded_count // total_places)
    bar = '█' * filled_len + '-' * (bar_length - filled_len)
    print(f"\nİlerleme: |{bar}| %{percent:.2f}")
    print("========================================")

if __name__ == "__main__":
    main()
