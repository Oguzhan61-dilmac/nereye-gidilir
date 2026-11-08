// ==========================================
// Added theme initialization and SEO meta handling
// NEREYE GİDİLİR? - V2 SPA CONTROLLER
// Tüm yapı Vanilla JS ile "Tek Sayfa Uygulaması"nda (SPA) birleşti.
// ==========================================

// ================= GLOBAL IN-MEMORY DATA CACHE =================
const dataCache = new Map();
const inFlightRequests = new Map();

/**
 * JSON dosyalarını RAM önbelleği (dataCache) üzerinden getiren hızlı yükleyici.
 * Eğer veri dataCache içinde varsa ağa çıkmadan anında (Promise.resolve) döner,
 * yoksa fetch ile çekip dataCache.set(key, data) ile hafızaya kaydeder.
 */
async function fetchCachedJSON(url) {
  if (dataCache.has(url)) {
    return Promise.resolve(dataCache.get(url));
  }
  if (inFlightRequests.has(url)) {
    return inFlightRequests.get(url);
  }

  const reqPromise = fetch(url)
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status} (${url})`);
      return res.json();
    })
    .then((data) => {
      dataCache.set(url, data);
      inFlightRequests.delete(url);
      return data;
    })
    .catch((err) => {
      inFlightRequests.delete(url);
      throw err;
    });

  inFlightRequests.set(url, reqPromise);
  return reqPromise;
}

const STATE = {
  view: 'explore', // 'explore', 'map', 'place'
  geoData: null,   // D3 and BBox calculation from GeoJSON
  selectedCity: '',
  selectedDistrict: '',
  places: [],        // Overpass'tan gelen ham mekanlar
  filteredPlaces: [], // Filtreden geçmiş mekanlar (BUG #2 FIX)
  theme: 'light',
  leafletMap: null,
  markerCluster: null,
  endpoints: [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
  ]
};

const DOM = {
  loader: document.getElementById("loaderOverlay"),
  loaderMsg: document.getElementById("loaderMessage"),
  views: {
    explore: document.getElementById("view-explore"),
    map: document.getElementById("view-map"),
    place: document.getElementById("view-place"),
    about: document.getElementById("view-about"),
    blog: document.getElementById("view-blog")
  },
  themeBtn: document.getElementById("themeToggle"),
  d3Container: document.getElementById("d3MapContainer"),
  mapBoxTitle: document.getElementById("mapBoxTitle"),
  btnBackToTurkeyMap: document.getElementById("btnBackToTurkeyMap"),
  // Explore Elements
  citySelect: document.getElementById("provinceSelect"),
  districtSelect: document.getElementById("districtSelect"),
  globalCityLabel: document.getElementById("globalCityLabel"),
  globalStatsLabel: document.getElementById("globalStatsLabel"),
  btnGoToMap: document.getElementById("btnGoToMap"),
  searchInput: document.getElementById("searchInput"),
  categoryFilter: document.getElementById("categoryFilter"),
  placesGrid: document.getElementById("placesGrid"),
  // Map Elements
  btnBackFromMap: document.getElementById("btnBackFromMap"),
  mapTitle: document.getElementById("mapTitle"),
  mapCategoryFilter: document.getElementById("mapCategoryFilter"),
  // Detail Elements
  btnBackFromPlace: document.getElementById("btnBackFromPlace"),
  detailTitle: document.getElementById("detailTitle"),
  detailCategory: document.getElementById("detailCategory"),
  detailLocation: document.getElementById("detailLocation"),
  detailImageWrapper: document.getElementById("detailImageWrapper"),
  detailDescription: document.getElementById("detailDescription"),
  detailTags: document.getElementById("detailTags"),
  btnDirections: document.getElementById("btnDirections"),
  btnWikipedia: document.getElementById("btnWikipedia"),
  btnAddToRouteDetail: document.getElementById("btnAddToRouteDetail"),
  // Seyahat Günlüğü (Route Journal) Elements
  btnToggleJournal: document.getElementById("btnToggleJournal"),
  routeCountBadge: document.getElementById("routeCountBadge"),
  routeJournalPanel: document.getElementById("routeJournalPanel"),
  routeJournalBackdrop: document.getElementById("routeJournalBackdrop"),
  btnCloseJournal: document.getElementById("btnCloseJournal"),
  routeJournalList: document.getElementById("routeJournalList"),
  btnStartRoute: document.getElementById("btnStartRoute"),
  btnClearRoute: document.getElementById("btnClearRoute"),
  // Yakınımdakileri Bul (Geolocation & Haversine) Elements
  btnFindNearby: document.getElementById("btnFindNearby"),
  nearbySection: document.getElementById("nearbySection"),
  nearbyGrid: document.getElementById("nearbyGrid"),
  nearbySubtitle: document.getElementById("nearbySubtitle"),
  btnCloseNearby: document.getElementById("btnCloseNearby"),
  // Yöre Sofrası (restoranlar)
  foodSection: document.getElementById("foodSection"),
  foodTitle: document.getElementById("foodTitle"),
  foodSubtitle: document.getElementById("foodSubtitle"),
  foodList: document.getElementById("foodList"),
  btnShowFood: document.getElementById("btnShowFood")
};


// ================= SPA REKLAM (ADSENSE) MİMARİSİ & LAZY LOADER =================
const ADS_CONFIG = {
  // Kendi Google AdSense yayıncı kimliğinizi buraya girin (örn. "ca-pub-1234567890123456")
  client: "ca-pub-0000000000000000",
  // Harita (D3.js / Leaflet) çizimini ve pan/zoom performansını engellememek için gecikme süresi (ms)
  lazyDelayMs: 1600,
  // AdSense'in "In-Feed" reklam birimi için verdiği data-ad-layout-key (yoksa otomatik formata düşer)
  inFeedLayoutKey: "",
  // AdSense panelinden alınacak reklam birimi (slot) kimlikleri
  slots: { sidebar: "", inFeed: "", banner: "" },
  // Gerçek yayıncı kimliği girilene kadar reklam yuvaları gizli kalır (bkz. adsAreLive)
  enabled: true
};

let _adScriptLoaded = false;
let _adRefreshTimer = null;

// Gerçek yayıncı kimliği girilene kadar reklam yuvaları (ve "SPONSORLU" yer tutucuları) hiç gösterilmez.
// AdSense incelemesinde sahte "sponsorlu" içerik görünmemesi için önemlidir.
function adsAreLive() {
  return Boolean(
    ADS_CONFIG.enabled &&
    ADS_CONFIG.client &&
    ADS_CONFIG.client !== "ca-pub-0000000000000000"
  );
}

function ensureAdSenseScriptLoaded() {
  if (_adScriptLoaded || !adsAreLive()) return;
  _adScriptLoaded = true;
  if (document.querySelector('script[data-vintage-adsense="true"]')) return;

  const script = document.createElement("script");
  script.async = true;
  script.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(ADS_CONFIG.client)}`;
  script.crossOrigin = "anonymous";
  script.setAttribute("data-vintage-adsense", "true");
  document.head.appendChild(script);
}

function isInsideMap(el) {
  return Boolean(
    el.closest(".interactive-map-box") ||
    el.closest("#d3MapContainer") ||
    el.closest("#leafletMap") ||
    el.closest("#view-map")
  );
}

/**
 * Tek bir .vintage-ad-slot yuvasını temiz bir <ins class="adsbygoogle"> ile doldurur ve push({}) çağırır.
 * Eski ins/iframe kalıntıları silinir (SPA'da "already have ads" hatasını önler).
 */
function fillAdSlot(slotEl) {
  if (!adsAreLive() || !slotEl || isInsideMap(slotEl)) return;
  ensureAdSenseScriptLoaded();

  const bodyEl = slotEl.querySelector(".vintage-ad-body") || slotEl;
  const slotKey = slotEl.getAttribute("data-ad-slot-key") || "";
  const adSlotId = (slotKey && ADS_CONFIG.slots[slotKey]) || slotEl.getAttribute("data-ad-slot") || "";
  let adFormat = slotEl.getAttribute("data-ad-format") || "auto";
  const layoutKey = slotEl.getAttribute("data-ad-layout-key") || "";
  // "fluid" (In-Feed) formatı AdSense'in verdiği layout-key olmadan çalışmaz → otomatik formata düş
  if (adFormat === "fluid" && !layoutKey) adFormat = "auto";

  bodyEl.querySelectorAll("ins.adsbygoogle, iframe").forEach((node) => node.remove());

  const ins = document.createElement("ins");
  ins.className = "adsbygoogle";
  ins.style.display = "block";
  ins.setAttribute("data-ad-client", ADS_CONFIG.client);
  if (adSlotId) ins.setAttribute("data-ad-slot", adSlotId);
  ins.setAttribute("data-ad-format", adFormat);
  if (layoutKey) ins.setAttribute("data-ad-layout-key", layoutKey);
  if (adFormat !== "fluid") ins.setAttribute("data-full-width-responsive", "true");
  bodyEl.appendChild(ins);

  try {
    (window.adsbygoogle = window.adsbygoogle || []).push({});
    slotEl.classList.add("ad-requested");
  } catch (err) {
    console.warn("AdSense yenileme uyarısı:", err);
  }
}

/**
 * SPA görünümü (route) değiştiğinde o görünümdeki reklam yuvalarını yeniler.
 * Filtre / arama / kaydırma gibi küçük etkileşimlerde ÇAĞRILMAZ (AdSense yenileme politikası).
 */
function refreshAds(targetViewId = STATE.view) {
  if (!adsAreLive() || targetViewId === "map") return;
  const activeSection = DOM.views[targetViewId] || document;
  activeSection.querySelectorAll(".vintage-ad-slot").forEach(fillAdSlot);
}

/**
 * Harita çizimi ve sayfa geçiş animasyonu tamamlandıktan sonra
 * tarayıcı boşta iken (requestIdleCallback) reklamları asenkron tetikler.
 */
function scheduleRefreshAds(viewId = STATE.view) {
  if (_adRefreshTimer) {
    clearTimeout(_adRefreshTimer);
    _adRefreshTimer = null;
  }
  if (viewId === "map" || !adsAreLive()) return;

  _adRefreshTimer = setTimeout(() => {
    _adRefreshTimer = null;
    if (typeof window.requestIdleCallback === "function") {
      window.requestIdleCallback(() => refreshAds(viewId), { timeout: 1000 });
    } else {
      requestAnimationFrame(() => refreshAds(viewId));
    }
  }, ADS_CONFIG.lazyDelayMs);
}

// ================= GÜVENLİK & LİNK YARDIMCILARI =================
const _HTML_ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
function escapeHtml(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, (c) => _HTML_ESC[c]);
}

// Mekan kimlikleri (wd:Q123, node:456 ...) inline onclick içinde kullanılmadan önce doğrulanır
function safeId(value) {
  const v = String(value == null ? "" : value);
  return /^[A-Za-z0-9:._-]+$/.test(v) ? v : "";
}

// Yalnızca http(s) görsel adreslerine izin ver (javascript: vb. engellenir)
function safeUrl(value) {
  const v = String(value == null ? "" : value).trim();
  return /^https:\/\//i.test(v) ? escapeHtml(v) : "";
}

/**
 * Mekan detay linki: #place/{il-slug}/{id}
 * İl slug'ı sayesinde doğrudan açılan linklerde mekan, statik JSON'dan anında bulunur.
 */
function getPlaceHash(place) {
  if (!place) return "#explore";
  const slug = getCitySlug(place.il || STATE.selectedCity || "");
  const id = safeId(place.id);
  return slug ? `#place/${slug}/${id}` : `#place/${id}`;
}

// Wikimedia "Special:FilePath" görsellerini kart boyutunda iste (daha az bayt, daha hızlı liste)
function sizedImageUrl(url, width) {
  if (!url) return url;
  if (/Special:FilePath\//.test(url)) {
    return /[?&]width=\d+/.test(url)
      ? url.replace(/([?&]width=)\d+/, `$1${width}`)
      : `${url}${url.includes("?") ? "&" : "?"}width=${width}`;
  }
  return url;
}

// ================= YÖRE SOFRASI: GOOGLE YORUMLU RESTORANLAR =================
// Google Maps Platform şartları gereği puan/yorum verisi JSON'a KAYDEDİLMEZ; kullanıcı
// "Restoranları Göster" düğmesine bastığında canlı çekilir (ilk ekranda hiç istek atılmaz).
// Anahtar: Google Cloud → "Maps JavaScript API" + "Places API (New)" etkin, HTTP referrer
// kısıtlaması: https://geziatlasi.com.tr/*  (anahtar boşsa bölüm hiç görünmez)
const GOOGLE_PLACES_CONFIG = {
  apiKey: "",
  minRating: 4.0,      // bu puanın altındaki yerler listelenmez
  minReviews: 20,      // çok az yorumlu (güvenilmez) yerleri ele
  maxShown: 10
};

const _foodCache = new Map(); // yalnızca bu sayfa oturumu boyunca (bellekte) tutulur
let _gmLoadPromise = null;
let _foodAreaKey = "";
let _foodRequestToken = 0;

function foodFeatureEnabled() {
  return true; // Anahtar yoksa OpenStreetMap modu çalışır (kurulum gerektirmez)
}

function googleModeEnabled() {
  return Boolean(GOOGLE_PLACES_CONFIG.apiKey);
}

// Google Haritalar arama linki (Maps URLs — anahtar/ücret gerektirmez, resmi yöntem)
function googleMapsSearchUrl(query) {
  return "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(query);
}

function loadGoogleMapsApi() {
  if (window.google && window.google.maps && typeof window.google.maps.importLibrary === "function") {
    return Promise.resolve();
  }
  if (_gmLoadPromise) return _gmLoadPromise;
  _gmLoadPromise = new Promise((resolve, reject) => {
    const cbName = "__geziAtlasiGmReady";
    window[cbName] = () => resolve();
    window.gm_authFailure = () => reject(new Error("auth"));
    const script = document.createElement("script");
    script.src = "https://maps.googleapis.com/maps/api/js?key=" + encodeURIComponent(GOOGLE_PLACES_CONFIG.apiKey)
      + "&v=weekly&loading=async&language=tr&region=TR&callback=" + cbName;
    script.async = true;
    script.onerror = () => { _gmLoadPromise = null; reject(new Error("load")); };
    document.head.appendChild(script);
  });
  return _gmLoadPromise;
}

// Seçili ilçenin (yoksa ilin) sınır kutusu → arama yalnızca bu alanla sınırlanır
function getFoodAreaBounds() {
  let feature = null;
  if (STATE.selectedDistrict) {
    const dg = DISTRICT_GEO_CACHE[STATE.selectedCity];
    feature = dg && dg.features.find(f => f.properties && f.properties.name_tr === STATE.selectedDistrict);
  }
  if (!feature && STATE.geoData) {
    feature = STATE.geoData.features.find(f => f.properties.name_tr === STATE.selectedCity);
  }
  if (!feature) return null;
  const [[west, south], [east, north]] = d3.geoBounds(feature);
  return { west, south, east, north };
}

function updateFoodSection() {
  if (!DOM.foodSection) return;
  if (!foodFeatureEnabled() || !STATE.selectedCity) {
    DOM.foodSection.classList.add("hidden");
    _foodAreaKey = "";
    return;
  }
  DOM.foodSection.classList.remove("hidden");
  const area = STATE.selectedDistrict ? `${STATE.selectedDistrict}, ${STATE.selectedCity}` : STATE.selectedCity;
  const key = `${STATE.selectedCity}|${STATE.selectedDistrict || ""}`;
  if (key === _foodAreaKey) return;
  _foodAreaKey = key;
  _foodRequestToken++;
  DOM.foodTitle.textContent = `${area}: Nerede Yenir?`;
  DOM.foodSubtitle.textContent = googleModeEnabled()
    ? `Google yorumlarında yüksek puan almış, ${area} bölgesinde en çok tercih edilen lokantalar.`
    : `${area} bölgesindeki lokantalar; her birinin Google puanını ve yorumlarını tek tıkla açabilirsiniz.`;
  DOM.foodList.hidden = true;
  DOM.foodList.replaceChildren();
  DOM.btnShowFood.textContent = "🍲 Restoranları Göster";
  DOM.btnShowFood.setAttribute("aria-expanded", "false");
}

