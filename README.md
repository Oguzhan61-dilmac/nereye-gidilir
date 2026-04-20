# nereye-gidilir

Bu asamada OpenStreetMap Overpass API kullanilarak Turkiye icin gezilecek yerler veri seti uretilir.
Ilk kapsam: Istanbul, Izmir, Antalya.

## Proje Yapisi

- `scripts/`
- `dataset/`
- `README.md`

## Kurulum

Python 3.10+ onerilir.

Gerekli paket:

```bash
pip install requests
```

## Top 1000 Uretim ve Entegrasyon

Mevcut `dataset/places_tr.json` korunur.

1) Turkiye geneli populer 1000 yeni kayit uret:

```bash
python scripts/build_dataset.py --top-tr 1000 --with-images --merge-in dataset/places_tr.json --out dataset/places_tr_top1000.json --merge-out dataset/places_tr_merged.json
```

2) Siteyi ac:

```bash
python -m http.server 5500
```

Notlar:
- Yeni kayitlarda `image_url` zorunludur; gercek gorsel bulunamazsa kayit eklenmez.
- Site veri kaynagi olarak `dataset/places_tr_merged.json` dosyasini kullanir.

## 5000 Hedefine Tamamlama

Var olan kayitlari bozmadan toplam kaydi hedefe tamamlar. Gercek gorsel bulunamayan adaylar eklenmez.

```bash
python scripts/build_dataset.py --with-images --merge-in dataset/places_tr_merged.json --target-total 5000 --out dataset/places_tr_top5000_merged.json --added-out dataset/places_tr_top5000_added.json
```

## Harita Sayfasi

- `map.html` sayfasinda Leaflet tabanli kesif ekrani vardir.
- Veri kaynagi `dataset/places_tr_top1000.json` dosyasidir.
- Filtreler: arama, il, kategori, yakinimdakiler.
- Paylasilabilir URL parametreleri: `map.html?il=...&kategori=...&q=...` ve `map.html?id=...`.

## Ana Sayfa Ilce Haritasi (SVG)

- Ana sayfada il secilince sag panelde ilce haritasi gosterilir.
- Ilce haritalari klasoru: `geo/ilceler/`
- Dosya formati: `geo/ilceler/{il_slug}.geojson`
- Demo dosya eklendi: `geo/ilceler/trabzon.geojson`
- Ilce geojson yoksa panelde: \"Bu il icin ilce haritasi yok\" mesaji gosterilir.
