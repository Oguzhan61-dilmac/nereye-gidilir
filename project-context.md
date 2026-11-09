# GEZİ ATLASI (`geziatlasi.com.tr`) — MASTER PROJECT CONTEXT & DEVİR TESLİM REHBERİ

> **Yapay Zeka Asistanına (Claude) Not:**  
> Bu belge, **Gezi Atlası (`https://geziatlasi.com.tr`)** projesinin tüm dosya yapısını, mimarisini, veri şemasını, tasarım dilini ve uygulanan kritik performans/mobil optimizasyonlarını eksiksiz olarak aktarmak için hazırlanmıştır. Kod üretirken veya mevcut dosyaları güncellerken bu belgedeki **mimari kuralları, fonksiyon imzalarını ve tasarım yasaklarını KESİNLİKLE korumalısın.**

---

## 1. Dosya ve Klasör Ağacı (Workspace Anatomy)

Proje tamamen statik, sunucusuz (serverless) bir yapıda çalışır ve kök dizinden (`/` veya `./`) doğrudan servis edilir:

```text
nereyeGidilir/
├── index.html                  # Ana SPA kabuğu (5 farklı görünüm: #view-explore, #view-map, #view-place, #view-blog, #view-about)
├── app.js                      # Tüm SPA mantığı: Router, D3.js, Leaflet.js, RAM Cache, Prefetch, Popülerlik Sıralaması, Lazy Render, Rota Planlayıcı, Geolocation, AdSense
├── style.css                   # Ana Vintage / Eski Seyahatname tasarım sistemi, D3/Leaflet stilleri, mobil responsive kuralları (.vintage-ad-slot dahil)
├── about-extra.css             # #view-about ("Hakkında") sayfası için özel Antik Parşömen Mektup / Seyahatname Önsözü stilleri
├── vercel.json                 # Vercel sunucu başlıkları (HTML, CSS, JS, JSON için ayrı MIME tipleriyle charset=utf-8 zorlaması)
├── project-context.md          # Bu Master Context devir teslim dokümanı
│
├── assets/
│   ├── flag_tr.svg             # Türk bayrağı vektörel ikonu
│   └── geo/
│       ├── tr_provinces_simplified.geojson   # D3.js ana haritası için 81 ilin basitleştirilmiş poligon sınırları (WGS84, name_tr & slug içerir)
│       ├── tr_districts_simplified.geojson   # Tüm Türkiye ilçeleri toplu GeoJSON yedeği
│       └── districts/
│           ├── adana.geojson                 # Her il için ayrı bölünmüş 81 adet ilçe sınırları GeoJSON dosyası
│           ├── ankara.geojson
│           ├── antalya.geojson
│           └── ... (toplam 81 dosya)
│
├── data/
│   └── places/
│       ├── index.json          # 81 ilin özet dizini: { "Antalya": { "slug": "antalya", "count": 233, "with_img": 233 }, ... }
│       ├── adana.json          # İl bazlı statik mekan verileri (Toplam 81 il dosyası + index.json, 7.868 doğrulanmış keşif noktası)
│       ├── antalya.json
│       ├── istanbul.json
│       └── ... (toplam 83 JSON dosyası)
│
└── scripts/                    # Veri üretim ve görsel doğrulama için çevrimdışı (offline) Python araçları (Canlı sitede çalışmaz)
    ├── build_places.py
    ├── build_images.py
    ├── clean_places_final.py
    └── enrich_from_wikidata_sparql.py
```

### Statik Mekan JSON Şeması (`data/places/{slug}.json`)
Her ilin JSON dosyası bir dizi (`Array<Place>`) içerir. Örnek kayıt:
```json
{
  "id": "way:131469472",
  "ad": "Aspendos",
  "il": "Antalya",
  "ilce": "Serik",
  "lat": 36.940567,
  "lon": 31.169708,
  "kategori": "Turistik Alan",
  "wiki": "tr:Aspendos",
  "wikidata": "Q633757",
  "wp": "tr:Aspendos",
  "img": "https://commons.wikimedia.org/wiki/Special:FilePath/Aspendos_Amphitheatre.jpg?width=700"
}
```
- **Önemli Kural:** `loadStaticCityData(cityName)` fonksiyonu yalnızca `p.img && p.img.trim() !== ''` koşulunu sağlayan (doğrulanmış gerçek fotoğrafı olan) mekanları filtreler ve eski Overpass yapısıyla uyum için `tags: { wikipedia: p.wiki, wikidata: p.wikidata, image: p.image }` alanını otomatik üretir.