const PRICE_LABELS = { FREE: "Ücretsiz", INEXPENSIVE: "₺", MODERATE: "₺₺", EXPENSIVE: "₺₺₺", VERY_EXPENSIVE: "₺₺₺₺" };

function renderFoodStatus(text) {
  const div = document.createElement("div");
  div.className = "food-status";
  div.textContent = text;
  DOM.foodList.replaceChildren(div);
}

function renderFoodResults(items, area) {
  if (!items.length) {
    renderFoodStatus(`${area} için yeterince yorum almış, ${GOOGLE_PLACES_CONFIG.minRating.toFixed(1)}+ puanlı restoran bulunamadı.`);
    return;
  }
  const ol = document.createElement("ol");
  ol.className = "food-items";
  items.forEach((r, i) => {
    const li = document.createElement("li");
    li.className = "food-item";
    const price = PRICE_LABELS[String(r.priceLevel || "").toUpperCase()] || "";
    li.innerHTML = `
      <span class="food-rank">${i + 1}</span>
      <div class="food-info">
        <div class="food-name">${escapeHtml(r.name)}</div>
        <div class="food-meta">
          <span class="food-stars">★ ${escapeHtml(r.rating.toFixed(1))}</span>
          · ${escapeHtml(r.count.toLocaleString("tr-TR"))} yorum${r.type ? ` · ${escapeHtml(r.type)}` : ""}${price ? ` · ${escapeHtml(price)}` : ""}
        </div>
        ${r.address ? `<div class="food-address" title="${escapeHtml(r.address)}">📍 ${escapeHtml(r.address)}</div>` : ""}
        ${safeUrl(r.url) ? `<a class="food-link" href="${safeUrl(r.url)}" target="_blank" rel="noopener">Google Haritalar'da yorumları oku →</a>` : ""}
      </div>`;
    ol.appendChild(li);
  });
  const attr = document.createElement("p");
  attr.className = "food-attribution";
  attr.innerHTML = `Puanlar ve yorum sayıları: <span class="gm-text">Google Maps</span>`;
  DOM.foodList.replaceChildren(ol, attr);
}

// ---------- OpenStreetMap modu (anahtarsız) ----------
const CUISINE_TR = {
  regional: "Yöresel", local: "Yöresel", turkish: "Türk mutfağı", kebab: "Kebap", pide: "Pide",
  lahmacun: "Lahmacun", fish: "Balık", seafood: "Deniz ürünleri", meat: "Et", steak_house: "Et",
  grill: "Izgara", barbecue: "Mangal", kofte: "Köfte", "köfte": "Köfte", soup: "Çorba",
  breakfast: "Kahvaltı", homestyle: "Ev yemekleri", home_cooking: "Ev yemekleri",
  pizza: "Pizza", burger: "Burger", italian: "İtalyan", chinese: "Çin", international: "Dünya mutfağı",
  vegetarian: "Vejetaryen", vegan: "Vegan", dessert: "Tatlı", coffee_shop: "Kahve", tea: "Çay bahçesi",
  cafe: "Kafe", sandwich: "Sandviç", chicken: "Tavuk", doner: "Döner", "döner": "Döner", ottoman: "Osmanlı mutfağı",
  mediterranean: "Akdeniz", middle_eastern: "Orta Doğu", sushi: "Suşi", asian: "Asya"
};

function renderOsmFoodResults(items, area, total) {
  const wrap = document.createElement("div");

  const top = document.createElement("a");
  top.className = "food-google-cta";
  top.href = googleMapsSearchUrl(`${area} en iyi restoranlar`);
  top.target = "_blank";
  top.rel = "noopener";
  top.textContent = `⭐ ${area} için en yüksek puanlı restoranları Google Haritalar'da aç →`;
  wrap.appendChild(top);

  if (!items.length) {
    const div = document.createElement("div");
    div.className = "food-status";
    div.textContent = `${area} için haritada kayıtlı restoran bulunamadı. Yukarıdaki bağlantıdan Google'daki listeye bakabilirsiniz.`;
    wrap.appendChild(div);
    DOM.foodList.replaceChildren(wrap);
    return;
  }

  const ol = document.createElement("ol");
  ol.className = "food-items";
  items.forEach((r, i) => {
    const t = r.tags;
    const cuisines = String(t.cuisine || "").toLowerCase().split(/[;,]/).map(c => c.trim()).filter(Boolean)
      .map(c => CUISINE_TR[c] || "").filter(Boolean);
    const uniqueCuisines = [...new Set(cuisines)].slice(0, 2).join(", ");
    const street = [t["addr:street"], t["addr:housenumber"]].filter(Boolean).join(" ");
    const district = r.ilce || STATE.selectedDistrict || "";
    const searchQ = `${t.name} ${district} ${STATE.selectedCity}`.replace(/\s+/g, " ").trim();
    const phone = t.phone || t["contact:phone"] || "";
    const li = document.createElement("li");
    li.className = "food-item";
    li.innerHTML = `
      <span class="food-rank">${i + 1}</span>
      <div class="food-info">
        <div class="food-name">${escapeHtml(t.name)}</div>
        <div class="food-meta">${escapeHtml(uniqueCuisines || "Restoran")}${district ? ` · ${escapeHtml(district)}` : ""}</div>
        ${street ? `<div class="food-address" title="${escapeHtml(street)}">📍 ${escapeHtml(street)}</div>` : ""}
        <a class="food-link" href="${escapeHtml(googleMapsSearchUrl(searchQ))}" target="_blank" rel="noopener">⭐ Google puanı ve yorumları →</a>
        ${phone ? `<a class="food-link food-phone" href="tel:${escapeHtml(phone.replace(/[^+\d]/g, ""))}">📞 Ara</a>` : ""}
      </div>`;
    ol.appendChild(li);
  });
  wrap.appendChild(ol);

  const attr = document.createElement("p");
  attr.className = "food-attribution";
  attr.innerHTML = `Liste: <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> katkıcıları (${escapeHtml(String(total))} kayıtlı restoran içinden öne çıkanlar). Puanlar Google Haritalar'da açılır.`;
  wrap.appendChild(attr);
  DOM.foodList.replaceChildren(wrap);
}

// Restoranlar derleme anında OSM'den çıkarılmış statik dosyadan gelir (data/food/{il}.json,
// scripts/build_osm_extras.py). Canlı Overpass sunucuları sık sık aşırı yüklü olduğu için kullanılmaz.
async function loadFoodListOsm(area, cacheKey, token) {
  try {
    const slug = getCitySlug(STATE.selectedCity);
    let data = null;
    try {
      data = await fetchCachedJSON(`./data/food/${slug}.json`);
    } catch (e) {
      data = { counts: {}, items: [] };
    }
    if (token !== _foodRequestToken) return;

    const district = STATE.selectedDistrict || "";
    const items = (data.items || [])
      .filter(r => !district || r.i === district)
      .slice(0, 15)
      .map(r => ({
        lat: r.lat, lon: r.lon, ilce: r.i,
        tags: { name: r.n, cuisine: r.c || "", "addr:street": r.s || "", phone: r.p || "" }
      }));
    const counts = data.counts || {};
    const total = district ? (counts[district] || 0) : Object.values(counts).reduce((a, b) => a + b, 0);

    const payload = { mode: "osm", items, total };
    _foodCache.set(cacheKey, payload);
    renderOsmFoodResults(items, area, total);
  } catch (err) {
    if (token !== _foodRequestToken) return;
    console.warn("Restoran listesi alınamadı:", err);
    renderOsmFoodResults([], area, 0);
  }
}

async function loadFoodList() {
  const city = STATE.selectedCity;
  if (!city || !foodFeatureEnabled()) return;
  const district = STATE.selectedDistrict || "";
  const area = district ? `${district}, ${city}` : city;
  const cacheKey = `${city}|${district}`;
  const token = ++_foodRequestToken;

  DOM.foodList.hidden = false;
  DOM.btnShowFood.textContent = "▲ Listeyi Gizle";
  DOM.btnShowFood.setAttribute("aria-expanded", "true");

  if (_foodCache.has(cacheKey)) {
    const cached = _foodCache.get(cacheKey);
    if (cached && cached.mode === "osm") renderOsmFoodResults(cached.items, area, cached.total);
    else renderFoodResults(cached, area);
    return;
  }
  renderFoodStatus("🧭 Yöre sofrası defteri açılıyor...");

  if (!googleModeEnabled()) {
    await loadFoodListOsm(area, cacheKey, token);
    return;
  }

  try {
    await loadGoogleMapsApi();
    const { Place } = await google.maps.importLibrary("places");
    const request = {
      textQuery: `${area} restoran`,
      fields: ["displayName", "rating", "userRatingCount", "formattedAddress", "googleMapsURI", "priceLevel", "primaryTypeDisplayName"],
      includedType: "restaurant",
      maxResultCount: 20,
      minRating: GOOGLE_PLACES_CONFIG.minRating,
      language: "tr",
      region: "tr"
    };
    const bounds = getFoodAreaBounds();
    if (bounds) request.locationRestriction = bounds;

    const { places } = await Place.searchByText(request);
    if (token !== _foodRequestToken) return;

    // Bayes ortalaması: 4,9 puan/12 yorum, 4,6 puan/2.000 yorumun önüne geçmesin
    const C = 4.2, M = 150;
    const items = (places || [])
      .map(p => ({
        name: p.displayName || "",
        rating: Number(p.rating) || 0,
        count: Number(p.userRatingCount) || 0,
        address: p.formattedAddress || "",
        url: p.googleMapsURI || "",
        priceLevel: p.priceLevel || "",
        type: p.primaryTypeDisplayName || ""
      }))
      .filter(r => r.name && r.rating >= GOOGLE_PLACES_CONFIG.minRating && r.count >= GOOGLE_PLACES_CONFIG.minReviews)
      .map(r => ({ ...r, score: (r.count / (r.count + M)) * r.rating + (M / (r.count + M)) * C }))
      .sort((a, b) => b.score - a.score)
      .slice(0, GOOGLE_PLACES_CONFIG.maxShown);

    _foodCache.set(cacheKey, items);
    renderFoodResults(items, area);
  } catch (err) {
    if (token !== _foodRequestToken) return;
    console.warn("Restoran listesi alınamadı:", err);
    renderFoodStatus("Restoran listesi şu an alınamadı. Lütfen biraz sonra tekrar deneyin.");
  }
}

function toggleFoodList() {
  if (!DOM.foodList) return;
  if (!DOM.foodList.hidden) {
    DOM.foodList.hidden = true;
    DOM.btnShowFood.textContent = "🍲 Restoranları Göster";
    DOM.btnShowFood.setAttribute("aria-expanded", "false");
    return;
  }
  loadFoodList();
}

// ================= CORE ROUTER =================
function setupRouter() {
  window.addEventListener('hashchange', handleRoute);
}

function handleRoute() {
  const hash = window.location.hash || '#explore';
  
  // Hash Parser: #place/{il-slug}/{id}  (eski format #place/{id} de desteklenir)
  if (hash.startsWith('#place/')) {
    const rest = decodeURIComponent(hash.slice('#place/'.length));
    const slashIdx = rest.indexOf('/');
    const slug = slashIdx > -1 ? rest.slice(0, slashIdx) : '';
    const id = slashIdx > -1 ? rest.slice(slashIdx + 1) : rest;
    showView('place');
    renderPlaceDetails(id, slug);
    return;
  }

  if (hash === '#map') {
    if (!STATE.selectedCity) {
      window.location.hash = '#explore';
      return;
    }
    showView('map');
    initOrUpdateLeafletMap();
    return;
  }

  if (hash === '#about') { showView('about'); return; }
  if (hash === '#blog')  { showView('blog');  return; }

  // Default
  showView('explore');
}

const DEFAULT_DOC_TITLE = document.title;

function showView(viewId) {
  STATE.view = viewId;
  if (viewId !== 'place') document.title = DEFAULT_DOC_TITLE;
  window.scrollTo(0, 0);
  Object.values(DOM.views).forEach(el => el.classList.remove('active'));
  if (DOM.views[viewId]) DOM.views[viewId].classList.add('active');

  // Nav aktif güncelle
  document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
  const activeLink = document.querySelector(`.nav-link[data-target="${viewId}"]`);
  if (activeLink) activeLink.classList.add('active');

  if (viewId === 'map') {
    // display:none -> block geçişinden sonra Leaflet boyutunu yeniden hesaplasın (gri ekran fix)
    setTimeout(() => { if (STATE.leafletMap) STATE.leafletMap.invalidateSize(); }, 200);
    setTimeout(() => { if (STATE.leafletMap) STATE.leafletMap.invalidateSize(); }, 600);
  } else {
    // Harita dışı görünümlerde 1.6 sn gecikmeli (lazy) reklam yenilemesini planla
    scheduleRefreshAds(viewId);
  }
}

// ================= LOADER UTILS =================
function showLoader(msg = "Yükleniyor...") {
  if (DOM.loaderMsg) DOM.loaderMsg.textContent = msg;
  if (DOM.loader) {
    DOM.loader.classList.remove("hidden");
    DOM.loader.style.display = "flex";
  }
}

function hideLoader() {
  if (DOM.loader) {
    DOM.loader.classList.add("hidden");
    DOM.loader.style.display = "none";
  }
}

// Harita kapsayıcısı içinde küçük "Vintage Pusula / Yükleniyor..." animasyonu
function showMapCompass(container, msg = "Harita çiziliyor...") {
  if (!container) return;
  let el = container.querySelector(".map-compass-loader");
  if (!el) {
    el = document.createElement("div");
    el.className = "map-compass-loader";
    el.setAttribute("role", "status");
    container.appendChild(el);
  }
  el.classList.remove("hidden");
  el.style.display = "flex";
  el.innerHTML = `<span class="map-compass-needle" aria-hidden="true">🧭</span><span class="map-compass-text">${msg}</span>`;
}

function hideMapCompass(container) {
  const scope = container || document;
  const loaders = scope.querySelectorAll(".map-compass-loader");
  loaders.forEach((el) => {
    el.classList.add("hidden");
    el.style.display = "none";
    el.remove();
  });
}

// ================= MOBİL DOKUNMATİK (TOUCH + CLICK) YARDIMCISI =================
let _lastTouchActionTime = 0;

/**
 * D3 elementlerine hem masaüstü "click" hem de mobil "touchstart.tap/touchend.tap"
 * olayı bağlar.
 * - stopPropagation() touch olaylarında çağrılmaz; böylece üstteki <svg> üzerindeki
 *   d3.zoom() 2 parmakla pinch-to-zoom ve pan hareketlerini kesintisiz takip eder.
 * - Çoklu dokunuş (2 parmak pinch) algılandığında il/ilçe seçimi tetiklenmez.
 */
function bindD3TapAndClick(selection, callback) {
  let touchStartX = 0;
  let touchStartY = 0;
  let touchStartTime = 0;
  let isMultiTouch = false;

  selection
    .on("touchstart.tap", function(event) {
      if (!event.touches) return;
      if (event.touches.length > 1) {
        isMultiTouch = true;
        return;
      }
      isMultiTouch = false;
      touchStartX = event.touches[0].clientX;
      touchStartY = event.touches[0].clientY;
      touchStartTime = Date.now();
    }, { passive: true })
    .on("touchend.tap", function(event, d) {
      if (isMultiTouch) {
        if (!event.touches || event.touches.length === 0) isMultiTouch = false;
        return;
      }
      if (!event.changedTouches || event.changedTouches.length !== 1) return;
      const dx = Math.abs(event.changedTouches[0].clientX - touchStartX);
      const dy = Math.abs(event.changedTouches[0].clientY - touchStartY);
      const dt = Date.now() - touchStartTime;
      // Parmak sürüklenmediyse (gerçek tek parmak dokunuş/tap ise) seçimi tetikle
      if (dx < 12 && dy < 12 && dt < 550) {
        _lastTouchActionTime = Date.now();
        callback.call(this, event, d);
      }
    })
    .on("click", function(event, d) {
      // touchend.tap az önce tetiklendiyse çift çalışmayı önle
      if (Date.now() - _lastTouchActionTime < 450) return;
      event.stopPropagation();
      callback.call(this, event, d);
    });
}

// ================= PERFORMANCE UTILS (DEBOUNCE / THROTTLE / RAF) =================
function debounce(fn, delay = 180) {
  let timer = null;
  return function(...args) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      fn.apply(this, args);
    }, delay);
  };
}

function throttle(fn, limit = 80) {
  let inThrottle = false;
  let lastArgs = null;
  return function(...args) {
    if (!inThrottle) {
      fn.apply(this, args);
      inThrottle = true;
      setTimeout(() => {
        inThrottle = false;
        if (lastArgs) {
          const pending = lastArgs;
          lastArgs = null;
          fn.apply(this, pending);
        }
      }, limit);
    } else {
      lastArgs = args;
    }
  };
}

// D3 harita katmanlarını, event listener'ları ve bekleyen rAF çağrılarını bellek sızıntısı olmadan temizler
let _d3ZoomRafId = null;
let _d3TooltipRafId = null;
let _d3DrawRafId = null;

function cleanupD3Map() {
  if (_d3ZoomRafId) {
    cancelAnimationFrame(_d3ZoomRafId);
    _d3ZoomRafId = null;
  }
  if (_d3TooltipRafId) {
    cancelAnimationFrame(_d3TooltipRafId);
    _d3TooltipRafId = null;
  }
  if (_d3DrawRafId) {
    cancelAnimationFrame(_d3DrawRafId);
    _d3DrawRafId = null;
  }
  const containerSel = d3.select("#d3MapContainer");
  containerSel.selectAll("svg").on(".zoom", null).on("click", null);
  containerSel.selectAll("path, circle").on("mouseenter mousemove mouseleave click touchstart touchend", null);
  containerSel.selectAll("svg, .d3-map-tooltip").remove();
}

// ================= D3 MAP INITIALIZATION =================
function initD3Map() {
  showMapCompass(DOM.d3Container, "Anadolu haritası açılıyor...");
  return fetchCachedJSON("./assets/geo/tr_provinces_simplified.geojson")
    .then(data => {
      STATE.geoData = data;
      populateSelects();
      // Container henüz 0x0 olabilir; gerçek boyut hazır olduğunda çiz
      waitForContainerAndDraw();
      // Harita çizilir çizilmez arka planda popüler illeri ve index.json'u sessizce önbelleğe al
      scheduleBackgroundPrefetch();
    })
    .catch(err => {
      console.error("Harita verisi yüklenemedi:", err);
      hideMapCompass(DOM.d3Container);
      DOM.d3Container.innerHTML = "<p style='color:var(--accent-color); padding:2rem;'>Harita yüklenemedi. Lütfen bağlantınızı kontrol edip sayfayı yenileyin.</p>";
    });
}

// BUG FIX: Container boyutu CSS layout tamamlanmadan 0 olabilir
function waitForContainerAndDraw() {
  requestAnimationFrame(() => {
    drawD3Map();
  });
}

// Vintage Harita Yardımcıları: Hafifletilmiş SVG <defs> (CPU yoran feTurbulence ve hareketli feDropShadow kaldırıldı)
function injectVintageMapDefs(svg) {
  const defs = svg.append("defs");

  // Antik Deniz / Zemin Radyal Gradyanı (GPU dostu vektör gradyan)
  const seaGrad = defs.append("radialGradient")
    .attr("id", "vintageSeaGrad")
    .attr("cx", "50%")
    .attr("cy", "50%")
    .attr("r", "70%");
  seaGrad.append("stop").attr("offset", "0%").attr("stop-color", "#efe3c8").attr("stop-opacity", "0.55");
  seaGrad.append("stop").attr("offset", "65%").attr("stop-color", "#decba6").attr("stop-opacity", "0.75");
  seaGrad.append("stop").attr("offset", "100%").attr("stop-color", "#c7ae83").attr("stop-opacity", "0.92");
}

// Eski Denizcilik Haritası Rüzgâr Gülü / Pusula Çizgileri (Rhumb Lines)
function drawNauticalGridLines(layer, width, height) {
  const cx = width * 0.14;
  const cy = height * 0.82;
  const angles = Array.from({ length: 16 }, (_, i) => (i * Math.PI) / 8);
  angles.forEach(angle => {
    const x2 = cx + Math.cos(angle) * Math.max(width, height) * 1.4;
    const y2 = cy + Math.sin(angle) * Math.max(width, height) * 1.4;
    layer.append("line")
      .attr("x1", cx)
      .attr("y1", cy)
      .attr("x2", x2)
      .attr("y2", y2)
      .attr("class", "nautical-rhumb-line");
  });

  // Enlem-boylam seyir ızgarası
  for (let x = width * 0.2; x < width; x += width * 0.2) {
    layer.append("line")
      .attr("x1", x).attr("y1", 0).attr("x2", x).attr("y2", height)
      .attr("class", "nautical-grid-line");
  }
  for (let y = height * 0.25; y < height; y += height * 0.25) {
    layer.append("line")
      .attr("x1", 0).attr("y1", y).attr("x2", width).attr("y2", y)
      .attr("class", "nautical-grid-line");
  }
}

// İl ismine göre deterministik 4 tonlu el boyaması sepia indeks üretici
function getVintageToneClass(name, index) {
  let hash = index || 0;
  const str = String(name || "");
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 31 + str.charCodeAt(i)) % 997;
  }
  return `vintage-tone-${hash % 4}`;
}

// Tooltip konumunu layout-shift (left/top) yerine GPU translate3d + requestAnimationFrame ile güncelle
function updateTooltipPositionRaf(tooltip, event, container) {
  const [mx, my] = d3.pointer(event, container);
  if (_d3TooltipRafId) cancelAnimationFrame(_d3TooltipRafId);
  _d3TooltipRafId = requestAnimationFrame(() => {
    _d3TooltipRafId = null;
    tooltip.style("transform", `translate3d(${mx}px, ${my}px, 0) translate(-50%, -125%)`);
  });
}

/**
 * Harita kapsayıcısını ölçer ve Mercator projeksiyonunu sıfır boşlukla (fitExtent) hazırlar.
 * - geoIdentity ham boylam/enlemi düz çizdiği için Türkiye ~3:1 yassı görünüyordu;
 *   Mercator gerçek oranı (~2.3:1) verir ve haritayı belirgin biçimde büyütür.
 * - Mobilde (<=768px) kapsayıcı yüksekliği haritanın gerçek oranına göre ayarlanır;
 *   böylece 50vh kutunun içinde küçük bir şerit + boş alan kalmaz.
 */
function measureMapContainer(container, geo) {
  let width = container.clientWidth || container.getBoundingClientRect().width
    || (container.parentElement && container.parentElement.clientWidth) || 800;
  if (width < 100) width = 800;

  const isMobile = window.matchMedia("(max-width: 768px)").matches;
  const pad = isMobile ? 6 : 12;
  let height;

  if (isMobile) {
    const probe = d3.geoMercator().fitWidth(width - pad * 2, geo);
    const b = d3.geoPath(probe).bounds(geo);
    const natural = Math.ceil((b[1][1] - b[0][1]) + pad * 2);
    const maxH = Math.round((window.innerHeight || 700) * 0.72);
    height = Math.max(220, Math.min(natural, maxH));
    container.style.height = `${height}px`;
    container.style.minHeight = `${height}px`;
  } else {
    container.style.height = "";
    container.style.minHeight = "";
    height = container.clientHeight || container.getBoundingClientRect().height || 480;
    if (height < 100) height = 480;
  }

  const projection = d3.geoMercator().fitExtent([[pad, pad], [width - pad, height - pad]], geo);
  return { width, height, projection };
}

function drawD3Map() {
  cleanupD3Map();
  if (DOM.mapBoxTitle) DOM.mapBoxTitle.textContent = "🗺️ Katlanmış Anadolu Yol Haritası";
  if (DOM.btnBackToTurkeyMap) DOM.btnBackToTurkeyMap.classList.add("hidden");

  if (!STATE.geoData) return;

  _d3DrawRafId = requestAnimationFrame(() => {
    _d3DrawRafId = null;
    const container = DOM.d3Container;
    hideMapCompass(container);

    const { width, height, projection } = measureMapContainer(container, STATE.geoData);

    const tooltip = d3.select("#d3MapContainer")
      .append("div")
      .attr("class", "d3-map-tooltip");

    // Responsive SVG: kapsayıcının tamamını (%100 genişlik ve yükseklik) doldurur
    const svg = d3.select("#d3MapContainer").append("svg")
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("preserveAspectRatio", "xMidYMid meet")
      .style("width", "100%")
      .style("height", "100%")
      .attr("class", "vintage-d3-svg")
      .style("display", "block");

    // 1) Hafifletilmiş SVG Gradyan (<defs>)
    injectVintageMapDefs(svg);

    // 2) Arka Plan Antik Deniz Katmanı + Pusula Rhumb Çizgileri
    const bgGroup = svg.append("g").attr("class", "vintage-sea-bg");
    bgGroup.append("rect")
      .attr("width", width)
      .attr("height", height)
      .attr("fill", "url(#vintageSeaGrad)");
    drawNauticalGridLines(bgGroup, width, height);

    // Tight Bounding Box: Türkiye GeoJSON verisini sıfır boşlukla (fitSize / [[0,0],[width,height]]) SVG'ye tam yay

    const path = d3.geoPath().projection(projection);

    // Ana Zoom Katmanı (<g class="map-zoom-group">) — Tüm path ve kıyı elementleri bu gruba eklenir
    const g = svg.append("g").attr("class", "map-zoom-group vintage-map-root");

    // 3) Deniz / Kıyı Çizgileri (Bathymetry)
    const coastGroup = g.append("g").attr("class", "bathymetry-layer");
    const combinedOutlineD = path(STATE.geoData);

    coastGroup.append("path")
      .attr("d", combinedOutlineD)
      .attr("class", "coast-ring coast-ring-outer");

    coastGroup.append("path")
      .attr("d", combinedOutlineD)
      .attr("class", "coast-ring coast-ring-inner");

    // 4) Karalar (İller) Katmanı — Ağır SVG feDropShadow yerine GPU dostu katman
    const landGroup = g.append("g")
      .attr("class", "land-layer");

    const provincePaths = landGroup.selectAll("path.country-path")
      .data(STATE.geoData.features)
      .enter()
      .append("path")
      .attr("class", (d, i) => {
        const toneClass = getVintageToneClass(d.properties.name_tr, i);
        const isSelected = STATE.selectedCity === d.properties.name_tr;
        return `country-path province ${toneClass}${isSelected ? " selected" : ""}`;
      })
      .attr("d", path)
      .attr("id", d => `province-${d.properties.name_tr}`)
      .on("mouseenter", function(event, d) {
        tooltip.classed("visible", true).html(`<strong>🧭 ${d.properties.name_tr}</strong> · Diyarı keşfetmek için dokunun`);
        updateTooltipPositionRaf(tooltip, event, container);
      })
      .on("mousemove", function(event) {
        updateTooltipPositionRaf(tooltip, event, container);
      })
      .on("mouseleave", function() {
        tooltip.classed("visible", false);
      });

    // Hem masaüstü click hem mobil touchstart/touchend (tap) desteği
    bindD3TapAndClick(provincePaths, function(event, d) {
      selectCity(d.properties.name_tr);
    });

    // Zoom Davranışı (Pinch & Mouse Wheel) — .map-zoom-group üzerinde GPU hızlandırmalı
    const zoom = d3.zoom()
      .scaleExtent([1, 8])
      .translateExtent([[0, 0], [width, height]])
      .extent([[0, 0], [width, height]])
      .on("zoom", (event) => {
        const t = event.transform;
        if (_d3ZoomRafId) cancelAnimationFrame(_d3ZoomRafId);
        _d3ZoomRafId = requestAnimationFrame(() => {
          _d3ZoomRafId = null;
          d3.select("#d3MapContainer .map-zoom-group").attr("transform", t);
        });
      });
    svg.call(zoom).on("dblclick.zoom", null);
  });
}

const DISTRICT_GEO_CACHE = {};

async function loadDistrictGeo(cityName) {
  if (DISTRICT_GEO_CACHE[cityName]) return DISTRICT_GEO_CACHE[cityName];
  const slug = getCitySlug(cityName);
  if (!slug) return null;
  const cacheKey = `./assets/geo/districts/${slug}.geojson`;
  try {
    const data = await fetchCachedJSON(cacheKey);
    if (data) DISTRICT_GEO_CACHE[cityName] = data;
    return data;
  } catch (e) {
    console.error("Veri yüklenemedi:", e);
    return null;
  }
}