---

## 2. Proje Mimarisi (Zero-Framework Vanilla JS SPA)

- **Zero-Framework:** Projede React, Vue, Angular, Tailwind, Bootstrap veya herhangi bir bundler (Webpack/Vite) **YOKTUR** ve **KESİNLİKLE EKLENMEMELİDİR**. Tüm kod saf HTML5, CSS3 ve Vanilla JavaScript (ES6+) ile yazılmıştır.
- **Sunucusuz (Serverless) Mimari:** Node.js/PHP backend veya SQL/MongoDB veritabanı yoktur. GitHub `main` dalına yapılan her push, Vercel tarafından doğrudan canlıya (`https://geziatlasi.com.tr`) alınır.
- **SPA Hash-Routing (`setupRouter` & `handleRoute`):**
  Sayfa yenilenmeden `window.location.hash` üzerinden 5 görünüm (`section.view-section`) yönetilir:
  1. `#explore` (`#view-explore`): Varsayılan ana görünüm. D3.js katlanmış Anadolu/İlçe haritası, sağ kontrol paneli, "Yakınımdakileri Bul" bölümü ve mekan kartları ızgarası (`#placesGrid`).
  2. `#map` (`#view-map`): Seçili ilin tam ekran Leaflet.js + MarkerCluster haritası (`#leafletMap`). İl seçilmeden `#map`'e gidilirse otomatik olarak `#explore`'a yönlendirir.
  3. `#place/{id}` (`#view-place`): Tekil mekan detay sayfası (Örn: `#place/way:131469472`). Fotoğraf, konum, kategori etiketleri, Wikipedia REST API (`https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}`) özeti, Google Maps yol tarifi ve "Rotama Ekle" butonunu barındırır.
  4. `#blog` (`#view-blog`): "Seyahatname" gezi yazıları ve rota rehberleri görünümü.
  5. `#about` (`#view-about`): "Hakkında" sayfası. Teknik terimlerden tamamen arındırılmış, "Gezi Atlası'na Hoş Geldiniz" başlıklı edebi bir **Seyahatname Önsözü / Antik Parşömen Mektup** görünümü (`81 İl`, `973 İlçe`, `7.868 Doğrulanmış Keşif Noktası` infografiği ile).
- **LocalStorage Tabanlı Özellikler:**
  1. **Seyahat Günlüğü / Akıllı Rota Planlayıcı (`ROUTE_STORAGE_KEY = "savedRoute"`):**
     - Kullanıcılar mekan kartlarındaki veya detay sayfasındaki `"📜 Rotama Ekle"` butonuyla mekanları `localStorage` üzerindeki `savedRoute` dizisine ekler/çıkarır (`toggleRoutePlace`, `getSavedRoute`, `saveRoute`).
     - Sağdan (mobilde alttan bottom-sheet olarak) açılan `#routeJournalPanel` çekmecesinde duraklar listelenir ve `"🧭 Rotayı Başlat (Google Maps)"` (`startGoogleMapsRoute`) butonu tüm durakların koordinatlarını `https://www.google.com/maps/dir/{lat1,lon1}/{lat2,lon2}/...` formatında birleştirerek çok duraklı Google Haritalar rotasını başlatır.
  2. **Fotoğraf Önbelleği (`PHOTO_CACHE_KEY = "nereye_photo_cache_v4_verified"`):**
     - Canlı Overpass/Wikidata yedek yolundan çözülen görseller 24 saat (`PHOTO_CACHE_TTL`) boyunca `localStorage`'da (maks. 500 kayıt) saklanır.
  3. **Tema Tercihi (`THEME_KEY = "nereye_vintage_theme_v5"`):**
     - Varsayılan tema `theme-light` (Vintage Parşömen / Eski Kâğıt), alternatif tema `theme-dark` (Antik Deri Ciltli Atlas & Fener Işığı).

---

## 3. Kullanılan Teknolojiler ve Harita Motorları