function drawProvinceMap(cityName, districtGeo) {
  cleanupD3Map();
  if (DOM.mapBoxTitle) DOM.mapBoxTitle.textContent = `${cityName} Haritası (İlçeler ve Mekanlar)`;
  if (DOM.btnBackToTurkeyMap) DOM.btnBackToTurkeyMap.classList.remove("hidden");

  // Eğer ilçe GeoJSON bulunamazsa ilin kendi poligonunu yedek olarak kullan
  const fallbackFeature = STATE.geoData && STATE.geoData.features.find(f => f.properties.name_tr === cityName);
  const geoToRender = (districtGeo && districtGeo.features && districtGeo.features.length > 0)
    ? districtGeo
    : (fallbackFeature ? { type: "FeatureCollection", features: [fallbackFeature] } : null);

  if (!geoToRender) return;

  _d3DrawRafId = requestAnimationFrame(() => {
    _d3DrawRafId = null;
    const container = DOM.d3Container;
    hideMapCompass(container);

    const { width, height, projection } = measureMapContainer(container, geoToRender);

    const tooltip = d3.select("#d3MapContainer")
      .append("div")
      .attr("class", "d3-map-tooltip");

    // Responsive SVG: kapsayıcının tamamını doldurur
    const svg = d3.select("#d3MapContainer").append("svg")
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("preserveAspectRatio", "xMidYMid meet")
      .style("width", "100%")
      .style("height", "100%")
      .attr("class", "vintage-d3-svg")
      .style("display", "block");

    injectVintageMapDefs(svg);

    const bgGroup = svg.append("g").attr("class", "vintage-sea-bg");
    bgGroup.append("rect")
      .attr("width", width)
      .attr("height", height)
      .attr("fill", "url(#vintageSeaGrad)");
    drawNauticalGridLines(bgGroup, width, height);

    // Tight Bounding Box: İl/İlçe sınırlarını sıfır boşlukla (fitSize) SVG'nin tamamına yay

    const path = d3.geoPath().projection(projection);
    const g = svg.append("g").attr("class", "map-zoom-group vintage-map-root");

    // İl dış sınırı etrafında kıyı / sınır konturu (Bathymetry)
    const coastGroup = g.append("g").attr("class", "bathymetry-layer");
    const combinedDistrictOutline = path(geoToRender);
    coastGroup.append("path").attr("d", combinedDistrictOutline).attr("class", "coast-ring coast-ring-outer");
    coastGroup.append("path").attr("d", combinedDistrictOutline).attr("class", "coast-ring coast-ring-inner");

    const landGroup = g.append("g")
      .attr("class", "land-layer");

    // İlçe başına mekan sayısı
    const districtCounts = {};
    (STATE.places || []).forEach(p => {
      if (p.ilce) districtCounts[p.ilce] = (districtCounts[p.ilce] || 0) + 1;
    });

    // İlçe poligonları
    const districtPaths = landGroup.selectAll("path.district-path")
      .data(geoToRender.features)
      .enter()
      .append("path")
      .attr("class", (d, i) => {
        const name = d.properties.name_tr || "";
        const toneClass = getVintageToneClass(name, i);
        const hasPlaces = (districtCounts[name] || 0) > 0;
        const isSelected = STATE.selectedDistrict && STATE.selectedDistrict === name;
        return `district-path province ${toneClass}${hasPlaces ? " has-places" : ""}${isSelected ? " selected" : ""}`;
      })
      .attr("d", path)
      .on("mouseenter", function(event, d) {
        const name = d.properties.name_tr || cityName;
        const cnt = districtCounts[name] || 0;
        tooltip
          .classed("visible", true)
          .html(`<strong>${name}</strong>${cnt > 0 ? ` · ${cnt} mekan` : " · Mekan yok"}`);
        updateTooltipPositionRaf(tooltip, event, container);
      })
      .on("mousemove", function(event) {
        updateTooltipPositionRaf(tooltip, event, container);
      })
      .on("mouseleave", function() {
        tooltip.classed("visible", false);
      });

    bindD3TapAndClick(districtPaths, function(event, d) {
      const clickedDistrict = d.properties.name_tr || "";
      if (!clickedDistrict) return;
      STATE.selectedDistrict = (STATE.selectedDistrict === clickedDistrict) ? "" : clickedDistrict;
      if (DOM.districtSelect && !DOM.districtSelect.disabled) {
        const hasOption = Array.from(DOM.districtSelect.options).some(o => o.value === STATE.selectedDistrict);
        DOM.districtSelect.value = hasOption ? STATE.selectedDistrict : "";
      }
      filterPlaces();
      syncProvinceMapSelection();
    });

    // İlçe isim etiketleri
    g.selectAll("text.district-label")
      .data(geoToRender.features)
      .enter()
      .append("text")
      .attr("class", "district-label")
      .attr("transform", d => {
        const c = path.centroid(d);
        return Number.isFinite(c[0]) && Number.isFinite(c[1]) ? `translate(${c[0]},${c[1]})` : "translate(-999,-999)";
      })
      .text(d => {
        const b = path.bounds(d);
        const bw = Math.abs((b[1] && b[1][0]) - (b[0] && b[0][0]));
        const bh = Math.abs((b[1] && b[1][1]) - (b[0] && b[0][1]));
        if (bw < 26 || bh < 14) return "";
        return d.properties.name_tr || "";
      });

    // Seçili ilçe için mum mühür / "X" işareti katmanı
    const districtSealLayer = g.append("g").attr("class", "wax-seal-layer");

    // Mekan pinleri katmanı
    const pinsLayer = g.append("g").attr("class", "province-pins-layer");

    function renderPins() {
      requestAnimationFrame(() => {
        districtSealLayer.selectAll("*").remove();
        if (STATE.selectedDistrict) {
          const targetFeat = geoToRender.features.find(f => f.properties && f.properties.name_tr === STATE.selectedDistrict);
          if (targetFeat) {
            const [cx, cy] = path.centroid(targetFeat);
            if (Number.isFinite(cx) && Number.isFinite(cy)) {
              const marker = districtSealLayer.append("g")
                .attr("class", "wax-seal-stamp")
                .attr("transform", `translate(${cx},${cy - 14})`);
              marker.append("circle").attr("r", 10).attr("class", "wax-seal-circle");
              marker.append("text").attr("dy", "3.5").attr("text-anchor", "middle").attr("class", "wax-seal-x").text("✕");
            }
          }
        }

        const activePlaces = (STATE.filteredPlaces || []).filter(p => p.lat && p.lon);
        const pins = pinsLayer.selectAll("circle.province-place-pin")
          .data(activePlaces, d => d.id);

        pins.exit().on("mouseenter mousemove mouseleave click touchstart touchend", null).remove();

        const mergedPins = pins.enter()
          .append("circle")
          .attr("class", "province-place-pin")
          .attr("r", 4.5)
          .merge(pins)
          .attr("cx", d => {
            const pt = projection([d.lon, d.lat]);
            return pt ? pt[0] : -999;
          })
          .attr("cy", d => {
            const pt = projection([d.lon, d.lat]);
            return pt ? pt[1] : -999;
          })
          .on("mouseenter", function(event, d) {
            tooltip
              .classed("visible", true)
              .html(`<strong>${escapeHtml(d.ad)}</strong> (${escapeHtml(d.kategori)})${d.ilce ? ` · ${escapeHtml(d.ilce)}` : ""}`);
            updateTooltipPositionRaf(tooltip, event, container);
          })
          .on("mousemove", function(event) {
            updateTooltipPositionRaf(tooltip, event, container);
          })
          .on("mouseleave", function() {
            tooltip.classed("visible", false);
          });

        bindD3TapAndClick(mergedPins, function(event, d) {
          window.location.hash = getPlaceHash(d);
        });
      });
    }

    renderPins();
    STATE.updateProvinceMapPins = renderPins;

    // Boş alana tıklanınca ilçe seçimini sıfırla
    svg.on("click", () => {
      if (Date.now() - _lastTouchActionTime < 450) return;
      if (STATE.selectedDistrict) {
        STATE.selectedDistrict = "";
        if (DOM.districtSelect) DOM.districtSelect.value = "";
        filterPlaces();
        syncProvinceMapSelection();
      }
    });

    // Zoom & Pan (Pinch & Mouse Wheel) — .map-zoom-group üzerinde 60 FPS akıcı pan/zoom
    const zoom = d3.zoom()
      .scaleExtent([1, 8])
      .translateExtent([[0, 0], [width, height]])
      .extent([[0, 0], [width, height]])
      .on("zoom", (event) => {
        const t = event.transform;
        if (_d3ZoomRafId) cancelAnimationFrame(_d3ZoomRafId);
        _d3ZoomRafId = requestAnimationFrame(() => {
          _d3ZoomRafId = null;
          d3.select("#d3MapContainer .map-zoom-group").attr("transform", t);
        });
      });
    svg.call(zoom).on("dblclick.zoom", null);
  });
}

function syncProvinceMapSelection() {
  d3.selectAll("#d3MapContainer .district-path")
    .classed("selected", d => d && d.properties && d.properties.name_tr === STATE.selectedDistrict);
  if (typeof STATE.updateProvinceMapPins === "function") {
    STATE.updateProvinceMapPins();
  }
}

function resetToTurkeyMap() {
  STATE.selectedCity = "";
  STATE.selectedDistrict = "";
  STATE.places = [];
  STATE.filteredPlaces = [];
  STATE.updateProvinceMapPins = null;
  cleanupLeafletLayers();

  DOM.citySelect.value = "";
  DOM.globalCityLabel.textContent = "Tüm Türkiye";
  DOM.globalStatsLabel.textContent = "Veri Yok";

  DOM.districtSelect.innerHTML = '<option value="">Önce İl Seçin</option>';
  DOM.districtSelect.disabled = true;
  DOM.searchInput.value = "";
  DOM.searchInput.disabled = true;
  DOM.categoryFilter.innerHTML = '<option value="">Tüm Kategoriler</option>';
  DOM.categoryFilter.disabled = true;
  DOM.btnGoToMap.classList.add("disabled");

  DOM.placesGrid.innerHTML = `
    <div class="empty-state">
      <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
      <p>Lütfen önce arama yapmak için haritadan veya listeden bir il seçin.</p>
    </div>`;

  updateFoodSection();
  drawD3Map();
}

function populateSelects() {
  if (!STATE.geoData || !DOM.citySelect) return;
  const cities = STATE.geoData.features.map(f => f.properties.name_tr).sort((a,b) => a.localeCompare(b, 'tr'));

  const frag = document.createDocumentFragment();
  const defaultOpt = document.createElement("option");
  defaultOpt.value = "";
  defaultOpt.textContent = "Türkiye Geneli (Tümü)";
  frag.appendChild(defaultOpt);

  cities.forEach(city => {
    const opt = document.createElement("option");
    opt.value = city;
    opt.textContent = city;
    frag.appendChild(opt);
  });

  DOM.citySelect.innerHTML = "";
  DOM.citySelect.appendChild(frag);
}

// ================= CITY SELECTION & OVERPASS =================
async function selectCity(cityName) {
  if (!cityName) {
    resetToTurkeyMap();
    return;
  }
  
  STATE.selectedCity = cityName;
  STATE.selectedDistrict = '';         // İl değişince ilçe sıfırla
  DOM.citySelect.value = cityName;
  DOM.globalCityLabel.textContent = cityName;
  // İlçe dropdown'ı sıfırla yüklenene kadar
  DOM.districtSelect.innerHTML = '<option value="">Yükleniyor...</option>';
  DOM.districtSelect.disabled = true;

  // Butonları aç
  DOM.btnGoToMap.classList.remove('disabled');
  DOM.searchInput.disabled = false;
  DOM.categoryFilter.disabled = false;

  // Eğer hem il verisi hem ilçe sınırları RAM'de (dataCache) hazırsa pusula göstermeden anında çiz!
  const slug = getCitySlug(cityName);
  const isCached = Boolean(
    CITY_CACHE[cityName] &&
    (DISTRICT_GEO_CACHE[cityName] || (slug && dataCache.has(`./assets/geo/districts/${slug}.geojson`)))
  );
  if (!isCached) {
    showMapCompass(DOM.d3Container, `${cityName} haritası hazırlanıyor...`);
  }

  const [, districtGeo] = await Promise.all([
    loadCityData(cityName),
    loadDistrictGeo(cityName)
  ]).catch(err => {
    console.error("İl verisi yüklenemedi:", err);
    return [null, null];
  });
  hideMapCompass(DOM.d3Container);

  if (STATE.selectedCity === cityName) {
    drawProvinceMap(cityName, districtGeo);
  }
}

// Lokal GeoJSON üzerinden Enlem-Boylam Sınır Kutusu Çıkartma
function calculateCityBBox(cityName) {
    if (!STATE.geoData) return null;
    const feature = STATE.geoData.features.find(f => f.properties.name_tr === cityName);
    if (!feature) return null;

    let minLat = 90, maxLat = -90, minLon = 180, maxLon = -180;
    const findCoords = (coords) => {
        for (const item of coords) {
            if (typeof item[0] === 'number') {
                const lat = item[1], lon = item[0];
                if (lat < minLat) minLat = lat;
                if (lat > maxLat) maxLat = lat;
                if (lon < minLon) minLon = lon;
                if (lon > maxLon) maxLon = lon;
            } else if (Array.isArray(item)) {
                findCoords(item);
            }
        }
    };
    findCoords(feature.geometry.coordinates);
    return `[bbox:${minLat},${minLon},${maxLat},${maxLon}]`;
}

// ================= POPÜLERLİK PUANLAMA & SIRALAMA SİSTEMİ =================
const CATEGORY_POPULARITY_WEIGHTS = {
  "Antik Kent": 10,
  "Tarihi / Antik Kent": 10,
  "Müze": 10,
  "Milli Park": 10,
  "Doğa Parkı": 9.5,
  "Plaj / Koy": 9.5,
  "Şelale": 9.5,
  "Kanyon": 9.5,
  "Kale / Hisar": 9,
  "Saray / Köşk": 9,
  "Yayla": 9,
  "Göl / Nehir": 8.5,
  "Mağara": 8.5,
  "Kaplıca": 8.5,
  "Ada": 8.5,
  "Kervansaray / Han": 8,
  "Tarihi Camii": 8,
  "Tarihi Kilise": 8,
  "Tarihi Kapı": 8,
  "Seyir Noktası": 8,
  "Sahil / Kordon": 8,
  "Vadi": 8,
  "Türbe / Külliye": 7.5,
  "Medrese": 7.5,
  "Tarihi Köprü": 7.5,
  "Tarihi Konak": 7.5,
  "Turistik Alan": 7,
  "Anıt": 6.5,
  "Tarihi Hamam": 6.5,
  "Saat Kulesi": 6,
  "Deniz Feneri": 6,
  "Dağ Zirvesi": 6,
  "Park": 5,
  "Sanat Eseri": 5,
  "Eğlence Parkı": 5,
  "Diğer": 1
};

/**
 * Bir mekanın popülerlik / ünlülük puanı:
 * 1) Türkçe Wikipedia maddesinin son 12 aylık görüntülenmesi (pop) — en güçlü sinyal.
 *    log ölçeği: 1.000 görüntülenme ≈ +9, 100.000 ≈ +15, 1.000.000 ≈ +18
 * 2) Kaç dilde Wikipedia maddesi olduğu (sl) — uluslararası bilinirlik
 * 3) Kategori ağırlığı (Antik Kent / Müze / Milli Park = 10, Diğer = 1)
 * 4) Doğrulanmış fotoğraf
 */
function getPlacePopularityScore(place) {
  if (!place) return 0;
  if (typeof place._score === "number") return place._score;

  let score = CATEGORY_POPULARITY_WEIGHTS[place.kategori] || 2;
  // Ünlülük: Wikipedia görüntülenmesi (pop) veya kaç dilde maddesi olduğu (sl) — hangisi güçlüyse
  // sl: 1 dil ≈ +2, 10 dil ≈ +7.6, 50 dil ≈ +12.5, 100 dil ≈ +14.7
  const pop = Number(place.pop) || 0;
  const sl = Number(place.sl) || 0;
  score += Math.max(pop > 0 ? Math.log10(pop + 1) * 3 : 0, sl > 0 ? Math.log2(sl + 1) * 2.2 : 0);

  if (place.img && String(place.img).trim() !== "") score += 2;

  const wpRef = String(place.wp || place.wiki || (place.tags && place.tags.wikipedia) || "");
  if (!pop && wpRef.startsWith("tr:")) score += 2;

  place._score = score;
  return score;
}

/**
 * Mekan listesini A-Z yerine popülerliğe göre sıralar (en meşhur yerler en üstte).
 */
function sortPlacesByPopularity(places) {
  if (!Array.isArray(places)) return [];
  return places.sort((a, b) => {
    const scoreDiff = getPlacePopularityScore(b) - getPlacePopularityScore(a);
    if (scoreDiff !== 0) return scoreDiff;
    return String(a.ad || "").localeCompare(String(b.ad || ""), "tr");
  });
}

// ================= HAZIR VERİ (data/places/*.json) & RAM CACHE =================
// Veriler scripts/build_places.py ile önceden üretilir; dataCache ile RAM'de tutulur.
const CITY_CACHE = {};

function getCitySlug(cityName) {
  const f = STATE.geoData && STATE.geoData.features.find(x => x.properties.name_tr === cityName);
  return f && f.properties.slug ? f.properties.slug : null;
}

async function loadStaticCityData(cityName) {
  if (CITY_CACHE[cityName]) {
    return CITY_CACHE[cityName];
  }
  const slug = getCitySlug(cityName);
  if (!slug) return null;
  const parsedCacheKey = `places_parsed:${slug}`;
  if (dataCache.has(parsedCacheKey)) {
    const cached = dataCache.get(parsedCacheKey);
    CITY_CACHE[cityName] = cached;
    return cached;
  }
  try {
    const list = await fetchCachedJSON(`./data/places/${slug}.json`);
    if (!Array.isArray(list)) return null;
    // Fotoğrafı olmayan (ama Wikidata/Wikipedia ile doğrulanmış) yerler de listelenir;
    // böylece plaj, yayla, göl gibi eksik kalan yerler görünür. Fotoğraflılar sıralamada öne geçer.
    const verified = list.filter(p => p && p.ad && Number.isFinite(p.lat) && Number.isFinite(p.lon));
    // Eski kodla uyum için tags alanını düz alanlardan oluştur
    const mapped = verified.map(p => ({
      ...p,
      ilce: p.ilce || '',
      fromStatic: true, // statik veri: stok fotoğraf yerine fotoğrafsız kart
      wiki: p.wiki || p.wikidata || null,
      tags: { wikipedia: p.wiki, wikidata: p.wikidata, image: p.image }
    }));
    // Alfabetik yerine popülerlik puanına göre sırala
    sortPlacesByPopularity(mapped);
    dataCache.set(parsedCacheKey, mapped);
    CITY_CACHE[cityName] = mapped;
    return mapped;
  } catch (e) {
    console.error("Veri yüklenemedi:", e);
    return null;
  }
}

/**
 * Arka Plan Ön Yükleme (Background Prefetch):
 * Harita ilk çizildiğinde tarayıcı boşta iken (requestIdleCallback / setTimeout)
 * önce index.json ve en popüler illeri, ardından diğer illeri sessizce RAM'e (dataCache) alır.
 */
let _prefetchStarted = false;
function scheduleBackgroundPrefetch() {
  if (_prefetchStarted) return;
  _prefetchStarted = true;

  const runIdle = (fn, delay = 250) => {
    if (typeof window.requestIdleCallback === "function") {
      window.requestIdleCallback(fn, { timeout: 2000 });
    } else {
      setTimeout(fn, delay);
    }
  };

  const priorityCities = [
    "İstanbul", "Antalya", "İzmir", "Ankara", "Muğla", "Bursa",
    "Nevşehir", "Çanakkale", "Trabzon", "Gaziantep", "Hatay",
    "Mardin", "Aydın", "Balıkesir", "Konya", "Adana", "Şanlıurfa", "Kars"
  ];

  // Veri tasarrufu modu / yavaş bağlantıda arka plan indirmesi yapma (mobil veriyi koru)
  const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  if (conn && (conn.saveData || /(^|-)2g$/.test(conn.effectiveType || ""))) return;
  const isCellular = Boolean(conn && conn.type === "cellular");

  runIdle(() => {
    // Yalnızca en çok ziyaret edilen illeri 2'şerli küçük paketlerle RAM'e al.
    // (Önceden 81 ilin tamamı + 81 ilçe GeoJSON'u indiriliyordu: mobilde gereksiz megabaytlar.)
    // Hücresel bağlantıda sadece küçük ilçe sınırlarını al; mekan listesi il seçilince gelir.
    let idx = 0;
    const prefetchNextBatch = () => {
      const batch = priorityCities.slice(idx, idx + 2);
      idx += 2;
      if (batch.length === 0) return;

      Promise.allSettled(
        batch.map(cityName => isCellular
          ? loadDistrictGeo(cityName)
          : Promise.all([loadStaticCityData(cityName), loadDistrictGeo(cityName)]))
      ).finally(() => {
        if (idx < priorityCities.length) runIdle(prefetchNextBatch, 500);
      });
    };

    prefetchNextBatch();
  }, 1200);
}

function applyCityPlaces(cityName, places) {
  // Kullanıcı bu arada başka il seçtiyse eski sonucu uygulama
  if (STATE.selectedCity && STATE.selectedCity !== cityName) return;
  STATE.places = places;
  STATE.filteredPlaces = [...places];
  updateCategoryFilters();
  updateDistrictFilter();
  filterPlaces();
  if (STATE.leafletMap && STATE.view === 'map') renderMapMarkers();
}

async function loadCityData(cityName) {
  // 1) Bellek önbelleği (dataCache / CITY_CACHE) — aynı il veya prefetch edilmiş il seçilince 0ms
  if (CITY_CACHE[cityName]) {
    applyCityPlaces(cityName, CITY_CACHE[cityName]);
    return;
  }
  // 2) Hazır statik JSON (dataCache üzerinden)
  const staticPlaces = await loadStaticCityData(cityName);
  if (staticPlaces) {
    CITY_CACHE[cityName] = staticPlaces;
    applyCityPlaces(cityName, staticPlaces);
    return;
  }
  // 3) Yedek: canlı Overpass sorgusu
  return loadCityDataFromOverpass(cityName);
}