### A. D3.js v7 (`#d3MapContainer`)
- **Amacı:** `#view-explore` içindeki sol kutuda (`div.interactive-map-box`) önce 81 illi Türkiye haritasını (`drawD3Map`), bir il seçildiğinde ise o ilin ilçelerini ve mekan iğnelerini (`drawProvinceMap`) vektörel SVG olarak çizer.
- **Projeksiyon:** GeoJSON verisi RFC 7946 saat yönünün tersi (CCW) poligon halkalarına sahip olduğu için küresel sarma hatası yaşatmayan `d3.geoIdentity().reflectY(true).fitSize([width, height], geoData)` kullanılır.
- **Katman Yapısı:**
  - `<defs>`: `#vintageSeaGrad` radyal deniz gradyanı (`injectVintageMapDefs`). Ağır CPU yükü yaratan `feTurbulence` ve `feDropShadow` filtreleri **kaldırılmıştır**.
  - `g.vintage-sea-bg`: Deniz arka planı ve 16 yönlü denizcilik rüzgâr gülü / kerteriz çizgileri (`drawNauticalGridLines`).
  - `g.map-zoom-group.vintage-map-root`: Tüm yakınlaştırılabilir/kaydırılabilir harita elemanlarını barındıran ana grup:
    - `g.bathymetry-layer`: Kıyı kontur halkaları (`.coast-ring-outer`, `.coast-ring-inner`).
    - `g.land-layer`: İl (`path.country-path.province`) veya ilçe (`path.district-path.province`) poligonları. Her poligon `getVintageToneClass` ile deterministik olarak 4 farklı el boyaması sepia tonundan (`vintage-tone-0..3`) birini alır.
    - `text.district-label`: İl görünümünde ilçe isim etiketleri.
    - `g.wax-seal-layer`: Seçili ilçe üzerinde kırmızı mum mühür (`✕`) damgası.
    - `g.province-pins-layer`: İl görünümünde mekanların konumlarını gösteren `circle.province-place-pin` noktaları.

### B. Leaflet.js + Leaflet.MarkerCluster (`#leafletMap`)
- **Amacı:** `#view-map` görünümünde seçili ilin tüm mekanlarını gerçek dünya haritası üzerinde kümeleyerek (`MarkerCluster`) ve ilçe sınırlarıyla birlikte göstermek (`initOrUpdateLeafletMap`, `renderMapMarkers`).
- **Vintage Harita Dokusu (60 FPS GPU Dostu):**
  - `.leaflet-tile-pane` üzerinde eskiden bulunan ve her pan/zoom sırasında ağır repaint yükü oluşturan `filter: sepia(...)` **kaldırılmıştır**.
  - Bunun yerine `#leafletMap.leaflet-container::before` sözde (pseudo) elementi üzerinde `pointer-events: none; mix-blend-mode: multiply;` kullanan **sabit bir parşömen/sepia katmanı** vardır. Harita karoları kayarken tarayıcı yeniden filtre hesaplamaz.
- **Küme (Cluster) ve İğne Tasarımı:**
  - Küme ikonları `createVintageClusterIcon(cluster)` ile **Vintage Mum Mühür (`.vintage-cluster-seal`)** olarak üretilir.
  - Tekil mekanlar `createVintagePinIcon()` ile **Kırmızı Raptiye / Mühür (`.vintage-pin-seal`)** olarak çizilir.
  - **Hover Titreme (Layout Shift) Koruması:** `.marker-cluster`, `.vintage-cluster-icon` ve `.vintage-cluster-seal` sınıflarında `:hover` durumunda `width`, `height`, `margin`, `padding` veya `border-width` **ASLA değiştirilmez**; yalnızca `transform: scale(1.05); transform-origin: center center;` kullanılır ve iç elementlerde `pointer-events: none !important;` tanımlıdır.

### C. Yakınımdakileri Bul (Geolocation & Haversine)
- `findNearbyPlaces()` tarayıcının `navigator.geolocation.getCurrentPosition` API'sini kullanır.
- `getCandidatePlacesForLocation(userLat, userLon)` kullanıcının koordinatına en yakın 4 ili `d3.geoCentroid` ile bulur, bu illerin statik JSON verilerini `dataCache` üzerinden birleştirir ve `calculateHaversineKm` ile kuş uçuşu mesafeyi hesaplayıp en yakın 10 mekanı `#nearbySection` altında listeler.

---