async function loadCityDataFromOverpass(cityName) {
  showLoader(`${cityName} verileri yükleniyor...`);
  
  let bbox = calculateCityBBox(cityName);
  let areaDef = ""; let suffix = "";
  if (!bbox) {
     areaDef = `area["boundary"="administrative"]["admin_level"="4"]["name"="${cityName}"]->.searchArea;`;
     suffix = "(area.searchArea)";
  }

  const query = `
      [out:json][timeout:45]${bbox};
      ${areaDef}
      (
          node["tourism"="museum"]${suffix};
          way["tourism"="museum"]${suffix};
          node["tourism"="attraction"]${suffix};
          way["tourism"="attraction"]${suffix};
          node["tourism"="artwork"]${suffix};
          node["tourism"="viewpoint"]${suffix};
          node["tourism"="theme_park"]${suffix};
          node["historic"="castle"]${suffix};
          way["historic"="castle"]${suffix};
          node["historic"="ruins"]${suffix};
          way["historic"="ruins"]${suffix};
          node["historic"="archaeological_site"]${suffix};
          way["historic"="archaeological_site"]${suffix};
          node["historic"="monument"]${suffix};
          way["historic"="monument"]${suffix};
          node["historic"="memorial"]${suffix};
          node["historic"="fort"]${suffix};
          way["historic"="fort"]${suffix};
          node["historic"="city_gate"]${suffix};
          way["historic"="city_gate"]${suffix};
          node["historic"="mosque"]${suffix};
          way["historic"="mosque"]${suffix};
          node["historic"="church"]${suffix};
          way["historic"="church"]${suffix};
          node["natural"="waterfall"]${suffix};
          node["natural"="cave_entrance"]${suffix};
          node["natural"="peak"]${suffix};
          node["natural"="beach"]${suffix};
          way["natural"="beach"]${suffix};
          node["natural"="hot_spring"]${suffix};
          node["leisure"="nature_reserve"]${suffix};
          way["leisure"="nature_reserve"]${suffix};
          node["leisure"="park"]["name"]${suffix};
          node["amenity"="place_of_worship"]["historic"]${suffix};
          way["amenity"="place_of_worship"]["historic"]${suffix};
      );
      out center tags;
  `;

  let fetchedData = null;
  for (const url of STATE.endpoints) {
      try {
          const res = await fetch(url, {
              method: "POST",
              headers: { "Content-Type": "application/x-www-form-urlencoded" },
              body: "data=" + encodeURIComponent(query)
          });
          if (res.ok) {
              fetchedData = await res.json();
              break;
          }
      } catch (e) {
          console.warn(`${url} başarısız oldu, diğer sunucuya geçiliyor...`);
      }
  }

  hideLoader();

  if (!fetchedData || !fetchedData.elements) {
      DOM.placesGrid.innerHTML = `
        <div class="empty-state">
          <p style="color:var(--accent-color);">Veri çekilirken sunucu hatası (504) veya Limit engeli oluştu.</p>
          <button type="button" class="btn-primary btn-retry-city" style="width: auto;">Tekrar Dene</button>
        </div>`;
      STATE.places = [];
      STATE.filteredPlaces = [];
      DOM.globalStatsLabel.textContent = "Veri alınamadı";
      const retryBtn = DOM.placesGrid.querySelector(".btn-retry-city");
      if (retryBtn) retryBtn.addEventListener("click", () => loadCityData(cityName));
      return;
  }

  // Parse Overpass Elements (node + way + relation)
  STATE.places = fetchedData.elements.map(el => {
      const t = el.tags || {};
      const nameTR = t['name:tr'];
      const nameGen = t.name;
      const nameEN = t['name:en'];

      // Ad belirleme: Türkçe ad varsa öncelikli kullan
      const name = nameTR || nameGen;
      if (!name || name.trim() === '') return null;

      // ── TÜRKÇE / YABANCI DİL FİLTRESİ ────────────────────────
      // Kural 0: Her durumda — Latin-dışı alfabe (Arapça/Kiril/CJK) → çıkar
      // (name:tr olsa bile yanlış etiketlenmiş olabilir)
      if (/[؀-ۿЀ-ӿ一-鿿぀-ヿ＀-￯]/.test(name)) return null;

      // name:tr varsa Türkçe kabul et; yoksa ek filtreler uygula
      if (!nameTR) {
          // Kural 2: name:en ile birebir aynıysa İngilizce → çıkar
          if (nameEN && nameGen === nameEN) return null;
          // Kural 3: Tamamen ASCII + Türkçe harf yok → yabancı → çıkar
          const hasTurkishChar = /[ğşıçöüĞŞİÇÖÜ]/.test(nameGen || '');
          const isPureAscii = /^[a-zA-Z0-9 \-\.\,\/\(\)\'"]+$/.test(nameGen || '');
          if (!hasTurkishChar && isPureAscii) return null;
          // Kural 4: İngilizce coğrafi anahtar kelimeler → çıkar
          const engWords = /\b(statue|lake|river|mountain|mount|peak|ruins|cave|beach|bay|island|valley|forest|church|temple|bridge|gate|road|ancient|national|reserve|nature|hill|spring|tower|wall|palace|shrine)\b/i;
          if (engWords.test(nameGen || '')) return null;
      }
      // ─────────────────────────────────────────────────────────

      let cat = 'Diğer';
      if (t.tourism === 'museum') cat = 'Müze';
      else if (t.tourism === 'attraction') cat = 'Turistik Alan';
      else if (t.tourism === 'viewpoint') cat = 'Seyir Noktası';
      else if (t.tourism === 'artwork') cat = 'Sanat Eseri';
      else if (t.tourism === 'theme_park') cat = 'Eğlence Parkı';
      else if (t.historic === 'castle' || t.historic === 'fort') cat = 'Kale / Hisar';
      else if (t.historic === 'ruins' || t.historic === 'archaeological_site') cat = 'Antik Kent';
      else if (t.historic === 'monument' || t.historic === 'memorial') cat = 'Anıt';
      else if (t.historic === 'city_gate') cat = 'Tarihi Kapı';
      else if (t.historic === 'mosque' || (t.amenity === 'place_of_worship' && t.religion === 'muslim')) cat = 'Tarihi Camii';
      else if (t.historic === 'church' || (t.amenity === 'place_of_worship' && t.religion === 'christian')) cat = 'Tarihi Kilise';
      else if (t.natural === 'waterfall') cat = 'Şelale';
      else if (t.natural === 'cave_entrance') cat = 'Mağara';
      else if (t.natural === 'peak') cat = 'Dağ Zirvesi';
      else if (t.natural === 'beach') cat = 'Plaj / Koy';
      else if (t.natural === 'hot_spring') cat = 'Kaplıca';
      else if (t.leisure === 'nature_reserve') cat = 'Doğa Parkı';
      else if (t.leisure === 'park') cat = 'Park';

      return {
          id: `${el.type}:${el.id}`,
          ad: name,
          il: cityName,
          // Sadece ilçe seviyesi: addr:district > addr:county
          // addr:suburb / addr:quarter mahalle düzeyinde → kullanma
          ilce: t['addr:district'] || t['addr:county'] || t['is_in:district'] || t.ilce || '',

          lat: el.lat || (el.center && el.center.lat) || 0,
          lon: el.lon || (el.center && el.center.lon) || 0,
          kategori: cat,
          wiki: t.wikipedia || t.wikidata || null,
          tags: t
      };
  }).filter(i => i !== null);

  // Remove duplicates
  const uniq = [];
  const seens = new Set();
  STATE.places.forEach(p => {
     let lower = p.ad.toLowerCase();
     if (!seens.has(lower)) { seens.add(lower); uniq.push(p); }
  });
  
  sortPlacesByPopularity(uniq);
  CITY_CACHE[cityName] = uniq;
  applyCityPlaces(cityName, uniq);
  
  // Sadece yedek yolda: ilçe bilgisi eksik mekanlar için Nominatim ile zenginleştir
  enrichDistrictsFromNominatim();
}

// Nominatim reverse geocoding ile ilçe bilgisini arka planda doldur
async function enrichDistrictsFromNominatim() {
  const missing = STATE.places.filter(p => !p.ilce && p.lat && p.lon);
  if (missing.length === 0) return;

  // Nominatim rate limit: max 1 req/sn — 5 mekanı örnekle yeterli
  const sample = missing.slice(0, 30);

  for (const place of sample) {
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${place.lat}&lon=${place.lon}&zoom=10&addressdetails=1`,
        { headers: { 'Accept-Language': 'tr' } }
      );
      if (!res.ok) continue;
      const data = await res.json();
      const addr = data.address || {};
      // Türkiye'de Nominatim'de ilçe = county
      // suburb/town mahalle/semt düzeyinde olduğu için kullanma
      const district = addr.county || addr.district || '';

      if (district) {
        place.ilce = district;
        // STATE'deki place objesini de güncelle (referans aynı)
      }
      // Nominatim'e saygı: 1 saniye bekle
      await new Promise(r => setTimeout(r, 1100));
    } catch (e) {}
  }

  // İlçe dropdown'ını güncelle
  updateDistrictFilter();
}



// ================= UI RENDER (EXPLORE LIST — DOCUMENT FRAGMENT & LAZY RENDERING) =================
const LAZY_RENDER_BATCH_SIZE = 24;
let _placesRenderedCount = 0;
let _placesIntersectionObserver = null;

function disconnectPlacesObserver() {
  if (_placesIntersectionObserver) {
    _placesIntersectionObserver.disconnect();
    _placesIntersectionObserver = null;
  }
}

function updateCategoryFilters() {
    const cats = Array.from(new Set(STATE.places.map(p => p.kategori))).sort((a, b) => a.localeCompare(b, 'tr'));

    const buildOptionsFragment = () => {
        const frag = document.createDocumentFragment();
        const defOpt = document.createElement("option");
        defOpt.value = "";
        defOpt.textContent = "Tüm Kategoriler";
        frag.appendChild(defOpt);

        cats.forEach(c => {
            const opt = document.createElement("option");
            opt.value = c;
            opt.textContent = c;
            frag.appendChild(opt);
        });
        return frag;
    };

    if (DOM.categoryFilter) {
        DOM.categoryFilter.innerHTML = "";
        DOM.categoryFilter.appendChild(buildOptionsFragment());
    }
    if (DOM.mapCategoryFilter) {
        DOM.mapCategoryFilter.innerHTML = "";
        DOM.mapCategoryFilter.appendChild(buildOptionsFragment());
    }
}

function updateDistrictFilter() {
    // Mekanlardan çıkan benzersiz ilçeleri toplat
    const districts = [...new Set(
        STATE.places
            .map(p => p.ilce)
            .filter(d => d && d.trim() !== '')
    )].sort((a, b) => a.localeCompare(b, 'tr'));

    if (!DOM.districtSelect) return;

    if (districts.length === 0) {
        DOM.districtSelect.innerHTML = '<option value="">Tüm İlçeler</option>';
        DOM.districtSelect.disabled = true;
        return;
    }

    const frag = document.createDocumentFragment();
    const defOpt = document.createElement("option");
    defOpt.value = "";
    defOpt.textContent = "Tüm İlçeler";
    frag.appendChild(defOpt);

    districts.forEach(d => {
        const opt = document.createElement("option");
        opt.value = d;
        opt.textContent = d;
        frag.appendChild(opt);
    });

    DOM.districtSelect.innerHTML = "";
    DOM.districtSelect.appendChild(frag);
    DOM.districtSelect.disabled = false;
    DOM.districtSelect.value = STATE.selectedDistrict || '';
}

function filterPlaces() {
    const search = (DOM.searchInput.value || "").toLowerCase();
    const cat    = DOM.categoryFilter.value;
    const dist   = STATE.selectedDistrict || DOM.districtSelect.value;

    const filtered = STATE.places.filter(p => {
        const matchSearch = p.ad.toLowerCase().includes(search) || (p.ilce || "").toLowerCase().includes(search);
        const matchCat    = cat  === '' || p.kategori === cat;
        const matchDist   = dist === '' || p.ilce === dist;
        return matchSearch && matchCat && matchDist;
    });

    // DOM'a basmadan önce popülerliğe göre sırala
    STATE.filteredPlaces = sortPlacesByPopularity(filtered);

    updateExploreUI();
    syncProvinceMapSelection();
    updateFoodSection();
}

/**
 * Tek bir mekan kartı için DOM elementi üretir (innerHTML += kullanmadan DocumentFragment içine eklenir).
 */
function createPlaceCardElement(place) {
    const inRoute = isPlaceInRoute(place.id);
    const card = document.createElement("div");
    card.className = "place-card glass-panel";
    card.addEventListener("click", () => {
        window.location.hash = getPlaceHash(place);
    });

    const tags = place.tags || {};
    card.innerHTML = `
        <div class="card-image-wrapper">
            <img class="card-image" src="" alt="${escapeHtml(place.ad)}"
                 data-wiki="${escapeHtml(place.ad)}"
                 data-img="${safeUrl(place.img)}"
                 data-static="${place.fromStatic ? '1' : ''}"
                 data-wiki2="${escapeHtml(place.wiki || '')}"
                 data-wikidata="${escapeHtml(tags.wikidata || '')}"
                 data-osm-image="${safeUrl(tags.image || tags['image:0'] || '')}"
                 data-kategori="${escapeHtml(place.kategori)}"
                 loading="lazy">
        </div>
        <div class="card-content">
            <span class="card-category">${escapeHtml(place.kategori)}</span>
            <h3 class="card-title">${escapeHtml(place.ad)}</h3>
            <div class="card-location">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-color)" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                ${place.ilce ? escapeHtml(place.ilce) + ', ' : ''}${escapeHtml(place.il)}
            </div>
            <div class="card-actions-row">
                <button type="button"
                        class="card-route-btn ${inRoute ? 'added' : ''}"
                        data-route-id="${safeId(place.id)}">
                    ${inRoute ? '✓ Günlükte (Çıkar)' : '📜 Rotama Ekle'}
                </button>
            </div>
        </div>
    `;

    const routeBtn = card.querySelector(".card-route-btn");
    if (routeBtn) {
        routeBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            window.handleCardRouteClick(place.id);
        });
    }

    return card;
}

function createInFeedAdElement() {
    const adDiv = document.createElement("div");
    adDiv.className = "vintage-ad-slot vintage-ad-card";
    adDiv.setAttribute("data-ad-slot-key", "inFeed");
    adDiv.setAttribute("data-ad-format", "fluid");
    adDiv.setAttribute("aria-label", "Sponsorlu Keşif Kartı");
    adDiv.innerHTML = `
        <div class="vintage-ad-header">
            <span>🧭 SEYAHATNAME NOTU</span>
            <span class="vintage-ad-badge">İLAN</span>
        </div>
        <div class="vintage-ad-body">
            <div class="vintage-ad-placeholder">
                <span class="vintage-ad-compass">🏕️</span>
                <strong>${escapeHtml(STATE.selectedCity || 'Anadolu')} Keşif &amp; Konaklama Rehberi</strong>
                <p>Rotanız üzerindeki butik taş konaklar, yerel rehberler ve doğa kampları için ayrılmış özel vitrin.</p>
            </div>
        </div>
    `;
    if (ADS_CONFIG.inFeedLayoutKey) adDiv.setAttribute("data-ad-layout-key", ADS_CONFIG.inFeedLayoutKey);
    return adDiv;
}

/**
 * Sıradaki 24 mekanlık partiyi DocumentFragment ile tek seferde DOM'a basar (Lazy Rendering).
 * Alt kısma "Daha Fazla Göster" butonu + IntersectionObserver (sonsuz kaydırma) ekler.
 */
function renderNextPlacesBatch() {
    const total = STATE.filteredPlaces.length;
    if (_placesRenderedCount >= total) return;

    // Eski "Daha Fazla Göster" sentinel kutusunu kaldır
    const oldSentinel = document.getElementById("placesLoadMoreSentinel");
    if (oldSentinel) oldSentinel.remove();
    disconnectPlacesObserver();

    const startIdx = _placesRenderedCount;
    const endIdx = Math.min(startIdx + LAZY_RENDER_BATCH_SIZE, total);
    const batch = STATE.filteredPlaces.slice(startIdx, endIdx);

    const fragment = document.createDocumentFragment();
    const newImages = [];
    let inFeedAdEl = null;

    batch.forEach((place, i) => {
        const globalIdx = startIdx + i;
        // İlk partide 4. karttan sonra In-Feed Seyahatname reklam kartını ekle
        if (globalIdx === 4 && adsAreLive()) {
            inFeedAdEl = createInFeedAdElement();
            fragment.appendChild(inFeedAdEl);
        }
        const cardEl = createPlaceCardElement(place);
        const imgEl = cardEl.querySelector("img[data-wiki]");
        if (imgEl) newImages.push(imgEl);
        fragment.appendChild(cardEl);
    });

    _placesRenderedCount = endIdx;

    // Hâlâ gösterilmemiş mekanlar varsa "Daha Fazla Göster" butonu + IntersectionObserver ekle
    const remaining = total - _placesRenderedCount;
    let sentinelEl = null;
    if (remaining > 0) {
        sentinelEl = document.createElement("div");
        sentinelEl.id = "placesLoadMoreSentinel";
        sentinelEl.className = "load-more-sentinel";
        sentinelEl.innerHTML = `
            <button type="button" class="btn-primary btn-load-more">
                📜 Daha Fazla Keşif Noktası Göster (${remaining} mekan daha)
            </button>
        `;
        const loadMoreBtn = sentinelEl.querySelector(".btn-load-more");
        if (loadMoreBtn) {
            loadMoreBtn.addEventListener("click", () => renderNextPlacesBatch());
        }
        fragment.appendChild(sentinelEl);
    }

    // DocumentFragment'i DOM'a tek seferde ekle (Reflow / UI Blocking sıfırlanır)
    DOM.placesGrid.appendChild(fragment);

    // Yalnızca yeni eklenen In-Feed yuvasını doldur (filtre değişiminde diğer reklamlar yenilenmez)
    if (inFeedAdEl) {
        const slotEl = inFeedAdEl;
        setTimeout(() => fillAdSlot(slotEl), ADS_CONFIG.lazyDelayMs);
    }

    // Sadece yeni eklenen kartların görsellerini yükle
    if (newImages.length > 0) {
        loadWikiImagesForCards(newImages);
    }

    // Sonsuz kaydırma (IntersectionObserver) ile kullanıcı aşağı indikçe otomatik yükle
    if (sentinelEl && "IntersectionObserver" in window) {
        _placesIntersectionObserver = new IntersectionObserver((entries) => {
            if (entries.some(e => e.isIntersecting)) {
                renderNextPlacesBatch();
            }
        }, { rootMargin: "320px 0px" });
        _placesIntersectionObserver.observe(sentinelEl);
    }
}

function updateExploreUI() {
    disconnectPlacesObserver();
    _placesRenderedCount = 0;
    DOM.globalStatsLabel.textContent = `${STATE.filteredPlaces.length} Mekan Bulundu`;
    
    if (STATE.filteredPlaces.length === 0) {
        DOM.placesGrid.innerHTML = `
          <div class="empty-state">
            <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
            <p>Seçilen kritere uygun mekan bulunamadı.</p>
          </div>`;
        return;
    }

    // Grid'i temizle ve ilk 24 popüler mekanı DocumentFragment ile anında bas
    DOM.placesGrid.innerHTML = "";
    renderNextPlacesBatch();
}

// ================= FOTOĞRAF SİSTEMİ =================
// Kategori başlı Unsplash arama terimleri (API key gerekmez, CDN kaynaklı)
const CATEGORY_IMAGES = {
  'Müze':              'https://images.unsplash.com/photo-1566127992631-137a642a90f4?w=600&q=80',
  'Tarihi / Antik Kent': 'https://images.unsplash.com/photo-1603565816030-6b389eeb23cb?w=600&q=80',
  'Doğa Alanı':       'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=600&q=80',
  'Şelale':            'https://images.unsplash.com/photo-1503435824048-a799a3a84bf7?w=600&q=80',
  'Mağara':            'https://images.unsplash.com/photo-1519501025264-65ba15a82390?w=600&q=80',
  'Park / Orman':      'https://images.unsplash.com/photo-1448375240586-882707db888b?w=600&q=80',
  'Göl / Nehir':       'https://images.unsplash.com/photo-1439066615861-d1af74d74000?w=600&q=80',
  'Plaj / Koy':        'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600&q=80',
  'Kale / Hisar':      'https://images.unsplash.com/photo-1564507592333-c60657eea523?w=600&q=80',
  'Kilise / Camii':    'https://images.unsplash.com/photo-1524231757912-21f4fe3a7200?w=600&q=80',
  'Özel':              'https://images.unsplash.com/photo-1528360983277-13d401cdc186?w=600&q=80',
};
const DEFAULT_FALLBACK = 'https://images.unsplash.com/photo-1527838832700-5059252407fa?w=600&q=80';

function getCategoryFallback(kategori) {
  return CATEGORY_IMAGES[kategori] || DEFAULT_FALLBACK;
}

// ===== ÇOK KAYNAKLI GÖRSEL YÜKLEYİCİ (Önbellekli) =====

// Kategori → Unsplash kaliteli fotoğraf (son çare, ama gerçek fotoğraf)
const CATEGORY_PHOTOS = {
  'Müze':           'https://images.unsplash.com/photo-1566127992631-137a642a90f4?w=700&q=80',
  'Antik Kent':     'https://images.unsplash.com/photo-1603565816030-6b389eeb23cb?w=700&q=80',
  'Kale / Hisar':   'https://images.unsplash.com/photo-1564507592333-c60657eea523?w=700&q=80',
  'Şelale':         'https://images.unsplash.com/photo-1503435824048-a799a3a84bf7?w=700&q=80',
  'Mağara':         'https://images.unsplash.com/photo-1519501025264-65ba15a82390?w=700&q=80',
  'Dağ Zirvesi':    'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=700&q=80',
  'Plaj / Koy':     'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=700&q=80',
  'Doğa Parkı':     'https://images.unsplash.com/photo-1448375240586-882707db888b?w=700&q=80',
  'Tarihi Camii':   'https://images.unsplash.com/photo-1524231757912-21f4fe3a7200?w=700&q=80',
  'Tarihi Kilise':  'https://images.unsplash.com/photo-1548625149-720754863e5c?w=700&q=80',
  'Seyir Noktası':  'https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=700&q=80',
  'Turistik Alan':  'https://images.unsplash.com/photo-1527838832700-5059252407fa?w=700&q=80',
  'Kaplıca':        'https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=700&q=80',
  'Anıt':           'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=700&q=80',
  'Park':           'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=700&q=80',
  'Sanat Eseri':    'https://images.unsplash.com/photo-1547891654-e66ed7ebb968?w=700&q=80',
};
const PHOTO_CACHE_TTL = 86400000; // 24 saat (ms)
const PHOTO_CACHE_KEY = 'nereye_photo_cache_v4_verified';
try { localStorage.removeItem('nereye_photo_cache_v3'); } catch {}

function getPhotoCache() {
    try { return JSON.parse(localStorage.getItem(PHOTO_CACHE_KEY) || '{}'); } catch { return {}; }
}
function setPhotoCache(cache) {
    try { localStorage.setItem(PHOTO_CACHE_KEY, JSON.stringify(cache)); } catch {}
}
function getCachedPhoto(key) {
    const cache = getPhotoCache();
    const entry = cache[key];
    if (!entry) return null;
    if (Date.now() - entry.ts > PHOTO_CACHE_TTL) return null; // Süresi dolmuş
    return entry.url;
}
function cachePhoto(key, url) {
    const cache = getPhotoCache();
    cache[key] = { url, ts: Date.now() };
    // Önbellek 500'den büyükse en eskiyi sil
    const keys = Object.keys(cache);
    if (keys.length > 500) {
        const oldest = keys.sort((a,b) => cache[a].ts - cache[b].ts)[0];
        delete cache[oldest];
    }
    setPhotoCache(cache);
}

async function loadWikiImagesForCards(targetImages = null) {
    const images = Array.isArray(targetImages)
        ? targetImages
        : Array.from(DOM.placesGrid.querySelectorAll('img[data-wiki]:not([data-loaded="true"])'));

    const markLoaded = (img) => {
        img.classList.add('loaded');
        img.closest('.card-image-wrapper')?.classList.add('img-loaded');
    };
    const hideNoPhoto = (img) => {
        const wrapper = img.closest('.card-image-wrapper');
        if (wrapper) {
            wrapper.style.display = 'none';
            wrapper.closest('.place-card')?.classList.add('no-photo');
        }
    };
    const setImage = (img, src, cacheKey) => {
        img.onload = () => markLoaded(img);
        img.onerror = () => hideNoPhoto(img);
        img.src = src;
        img.dataset.loaded = 'true';
        if (cacheKey && !src.includes('unsplash')) cachePhoto(cacheKey, src);
    };

    // Wikimedia Commons FilePath URL
    const commonsUrl = (fn) =>
        `https://commons.wikimedia.org/wiki/Special:FilePath/${encodeURIComponent(fn.replace(/ /g,'_'))}?width=700`;

    const loadOne = async (img) => {
        if (img.dataset.loaded === 'true') return;

        // ── HAZIR VERİ: build_images.py ile doğrulanmış fotoğraf ──
        // (Wikidata/Wikipedia bağlantısı veya koordinat+isim eşleşmesi)
        if (img.dataset.img) { setImage(img, sizedImageUrl(img.dataset.img, 500), null); return; }
        // Hazır veride fotoğraf yoksa: yanlış fotoğraf yerine fotoğrafsız kart
        if (img.dataset.static) { hideNoPhoto(img); return; }

        // ── YEDEK (canlı Overpass verisi): sadece mekana BAĞLI kaynaklar ──
        const wikiRef     = img.dataset.wiki2 || '';
        const wikidataId  = img.dataset.wikidata;
        const osmImageUrl = img.dataset.osmImage;
        const cacheKey    = `photo_${wikidataId || wikiRef || img.dataset.wiki}`;

        const cached = getCachedPhoto(cacheKey);
        if (cached) { setImage(img, cached, null); return; }

        // OSM image= (sadece Wikimedia dosyası)
        if (/^https:\/\/upload\.wikimedia\.org\/.+\.(jpe?g|png|webp)$/i.test(osmImageUrl || '')) {
            setImage(img, osmImageUrl, cacheKey); return;
        }

        // Wikidata P18 (mekanın kendi kaydı)
        if (wikidataId?.startsWith('Q')) {
            try {
                const res = await fetch(
                    `https://www.wikidata.org/w/api.php?action=wbgetclaims&entity=${wikidataId}&property=P18&format=json&origin=*`
                );
                if (res.ok) {
                    const d = await res.json();
                    const fn = d?.claims?.P18?.[0]?.mainsnak?.datavalue?.value;
                    if (fn && !/\.svg$|map|harita|flag|logo/i.test(fn)) { setImage(img, commonsUrl(fn), cacheKey); return; }
                }
            } catch {}
        }

        // OSM'de bağlı Wikipedia makalesi (ör. "tr:Sümela Manastırı")
        const m = wikiRef.match(/^([a-z]{2,3}):(.+)$/);
        if (m) {
            try {
                const res = await fetch(`https://${m[1]}.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(m[2])}`);
                if (res.ok) {
                    const d = await res.json();
                    if (d.type !== 'disambiguation' && d.thumbnail?.source) {
                        setImage(img, d.thumbnail.source, cacheKey); return;
                    }
                }
            } catch {}
        }

        // Doğrulanmış kaynak yok → fotoğrafsız kart (isimle tahmin / stok fotoğraf YOK)
        hideNoPhoto(img);
    };

    await Promise.allSettled(images.map(loadOne));
}



// ================= LEAFLET MAP =================
function cleanupLeafletLayers() {
    if (STATE.markerCluster) {
        STATE.markerCluster.clearLayers();
    }
    if (STATE.leafletGeoLayer) {
        STATE.leafletGeoLayer.eachLayer((layer) => {
            if (layer.unbindTooltip) layer.unbindTooltip();
            if (layer.off) layer.off();
        });
        if (STATE.leafletMap) {
            STATE.leafletMap.removeLayer(STATE.leafletGeoLayer);
        }
        STATE.leafletGeoLayer = null;
    }
}

async function initOrUpdateLeafletMap() {
    if (!STATE.leafletMap) {
        STATE.leafletCanvasRenderer = L.canvas({ padding: 0.5 });

        STATE.leafletMap = L.map('leafletMap', {
            preferCanvas: true,
            renderer: STATE.leafletCanvasRenderer,
            fadeAnimation: false,
            markerZoomAnimation: true,
            zoomSnap: 0.5
        }).setView([39.0, 35.0], 6);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19,
            updateWhenIdle: false,
            updateWhenZooming: false,
            keepBuffer: 2
        }).addTo(STATE.leafletMap);

        if (typeof L.markerClusterGroup === 'function') {
            STATE.markerCluster = L.markerClusterGroup({
                chunkedLoading: true,
                chunkInterval: 100,
                chunkDelay: 20,
                removeOutsideVisibleBounds: true,
                showCoverageOnHover: false,
                animate: false,
                animateAddingMarkers: false,
                maxClusterRadius: 42
            });
        } else {
            STATE.markerCluster = L.layerGroup();
        }
        STATE.leafletMap.addLayer(STATE.markerCluster);

        // Throttled moveend / zoomend eventleri
        STATE.leafletMap.on('moveend zoomend', throttle(() => {
            if (STATE.leafletMap) {
                // Görünür sınır dışındaki ağır popup/tooltip kalıntılarını temiz tut
            }
        }, 120));
    }
    
    DOM.mapTitle.textContent = `${STATE.selectedCity} Keşif Haritası`;

    // Seçili ilin ilçe sınırları henüz bellekte yoksa yükle
    if (STATE.selectedCity && !DISTRICT_GEO_CACHE[STATE.selectedCity]) {
        await loadDistrictGeo(STATE.selectedCity);
    }
    
    // Görünüm geçişi tamamlandıktan sonra boyutu düzelt ve sınırları + pinleri TEK SEFERDE çiz
    requestAnimationFrame(() => {
        if (!STATE.leafletMap) return;
        STATE.leafletMap.invalidateSize({ animate: false });
        renderMapMarkers();
        setTimeout(() => {
            if (STATE.leafletMap) STATE.leafletMap.invalidateSize({ animate: false });
        }, 250);
    });
}