## 4. Kritik Performans ve Mobil Çözümler (BUNLARI ASLA BOZMA!)

1. **RAM Önbellekleme (`dataCache` & `inFlightRequests`):**
   - `app.js` dosyasının en üstünde `const dataCache = new Map();` ve `const inFlightRequests = new Map();` tanımlıdır.
   - Tüm JSON/GeoJSON istekleri `fetchCachedJSON(url)` üzerinden geçer. Veri `dataCache` içinde varsa ağa çıkmadan anında `Promise.resolve(dataCache.get(url))` döner; aynı URL için devam eden bir istek varsa mükerrer `fetch` atılmaz.
2. **Arka Plan Ön Yükleme (`scheduleBackgroundPrefetch`):**
   - Sayfa ilk açılıp Türkiye haritası çizilir çizilmez `requestIdleCallback` (desteklemeyen tarayıcılarda `setTimeout`) devreye girer.
   - Önce `./data/places/index.json`, ardından en popüler 18 il (`İstanbul, Antalya, İzmir, Ankara, Muğla, Bursa, Nevşehir, Çanakkale, Trabzon, Gaziantep, Hatay, Mardin, Aydın, Balıkesir, Konya, Adana, Şanlıurfa, Kars`) ve sonrasında kalan tüm iller 3'erli paketler halinde sessizce RAM'e (`dataCache` ve `CITY_CACHE` / `DISTRICT_GEO_CACHE`) yüklenir.
3. **D3.js Mobil Ölçekleme (`fitSize` & `50vh`):**
   - `style.css` içinde `.d3-container` üzerinde kısıtlayıcı `aspect-ratio` yoktur; mobilde (`@media (max-width: 768px)`) `min-height: 50vh; height: 50vh; width: 100%;` ve `#d3MapContainer svg.vintage-d3-svg { width: 100%; height: 100%; display: block; }` tanımlıdır.
   - `drawD3Map` ve `drawProvinceMap` içinde projeksiyon `.fitSize([width, height], ...)` ile **sıfır boşluklu (tight bounding box)** olarak hesaplanır.
4. **D3.js Zoom (`map-zoom-group`) ve Mobil Touch (`bindD3TapAndClick`) Uyumu:**
   - Tüm harita katmanları `<g class="map-zoom-group vintage-map-root">` içindedir.
   - `d3.zoom().scaleExtent([1, 8])` doğrudan `svg.call(zoom).on("dblclick.zoom", null)` ile bağlanır ve `requestAnimationFrame` içinde `.map-zoom-group` elementinin `transform` özniteliğini günceller.
   - **Kritik Touch Kuralı:** `bindD3TapAndClick(selection, callback)` fonksiyonu `touchstart.tap` ve `touchend.tap` olaylarında **`event.stopPropagation()` ÇAĞIRMAZ**. Eğer `touchend` içinde `stopPropagation()` çağrılırsa üstteki `<svg>` üzerinde çalışan `d3.zoom()` parmağın kalktığını anlayamaz ve 2 parmakla pinch-to-zoom kilitlenir! Çoklu dokunuş (`event.touches.length > 1`) algılandığında ise `isMultiTouch = true` yapılarak pinch hareketi bitişinde yanlışlıkla il seçilmesi engellenir.
5. **Leaflet Performans Ayarları:**
   - `preferCanvas: true` ve `L.canvas({ padding: 0.5 })` aktiftir.
   - `L.markerClusterGroup` içinde `chunkedLoading: true`, `removeOutsideVisibleBounds: true`, `animate: false` aktiftir.
   - Markerlar tek tek `addLayer` ile değil, dizi halinde hazırlanıp `STATE.markerCluster.addLayers(markersBatch)` ile tek seferde basılır.
   - Popup HTML'leri başlangıçta oluşturulmaz; `marker.bindPopup(() => buildMarkerPopupHtml(place))` ile yalnızca tıklanınca (lazy) üretilir.
   - `#map` görünümüne geçildiğinde gri ekran oluşmaması için `showView('map')` içinde `200ms` ve `600ms` gecikmeli `STATE.leafletMap.invalidateSize()` çağrılır.
6. **`DocumentFragment` ve 24'lü Lazy Rendering (`IntersectionObserver`):**
   - `populateSelects`, `updateCategoryFilters`, `updateDistrictFilter` ve `renderNextPlacesBatch` içinde `innerHTML +=` **kesinlikle kullanılmaz**; her zaman `document.createDocumentFragment()` kullanılır.
   - Bir il seçildiğinde yüzlerce mekan aynı anda DOM'a basılmaz. `LAZY_RENDER_BATCH_SIZE = 24` ile ilk etapta yalnızca **en popüler ilk 24 mekan** `createPlaceCardElement(place)` ile oluşturulup `DocumentFragment` üzerinden tek seferde `#placesGrid`'e eklenir.
   - Listenin altına `#placesLoadMoreSentinel` (hem tıklanabilir `"📜 Daha Fazla Keşif Noktası Göster"` butonu hem de `rootMargin: "320px 0px"` değerine sahip `IntersectionObserver`) eklenir. Yeni eklenen kartların görselleri için `loadWikiImagesForCards(newImages)` yalnızca yeni partideki `<img>` elementlerini işler.
7. **Karakter Kodlaması (UTF-8 without BOM):**
   - Tüm `.html`, `.js`, `.css` ve `.json` dosyaları **UTF-8 (BOM'suz)** formatındadır. Windows PowerShell `Get-Content / Set-Content` komutları Türkçe karakterleri (`ş, ı, ğ, ü, ö, ç, İ, Ş`) bozup BOM eklediği için dosya düzenlemelerinde **asla** varsayılan PowerShell encoding'i kullanılmamalıdır.

---

## 5. Özel Mantıklar: Popülerliğe Göre Sıralama (`sortPlacesByPopularity`)

Kullanıcılar bir ili seçtiğinde mekanlar A-Z alfabetik sırayla **DEĞİL**, önem ve popülerlik sırasına göre dizilir:

1. **Sayısal Metrik Önceliği:** Veri içinde `rating / puan` veya `reviewCount / reviews` varsa önce `(b.rating || b.puan || 0) - (a.rating || a.puan || 0)` ve `(b.reviewCount || b.reviews || 0) - (a.reviewCount || a.reviews || 0)` karşılaştırılır.
2. **Yapay Popülerlik Puanı (`getPlacePopularityScore`):**
   - **Kategori Ağırlıkları (`CATEGORY_POPULARITY_WEIGHTS`):**
     - `Antik Kent`, `Tarihi / Antik Kent`, `Müze`, `Doğa Parkı`, `Milli Park`: **10 puan**
     - `Kale / Hisar`, `Şelale`, `Plaj / Koy`: **9 puan**
     - `Mağara`, `Kaplıca`: **8.5 puan**
     - `Tarihi Camii`, `Tarihi Kilise`, `Tarihi Kapı`, `Seyir Noktası`: **8 puan**
     - `Turistik Alan`, `Anıt`: **7 puan**
     - `Dağ Zirvesi`, `Göl / Nehir`: **6 puan**
     - `Park`, `Sanat Eseri`, `Eğlence Parkı`: **5 puan**
     - `Diğer`: **1 puan**
   - **Zengin İçerik Bonusları:**
     - Doğrulanmış fotoğrafı (`place.img`) varsa: **`+3.0` puan**
     - Türkçe Wikipedia maddesi (`tr:...`) varsa: **`+2.5` puan** (diğer dillerde Wikipedia maddesi varsa **`+1.2` puan**)
     - Wikidata Q-ID bilinirlik bonusu (`Q81593` gibi erken açılmış dünyaca ünlü miraslar `< Q500000` için **`+2.0` puan**, `< Q5000000` için **`+1.2` puan**).

---

## 6. Tasarım Dili ve UI/UX Felsefesi (Tasarım Yasakları)

- **Ana Konsept:** *"Vintage / Eski Seyahatname / Katlanmış Kâğıt Yol Haritası / Kaşif Defteri"*.
- **Kesin Yasaklar:**
  - Modern *Glassmorphism* (buzlu cam, neon/mavi/mor gradyanlar), düz (flat) kurumsal SaaS kartları veya modern sans-serif (Inter, Roboto vb.) arayüzler **KESİNLİKLE YASAKTIR**. (Not: Kodda tarihsel uyumluluk için `.glass-panel` sınıf adı korunmuştur ancak içeriği tamamen parşömen kâğıdı dokusuna dönüştürülmüştür).
- **Renk Paleti (`style.css` `:root`):**
  - `--bg-primary`: `#ecdcbb` (Eski Parşömen Zemin)
  - `--bg-secondary`: `#f9f1df` (Açık Seyahatname Yaprağı)
  - `--bg-paper-dark`: `#dfd0b0` (Koyu Kâğıt Tonu)
  - `--text-main`: `#3b2618` (Koyu Mürekkep Kahvesi)
  - `--brown-deep`: `#5C4033`, `--brown-warm`: `#8B5A2B`
  - `--forest-green`: `#295238` (Pusula / Rota Ekle Butonu Yeşili)
  - `--accent-color`: `#a83228` (Kiremit Kırmızısı / Mum Mühür)
- **Tipografi:**
  - Ana Başlıklar: `'Playfair Display', Georgia, serif`
  - Gövde Metinleri: `'Lora', Georgia, serif`
  - Damgalar, Rozetler, Daktilo Notları ve Butonlar: `'Special Elite', monospace`
  - El Yazısı Alt Başlıklar: `'Caveat', cursive`
- **Karakteristik Görsel Öğeler:**
  - Mekan kartları (`.place-card`) ve reklam kartları (`.vintage-ad-slot`), üst kenarında yarı saydam sararmış kaşif bandı (`::before` scotch tape efekti) bulunan **Polaroid / Yıpranmış Defter Yaprağı** görünümündedir.
  - Harita kutusunun (`.interactive-map-box`) üzerinde tıklamaları engellemeyen (`pointer-events: none`) `.map-fold-creases` kat izi çizgileri ve sağ alt köşede `🧭 KUZEY` filigranı yer alır.

---

## 7. Sıradaki Hedef: Google AdSense (Vintage SPA) Entegrasyonu

Projede halihazırda `app.js`, `style.css` ve `index.html` içinde Google AdSense için temel SPA altyapısı hazırlanmıştır ve sıradaki geliştirmelerde bu yapı üzerinden ilerlenecektir:

1. **Mevcut AdSense Mimarisi (`app.js` satır 116–224):**
   - `ADS_CONFIG`: `{ client: "ca-pub-0000000000000000", lazyDelayMs: 1600, enabled: true }`
   - `ensureAdSenseScriptLoaded()`: Gerçek yayıncı kimliği (`ca-pub-...`) girildiğinde `adsbygoogle.js` script'ini `<head>` içine yalnızca bir kez asenkron ekler.
   - `refreshAds(targetViewId)`: SPA görünümü değiştiğinde aktif bölümdeki `.vintage-ad-slot` kutularını tarar, eski `<ins class="adsbygoogle">` ve `<iframe>` kalıntılarını temizler, yeni `<ins>` oluşturup `(window.adsbygoogle = window.adsbygoogle || []).push({});` çağırır.
   - `scheduleRefreshAds(viewId)`: Harita çizimi ve sayfa geçiş animasyonunu engellememek için `1600ms` gecikmeyle ve `requestIdleCallback` içinde reklamları tetikler.
2. **Harita İzolasyonu (Kesin Kural):**
   - `.interactive-map-box`, `#d3MapContainer`, `#leafletMap` ve `#view-map` içine veya üzerine **asla reklam yerleştirilmez**. Hem `refreshAds()` içinde JS kontrolüyle hem de `style.css` içinde `display: none !important; pointer-events: none !important;` kurallarıyla harita kapsayıcıları reklamlardan izole edilmiştir.
3. **Vintage Reklam Konteynerleri (`.vintage-ad-slot`):**
   - **Yan Panel (`#adSlotExploreSidebar.vintage-ad-sidebar`):** `#view-explore` sağ kontrol kutusunun altında "Gezgin İlan Panosu" olarak yer alır.
   - **Mekan Kartları Arası (`createInFeedAdElement` — `.vintage-ad-card`):** `#placesGrid` içinde ilk 4 popüler mekan kartından hemen sonra 5. sıraya "🧭 SEYAHATNAME NOTU / İLAN" başlığıyla Polaroid kart olarak eklenir.
   - **Mekan Detay Altı (`#adSlotPlaceDetail.vintage-ad-banner`):** `#view-place` sayfasında mekan detay kartının altında yatay gazete küpürü olarak yer alır.