function renderMapMarkers() {
    if (!STATE.leafletMap || !STATE.markerCluster) return;

    // Eski katmanları ve event listener'ları bellek sızıntısı bırakmadan temizle
    cleanupLeafletLayers();

    const bounds = L.latLngBounds();

    // Seçili ilin ilçe sınırlarını Canvas renderer üzerinde çiz (DOM SVG yükünü sıfırlar)
    const districtGeo = STATE.selectedCity ? DISTRICT_GEO_CACHE[STATE.selectedCity] : null;
    if (districtGeo && districtGeo.features && districtGeo.features.length > 0) {
        STATE.leafletGeoLayer = L.geoJSON(districtGeo, {
            renderer: STATE.leafletCanvasRenderer || undefined,
            style: (feature) => {
                const isSelectedDist = STATE.selectedDistrict && feature.properties?.name_tr === STATE.selectedDistrict;
                return {
                    color: '#5C4033',
                    weight: isSelectedDist ? 3 : 1.8,
                    fillColor: isSelectedDist ? '#a83228' : '#d8be92',
                    fillOpacity: isSelectedDist ? 0.28 : 0.16,
                    dashArray: isSelectedDist ? '' : '4, 4'
                };
            },
            onEachFeature: (feature, layer) => {
                if (feature.properties && feature.properties.name_tr) {
                    layer.bindTooltip(`İlçe: ${feature.properties.name_tr}`, { sticky: false, direction: 'center' });
                }
            }
        }).addTo(STATE.leafletMap);

        const geoBounds = STATE.leafletGeoLayer.getBounds();
        if (geoBounds && geoBounds.isValid()) {
            bounds.extend(geoBounds);
        }
    }
    
    let toRender = STATE.places || [];
    if (DOM.mapCategoryFilter.value) {
        toRender = toRender.filter(p => p.kategori === DOM.mapCategoryFilter.value);
    }

    // Pinleri tek tek addLayer ile değil, chunkedLoading'in çalışması için toplu dizi (addLayers) ile yükle!
    const markersBatch = [];

    for (let i = 0; i < toRender.length; i++) {
        const place = toRender[i];
        if (!place.lat || !place.lon) continue;

        const icon = L.divIcon({
            className: 'vintage-map-pin',
            html: `<div class="vintage-pin-seal" title="${escapeHtml(place.ad)}"><span class="vintage-pin-core">✦</span></div>`,
            iconSize: [28, 28],
            iconAnchor: [14, 14],
            popupAnchor: [0, -14]
        });

        const marker = L.marker([place.lat, place.lon], { icon });

        // Popup HTML'ini yalnızca kullanıcı tıkladığında (lazy) üret (binlerce string birleştirmeyi önler)
        marker.bindPopup(() => {
            const inRoute = isPlaceInRoute(place.id);
            return `
                <div style="font-family: 'Lora', Georgia, serif; padding:6px; min-width:210px;">
                    ${safeUrl(place.img) ? `<img src="${safeUrl(sizedImageUrl(place.img, 330))}" alt="${escapeHtml(place.ad)}" style="width:100%; height:auto; max-height:140px; object-fit:cover; margin-bottom:6px; border:1px solid #8B5A2B;" loading="lazy" onerror="this.remove()"/>` : ''}
                    <h4 style="margin:0 0 4px 0; font-size:15px; font-family:'Playfair Display', serif; color:#3b281e;">${escapeHtml(place.ad)}</h4>
                    <p style="margin:0 0 8px 0; color:#6e523e; font-size:12px;">${escapeHtml(place.kategori)}${place.ilce ? ' • ' + escapeHtml(place.ilce) : ''}</p>
                    <div style="display:flex; gap:4px; flex-wrap:wrap;">
                        <a href="${getPlaceHash(place)}" style="display:inline-block; padding:5px 9px; background:#a83228; color:#fdf8ee; border-radius:3px; text-decoration:none; font-size:12px; font-weight:bold;">Detay</a>
                        <button type="button" data-route-id="${safeId(place.id)}" onclick="window.handleCardRouteClick('${safeId(place.id)}')" style="padding:5px 9px; background:${inRoute ? '#8B5A2B' : '#2d5a3c'}; color:#fdf8ee; border:none; border-radius:3px; font-size:12px; font-weight:bold; cursor:pointer;">
                            ${inRoute ? '✓ Günlükte' : '+ Rotama Ekle'}
                        </button>
                        <a href="https://www.google.com/maps/dir/?api=1&destination=${place.lat},${place.lon}" target="_blank" style="display:inline-block; padding:5px 9px; background:#5C4033; color:#fdf8ee; border-radius:3px; text-decoration:none; font-size:12px; font-weight:bold;">Yol Tarifi</a>
                    </div>
                </div>
            `;
        });

        markersBatch.push(marker);
        bounds.extend([place.lat, place.lon]);
    }

    if (markersBatch.length > 0) {
        if (typeof STATE.markerCluster.addLayers === 'function') {
            STATE.markerCluster.addLayers(markersBatch);
        } else {
            markersBatch.forEach(m => STATE.markerCluster.addLayer(m));
        }
    }

    if (bounds.isValid()) {
        STATE.leafletMap.fitBounds(bounds, { padding: [40, 40], animate: false });
    }
}


// ================= PLACE DETAILS VIEW =================
function getCityNameBySlug(slug) {
  if (!slug || !STATE.geoData) return "";
  const f = STATE.geoData.features.find(x => x.properties.slug === slug);
  return f ? f.properties.name_tr : "";
}

function findPlaceInMemory(id) {
  const direct = (STATE.places || []).find(p => p.id === id)
    || (STATE.nearbyPlaces || []).find(p => p.id === id);
  if (direct) return direct;
  for (const list of Object.values(CITY_CACHE)) {
    const hit = Array.isArray(list) && list.find(p => p.id === id);
    if (hit) return hit;
  }
  return null;
}

/**
 * Doğrudan açılan (paylaşılan) mekan linkleri için mekanı STATİK veriden bulur:
 * 1) RAM önbelleği  2) linkteki il slug'ı  3) Seyahat Günlüğü kaydındaki il
 * 4) Eski formattaki linkler için illeri küçük paketlerle tarama  5) Son çare: Overpass
 */
async function resolvePlaceForDetail(id, slug) {
  let place = findPlaceInMemory(id);
  if (place) return place;

  const tryCity = async (cityName) => {
    if (!cityName) return null;
    const list = await loadStaticCityData(cityName);
    return Array.isArray(list) ? (list.find(p => p.id === id) || null) : null;
  };

  place = await tryCity(getCityNameBySlug(slug));
  if (place) return place;

  const saved = getSavedRoute().find(item => item.id === id);
  if (saved && saved.il) {
    place = await tryCity(saved.il);
    if (place) return place;
  }

  if (STATE.geoData) {
    const cities = STATE.geoData.features.map(f => f.properties.name_tr);
    for (let i = 0; i < cities.length; i += 6) {
      const found = (await Promise.all(cities.slice(i, i + 6).map(tryCity))).find(Boolean);
      if (found) return found;
    }
  }

  return /^(node|way|relation):\d+$/.test(id) ? tryFetchSinglePlace(id) : null;
}

let _detailRequestToken = 0;

async function renderPlaceDetails(id, slug = "") {
    const token = ++_detailRequestToken;
    DOM.detailTitle.textContent = "Yükleniyor...";
    DOM.detailCategory.textContent = "";
    DOM.detailLocation.textContent = "";
    DOM.detailDescription.textContent = "";
    DOM.detailTags.innerHTML = "";
    DOM.detailImageWrapper.innerHTML = "";
    DOM.detailImageWrapper.style.display = "";
    DOM.detailImageWrapper.classList.add("skeleton-loading");
    DOM.btnWikipedia.classList.add("hidden");

    let place = findPlaceInMemory(id);
    if (!place) {
        showLoader("Mekan bilgisi getiriliyor...");
        try {
            place = await resolvePlaceForDetail(id, slug);
        } finally {
            hideLoader();
        }
    }
    if (token !== _detailRequestToken) return; // Kullanıcı bu arada başka bir mekana geçti

    if (!place) {
        DOM.detailImageWrapper.classList.remove("skeleton-loading");
        DOM.detailImageWrapper.style.display = "none";
        DOM.detailTitle.textContent = "Mekan Bulunamadı.";
        DOM.detailDescription.textContent = "Bu bağlantıdaki mekan artık listemizde yer almıyor olabilir. Haritadan yeni bir durak seçebilirsiniz.";
        return;
    }

    const cityLabel = place.il || STATE.selectedCity || "";
    DOM.detailTitle.textContent = place.ad;
    DOM.detailCategory.textContent = place.kategori || "";
    DOM.detailLocation.textContent = `${place.ilce ? place.ilce + ', ' : ''}${cityLabel}`;
    place.tags = place.tags || {};
    document.title = `${place.ad} (${cityLabel}) | Gezi Atlası`;

    const chips = [place.kategori, place.ilce ? `${place.ilce} ilçesi` : '', cityLabel].filter(Boolean);
    if (place.wp || place.tags.wikipedia || place.tags.wikidata || place.wikidata) chips.push('Wikipedia kaydı var');
    chips.forEach(text => {
        const div = document.createElement("div");
        div.className = "detail-tag";
        div.textContent = text;
        DOM.detailTags.appendChild(div);
    });

    DOM.btnDirections.href = `https://www.google.com/maps/dir/?api=1&destination=${Number(place.lat)},${Number(place.lon)}`;
    DOM.btnDirections.rel = "noopener";

    STATE.currentDetailPlace = place;
    syncDetailRouteButton();

    const hideImage = () => {
        DOM.detailImageWrapper.classList.remove("skeleton-loading");
        DOM.detailImageWrapper.innerHTML = '';
        DOM.detailImageWrapper.style.display = 'none';
    };
    const showImage = (src) => {
        if (!/^https:\/\//i.test(String(src || ""))) return;
        DOM.detailImageWrapper.classList.remove("skeleton-loading");
        DOM.detailImageWrapper.style.display = '';
        const img = document.createElement("img");
        img.src = src;
        img.alt = place.ad;
        img.decoding = "async";
        img.style.cssText = "width:100%; height:100%; object-fit:cover;";
        img.onerror = hideImage;
        DOM.detailImageWrapper.replaceChildren(img);
    };
    if (place.img) showImage(sizedImageUrl(place.img, 960));

    DOM.detailDescription.textContent = "Bu mekan için Wikipedia açıklaması bulunmuyor.";
    const ref = String(place.wp || place.tags.wikipedia || '');
    const m = ref.match(/^([a-z]{2,3}):(.+)$/);
    if (m) {
        DOM.detailDescription.textContent = "Wikipedia'dan özet getiriliyor...";
        try {
            const res = await fetch(`https://${m[1]}.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(m[2])}`);
            if (token !== _detailRequestToken) return;
            if (res.ok) {
                const data = await res.json();
                if (token !== _detailRequestToken) return;
                if (data.type !== 'disambiguation') {
                    DOM.detailDescription.textContent = data.extract || "Bu mekan için Wikipedia açıklaması bulunmuyor.";
                    if (data.content_urls && data.content_urls.desktop) {
                        DOM.btnWikipedia.classList.remove("hidden");
                        DOM.btnWikipedia.href = data.content_urls.desktop.page;
                        DOM.btnWikipedia.rel = "noopener";
                    }
                    if (!place.img && data.thumbnail) showImage(data.thumbnail.source);
                } else {
                    DOM.detailDescription.textContent = "Bu mekan için Wikipedia açıklaması bulunmuyor.";
                }
            } else {
                DOM.detailDescription.textContent = "Bu mekan için Wikipedia açıklaması bulunmuyor.";
            }
        } catch (e) {
            if (token === _detailRequestToken) DOM.detailDescription.textContent = "Wikipedia özeti şu an alınamadı.";
        }
    }
    if (token === _detailRequestToken && !DOM.detailImageWrapper.querySelector('img')) hideImage();
}

async function tryFetchSinglePlace(fullId) {
    const parts = fullId.split(":");
    const query = `[out:json][timeout:15]; ${parts[0]}(${parts[1]}); out center tags;`;
    try {
        const r = await fetch("https://overpass-api.de/api/interpreter", {
            method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: "data=" + encodeURIComponent(query)
        });
        const d = await r.json();
        if (d.elements && d.elements.length > 0) {
            const el = d.elements[0];
            return {
                id: fullId,
                ad: el.tags["name:tr"] || el.tags.name || "Bilinmiyor",
                lat: el.lat || (el.center && el.center.lat) || 0,
                lon: el.lon || (el.center && el.center.lon) || 0,
                kategori: "Özel",
                tags: el.tags,
                il: el.tags.il || el.tags["addr:province"] || ""
            };
        }
    } catch(e) {}
    return null;
}


// ================= YENİ ÖZELLİK 1: AKILLI ROTA PLANLAYICI (SEYAHAT GÜNLÜĞÜ) =================
const ROUTE_STORAGE_KEY = "savedRoute";

function getSavedRoute() {
    try {
        const raw = localStorage.getItem(ROUTE_STORAGE_KEY);
        const parsed = raw ? JSON.parse(raw) : [];
        return Array.isArray(parsed) ? parsed : [];
    } catch {
        return [];
    }
}

function saveRoute(routeList) {
    try {
        localStorage.setItem(ROUTE_STORAGE_KEY, JSON.stringify(routeList));
    } catch {}
    renderRouteJournal();
    syncRouteButtonsInDOM();
    syncDetailRouteButton();
}

function isPlaceInRoute(placeId) {
    return getSavedRoute().some(item => item.id === placeId);
}

function findPlaceById(placeId) {
    return (
        (STATE.places || []).find(p => p.id === placeId) ||
        (STATE.nearbyPlaces || []).find(p => p.id === placeId) ||
        (STATE.currentDetailPlace && STATE.currentDetailPlace.id === placeId ? STATE.currentDetailPlace : null)
    );
}

function toggleRoutePlace(place) {
    if (!place || !place.id) return;
    const current = getSavedRoute();
    const exists = current.some(item => item.id === place.id);
    let next;
    if (exists) {
        next = current.filter(item => item.id !== place.id);
    } else {
        next = [
            ...current,
            {
                id: place.id,
                ad: place.ad,
                il: place.il || STATE.selectedCity || "",
                ilce: place.ilce || "",
                lat: place.lat,
                lon: place.lon,
                kategori: place.kategori || "",
                img: place.img || ""
            }
        ];
    }
    saveRoute(next);
}

window.handleCardRouteClick = function(placeId) {
    const place = findPlaceById(placeId);
    if (place) {
        toggleRoutePlace(place);
    } else if (isPlaceInRoute(placeId)) {
        removeFromRoute(placeId);
    }
};

function removeFromRoute(placeId) {
    const next = getSavedRoute().filter(item => item.id !== placeId);
    saveRoute(next);
}

function clearRoute() {
    saveRoute([]);
}

function openRouteJournal() {
    if (DOM.routeJournalPanel) DOM.routeJournalPanel.classList.add("open");
    if (DOM.routeJournalBackdrop) DOM.routeJournalBackdrop.classList.remove("hidden");
}

function closeRouteJournal() {
    if (DOM.routeJournalPanel) DOM.routeJournalPanel.classList.remove("open");
    if (DOM.routeJournalBackdrop) DOM.routeJournalBackdrop.classList.add("hidden");
}

function syncRouteButtonsInDOM() {
    const buttons = document.querySelectorAll("[data-route-id]");
    buttons.forEach(btn => {
        const id = btn.getAttribute("data-route-id");
        const added = isPlaceInRoute(id);
        if (btn.classList.contains("card-route-btn")) {
            btn.classList.toggle("added", added);
            btn.textContent = added ? "✓ Günlükte (Çıkar)" : "📜 Rotama Ekle";
        } else {
            btn.style.background = added ? "#8B5A2B" : "#2d5a3c";
            btn.textContent = added ? "✓ Günlükte" : "+ Rotama Ekle";
        }
    });
}

function syncDetailRouteButton() {
    if (!DOM.btnAddToRouteDetail || !STATE.currentDetailPlace) return;
    const added = isPlaceInRoute(STATE.currentDetailPlace.id);
    DOM.btnAddToRouteDetail.classList.toggle("in-route", added);
    DOM.btnAddToRouteDetail.textContent = added ? "✓ Seyahat Günlüğünde (Çıkar)" : "📜 Rotama Ekle";
}

function renderRouteJournal() {
    const route = getSavedRoute();
    if (DOM.routeCountBadge) {
        DOM.routeCountBadge.textContent = String(route.length);
    }

    if (!DOM.routeJournalList) return;

    if (route.length === 0) {
        DOM.routeJournalList.innerHTML = `
            <div class="journal-empty">
                <p>Henüz seyahat günlüğünüze bir durak eklemediniz.</p>
                <small>Mekan kartlarındaki veya detay sayfasındaki "📜 Rotama Ekle" düğmesini kullanabilirsiniz.</small>
            </div>
        `;
        if (DOM.btnStartRoute) DOM.btnStartRoute.classList.add("disabled");
        if (DOM.btnClearRoute) DOM.btnClearRoute.classList.add("hidden");
        return;
    }

    if (DOM.btnStartRoute) DOM.btnStartRoute.classList.remove("disabled");
    if (DOM.btnClearRoute) DOM.btnClearRoute.classList.remove("hidden");

    DOM.routeJournalList.innerHTML = route.map((item, idx) => `
        <div class="journal-item">
            <span class="journal-step-num">${idx + 1}</span>
            <div class="journal-item-info" onclick="window.location.hash='${getPlaceHash(item)}'">
                <div class="journal-item-title">${escapeHtml(item.ad)}</div>
                <div class="journal-item-sub">${item.ilce ? escapeHtml(item.ilce) + ', ' : ''}${escapeHtml(item.il)} • ${escapeHtml(item.kategori)}</div>
            </div>
            <button type="button" class="btn-journal-remove" title="Rotadan Çıkar" onclick="window.removeRouteStop('${safeId(item.id)}')">✕</button>
        </div>
    `).join("");
}

window.removeRouteStop = function(placeId) {
    removeFromRoute(placeId);
};

function startGoogleMapsRoute() {
    const route = getSavedRoute().filter(item => item.lat && item.lon);
    if (route.length === 0) return;
    const coordsPath = route.map(item => `${item.lat},${item.lon}`).join("/");
    const url = `https://www.google.com/maps/dir/${coordsPath}`;
    window.open(url, "_blank", "noopener");
}


// ================= YENİ ÖZELLİK 2: YAKINIMDAKİLERİ BUL (GEOLOCATION & HAVERSINE) =================
function calculateHaversineKm(lat1, lon1, lat2, lon2) {
    const R = 6371; // Dünya yarıçapı (km)
    const toRad = (deg) => (deg * Math.PI) / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a =
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

// Kullanıcının konumuna en yakın illeri GeoJSON üzerinden bulup statik JSON verilerini getirir
async function getCandidatePlacesForLocation(userLat, userLon) {
    // Eğer sadece seçili il varsa bile sınır bölgeleri için en yakın 4 ili de kontrol edelim
    if (!STATE.geoData || !Array.isArray(STATE.geoData.features)) {
        return STATE.places || [];
    }

    const scoredProvinces = STATE.geoData.features.map(f => {
        const c = d3.geoCentroid(f); // [lon, lat]
        const dist = calculateHaversineKm(userLat, userLon, c[1], c[0]);
        return { name: f.properties.name_tr, dist };
    }).sort((a, b) => a.dist - b.dist);

    const closestProvinces = scoredProvinces.slice(0, 4).map(p => p.name);
    if (STATE.selectedCity && !closestProvinces.includes(STATE.selectedCity)) {
        closestProvinces.push(STATE.selectedCity);
    }

    const lists = await Promise.all(
        closestProvinces.map(async (cityName) => {
            if (CITY_CACHE[cityName]) return CITY_CACHE[cityName];
            const data = await loadStaticCityData(cityName);
            if (data) CITY_CACHE[cityName] = data;
            return data || [];
        })
    );

    const merged = [];
    const seenIds = new Set();
    lists.flat().forEach(p => {
        if (p && p.id && !seenIds.has(p.id)) {
            seenIds.add(p.id);
            merged.push(p);
        }
    });
    return merged;
}

function findNearbyPlaces() {
    if (!navigator.geolocation) {
        alert("Tarayıcınız konum özelliğini (Geolocation) desteklemiyor.");
        return;
    }

    showLoader("🧭 Pusula konumunuzu hesaplıyor...");
    navigator.geolocation.getCurrentPosition(
        async (pos) => {
            try {
                const userLat = pos.coords.latitude;
                const userLon = pos.coords.longitude;

                const pool = await getCandidatePlacesForLocation(userLat, userLon);
                const withDistance = pool
                    .filter(p => p.lat && p.lon)
                    .map(p => ({
                        ...p,
                        distanceKm: calculateHaversineKm(userLat, userLon, p.lat, p.lon)
                    }))
                    .sort((a, b) => a.distanceKm - b.distanceKm)
                    .slice(0, 10);

                STATE.nearbyPlaces = withDistance;
                renderNearbyPlaces(withDistance);
            } finally {
                hideLoader();
            }
        },
        (err) => {
            hideLoader();
            let msg = "Konum bilgisi alınamadı. Lütfen tarayıcıdan konum izni verdiğinizden emin olun.";
            if (err && err.code === 1) msg = "Konum izni reddedildi. Yakınınızdaki mekanları görmek için konum izni vermelisiniz.";
            alert(msg);
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
}

function renderNearbyPlaces(places) {
    if (!DOM.nearbySection || !DOM.nearbyGrid) return;
    DOM.nearbySection.classList.remove("hidden");

    if (!places || places.length === 0) {
        DOM.nearbyGrid.innerHTML = `<div class="empty-state"><p>Yakınınızda kayıtlı mekan bulunamadı.</p></div>`;
        return;
    }

    DOM.nearbyGrid.innerHTML = places.map(place => {
        const inRoute = isPlaceInRoute(place.id);
        const distLabel = `${place.distanceKm.toFixed(1)} km`;
        return `
        <div class="place-card glass-panel" onclick="window.location.hash='${getPlaceHash(place)}'">
            <div class="card-image-wrapper">
                <span class="distance-stamp">📍 ${distLabel}</span>
                ${safeUrl(place.img) ? `<img class="card-image loaded" src="${safeUrl(sizedImageUrl(place.img, 500))}" alt="${escapeHtml(place.ad)}" loading="lazy" decoding="async" onerror="this.closest('.card-image-wrapper').classList.add('img-loaded')">` : ''}
            </div>
            <div class="card-content">
                <span class="card-category">${escapeHtml(place.kategori)}</span>
                <h3 class="card-title">${escapeHtml(place.ad)}</h3>
                <div class="card-location">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-color)" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                    ${place.ilce ? escapeHtml(place.ilce) + ', ' : ''}${escapeHtml(place.il)}
                </div>
                <div class="card-actions-row">
                    <button type="button"
                            class="card-route-btn ${inRoute ? 'added' : ''}"
                            data-route-id="${safeId(place.id)}"
                            onclick="event.stopPropagation(); window.handleCardRouteClick('${safeId(place.id)}')">
                        ${inRoute ? '✓ Günlükte (Çıkar)' : '📜 Rotama Ekle'}
                    </button>
                </div>
            </div>
        </div>
        `;
    }).join("");

    DOM.nearbySection.scrollIntoView({ behavior: "smooth", block: "start" });
}


// ================= EVENT LISTENERS =================
function setupEventListeners() {
    DOM.citySelect.addEventListener('change', (e) => selectCity(e.target.value));
    if (DOM.btnBackToTurkeyMap) {
        DOM.btnBackToTurkeyMap.addEventListener('click', () => selectCity(''));
    }
    
    // Filter bindings (Arama input'una Debounce eklendi — her tuş vuruşunda DOM yeniden çizimini önler)
    DOM.searchInput.addEventListener('input', debounce(filterPlaces, 180));
    DOM.categoryFilter.addEventListener('change', filterPlaces);
    DOM.districtSelect.addEventListener('change', () => {
        STATE.selectedDistrict = DOM.districtSelect.value;
        filterPlaces();
    });
    
    // Map Filter bindings
    DOM.mapCategoryFilter.addEventListener("change", renderMapMarkers);

    // Pencere boyutu değiştiğinde (resize) haritaları Debounce ile yeniden boyutlandır
    window.addEventListener('resize', debounce(() => {
        if (STATE.view === 'explore') {
            if (STATE.selectedCity) {
                const districtGeo = DISTRICT_GEO_CACHE[STATE.selectedCity] || null;
                drawProvinceMap(STATE.selectedCity, districtGeo);
            } else if (STATE.geoData) {
                drawD3Map();
            }
        } else if (STATE.view === 'map' && STATE.leafletMap) {
            STATE.leafletMap.invalidateSize({ animate: false });
        }
    }, 220));

    // Back buttons & Map navigation button
    // Görünüm değişimi YALNIZCA router (hashchange) üzerinden yapılır; aksi halde
    // showView + initOrUpdateLeafletMap iki kez çalışıyordu.
    const navigateTo = (hash) => {
        if (window.location.hash === hash) handleRoute();
        else window.location.hash = hash;
    };
    if (DOM.btnGoToMap) {
        DOM.btnGoToMap.addEventListener("click", (e) => {
            e.preventDefault();
            if (!STATE.selectedCity) return;
            navigateTo('#map');
        });
    }
    const navMapLink = document.querySelector('.nav-link[data-target="map"]');
    if (navMapLink) {
        navMapLink.addEventListener("click", (e) => {
            e.preventDefault();
            if (!STATE.selectedCity) {
                navigateTo('#explore');
                if (DOM.mapBoxTitle) {
                    DOM.mapBoxTitle.textContent = "🗺️ Tam ekran harita için önce bir il seçin";
                    setTimeout(() => {
                        if (!STATE.selectedCity && DOM.mapBoxTitle) DOM.mapBoxTitle.textContent = "🗺️ Katlanmış Anadolu Yol Haritası";
                    }, 3500);
                }
                return;
            }
            navigateTo('#map');
        });
    }
    DOM.btnBackFromMap.addEventListener("click", () => navigateTo('#explore'));
    DOM.btnBackFromPlace.addEventListener("click", () => navigateTo('#explore'));

    // Seyahat Günlüğü (Route Journal) bindings
    if (DOM.btnToggleJournal) DOM.btnToggleJournal.addEventListener("click", openRouteJournal);
    if (DOM.btnCloseJournal) DOM.btnCloseJournal.addEventListener("click", closeRouteJournal);
    if (DOM.routeJournalBackdrop) DOM.routeJournalBackdrop.addEventListener("click", closeRouteJournal);
    if (DOM.btnStartRoute) DOM.btnStartRoute.addEventListener("click", startGoogleMapsRoute);
    if (DOM.btnClearRoute) DOM.btnClearRoute.addEventListener("click", clearRoute);
    if (DOM.btnAddToRouteDetail) {
        DOM.btnAddToRouteDetail.addEventListener("click", () => {
            if (STATE.currentDetailPlace) toggleRoutePlace(STATE.currentDetailPlace);
        });
    }

    if (DOM.btnShowFood) DOM.btnShowFood.addEventListener("click", toggleFoodList);

    // Yakınımdakileri Bul (Geolocation & Haversine) bindings
    if (DOM.btnFindNearby) DOM.btnFindNearby.addEventListener("click", findNearbyPlaces);
    if (DOM.btnCloseNearby) {
        DOM.btnCloseNearby.addEventListener("click", () => {
            if (DOM.nearbySection) DOM.nearbySection.classList.add("hidden");
        });
    }

    // Theme logic (Vintage Parşömen varsayılan tema)
    const THEME_KEY = "nereye_vintage_theme_v5";
    DOM.themeBtn.addEventListener("click", () => {
        const isDark = document.body.classList.contains("theme-dark");
        if (isDark) {
            document.body.classList.remove("theme-dark");
            document.body.classList.add("theme-light");
            localStorage.setItem(THEME_KEY, "light");
            document.querySelector(".icon-moon").classList.remove("hidden");
            document.querySelector(".icon-sun").classList.add("hidden");
        } else {
            document.body.classList.add("theme-dark");
            document.body.classList.remove("theme-light");
            localStorage.setItem(THEME_KEY, "dark");
            document.querySelector(".icon-moon").classList.add("hidden");
            document.querySelector(".icon-sun").classList.remove("hidden");
        }
    });
}

function setupTheme() {
    try { localStorage.removeItem("nereye_theme"); } catch {}
    const savedTheme = localStorage.getItem("nereye_vintage_theme_v5") || "light";
    if (savedTheme === "dark") {
        document.body.classList.add("theme-dark");
        document.body.classList.remove("theme-light");
        document.querySelector(".icon-moon").classList.add("hidden");
        document.querySelector(".icon-sun").classList.remove("hidden");
    } else {
        document.body.classList.remove("theme-dark");
        document.body.classList.add("theme-light");
        document.querySelector(".icon-moon").classList.remove("hidden");
        document.querySelector(".icon-sun").classList.add("hidden");
    }
}

// ================= INIT (BUG #1 FIX) =================
// initApp() fonksiyonu daha önce hiç tanımlanmamıştı — uygulama hiç başlamıyordu!
async function initApp() {
  // Gerçek AdSense kimliği girilene kadar "SPONSORLU" yer tutucuları gizle
  document.body.classList.toggle("ads-off", !adsAreLive());
  setupTheme();
  setupRouter();
  setupEventListeners();
  renderRouteJournal();
  await initD3Map();
  handleRoute();
}

// Start
document.addEventListener("DOMContentLoaded", initApp);
