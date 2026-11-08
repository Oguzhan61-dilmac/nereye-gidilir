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
  btnCloseNearby: document.getElementById("btnCloseNearby")
};


// ================= SPA REKLAM (ADSENSE) MİMARİSİ & LAZY LOADER =================
const ADS_CONFIG = {
  // Kendi Google AdSense yayıncı kimliğinizi buraya girin (örn. "ca-pub-1234567890123456")
  client: "ca-pub-0000000000000000",
  // Harita (D3.js / Leaflet) çizimini ve pan/zoom performansını engellememek için gecikme süresi (ms)
  lazyDelayMs: 1600,
  // Test modunda gerçek AdSense hesabı bağlanana kadar konsol hatalarını bastır
  enabled: true
};

let _adScriptLoaded = false;
let _adRefreshTimer = null;

function ensureAdSenseScriptLoaded() {
  if (_adScriptLoaded) return;
  _adScriptLoaded = true;

  // Placeholder yayıncı kimliği kullanılıyorsa harici script isteği atıp 400 hatası üretme
  if (!ADS_CONFIG.client || ADS_CONFIG.client === "ca-pub-0000000000000000") {
    return;
  }

  if (document.querySelector('script[data-vintage-adsense="true"]')) return;

  const script = document.createElement("script");
  script.async = true;
  script.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(ADS_CONFIG.client)}`;
  script.crossOrigin = "anonymous";
  script.setAttribute("data-vintage-adsense", "true");
  document.head.appendChild(script);
}

/**
 * SPA Görünümü (View) veya İçerik Değiştiğinde Reklam Yuvalarını Güvenle Yeniler
 * - Harita kapsayıcılarını (.interactive-map-box, #d3MapContainer, #leafletMap, #view-map) kesinlikle hariç tutar.
 * - Eski iframe / ins kalıntılarını temizleyip yeni <ins class="adsbygoogle"> oluşturur ve push({}) çağırır.
 */
function refreshAds(targetViewId = STATE.view) {
  if (!ADS_CONFIG.enabled) return;
  // Tam ekran harita (#map) görünümünde pan/zoom performansını korumak için reklam yükleme!
  if (targetViewId === "map") return;

  ensureAdSenseScriptLoaded();

  const activeSection = DOM.views[targetViewId] || document;
  const adSlots = activeSection.querySelectorAll(".vintage-ad-slot");

  adSlots.forEach((slotEl) => {
    // Güvenlik: Eğer yanlışlıkla harita kutusunun içine konmuşsa asla çalıştırma
    if (
      slotEl.closest(".interactive-map-box") ||
      slotEl.closest("#d3MapContainer") ||
      slotEl.closest("#leafletMap") ||
      slotEl.closest("#view-map")
    ) {
      return;
    }

    const bodyEl = slotEl.querySelector(".vintage-ad-body") || slotEl;
    const adSlotId = slotEl.getAttribute("data-ad-slot") || "1000000001";
    const adFormat = slotEl.getAttribute("data-ad-format") || "auto";

    // Eski AdSense <ins> ve iframe kalıntılarını temizle (SPA'da duplicate push hatasını önler)
    const oldInsList = bodyEl.querySelectorAll("ins.adsbygoogle, iframe");
    oldInsList.forEach((node) => node.remove());

    // Yeni temiz <ins class="adsbygoogle"> elementi oluştur
    const ins = document.createElement("ins");
    ins.className = "adsbygoogle";
    ins.style.display = "block";
    ins.setAttribute("data-ad-client", ADS_CONFIG.client);
    ins.setAttribute("data-ad-slot", adSlotId);
    ins.setAttribute("data-ad-format", adFormat);
    ins.setAttribute("data-full-width-responsive", "true");

    bodyEl.appendChild(ins);

    // Gerçek AdSense yayıncı kimliği tanımlıysa güvenli şekilde tetikle
    if (ADS_CONFIG.client && ADS_CONFIG.client !== "ca-pub-0000000000000000") {
      try {
        (window.adsbygoogle = window.adsbygoogle || []).push({});
        slotEl.classList.add("ad-requested");
      } catch (err) {
        console.warn("AdSense yenileme uyarısı:", err);
      }
    }
  });
}

/**
 * Harita çizimi ve sayfa geçiş animasyonu tamamlandıktan 1.6 sn sonra
 * tarayıcı boşta iken (requestIdleCallback) reklamları asenkron tetikler.
 */
function scheduleRefreshAds(viewId = STATE.view) {
  if (_adRefreshTimer) {
    clearTimeout(_adRefreshTimer);
    _adRefreshTimer = null;
  }
  if (viewId === "map") return;

  _adRefreshTimer = setTimeout(() => {
    _adRefreshTimer = null;
    if (typeof window.requestIdleCallback === "function") {
      window.requestIdleCallback(() => refreshAds(viewId), { timeout: 1000 });
    } else {
      requestAnimationFrame(() => refreshAds(viewId));
    }
  }, ADS_CONFIG.lazyDelayMs);
}

// ================= CORE ROUTER =================
function setupRouter() {
  window.addEventListener('hashchange', handleRoute);
}

function handleRoute() {
  const hash = window.location.hash || '#explore';
  
  // Hash Parser (#place/node:123)
  if (hash.startsWith('#place/')) {
    const id = hash.replace('#place/', '');
    showView('place');
    renderPlaceDetails(id);
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

function showView(viewId) {
  STATE.view = viewId;
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
 * D3 elementlerine hem masaüstü "click" hem de mobil "touchstart/touchend" (tap)
 * olayı bağlar. d3.zoom()'un mobilde sentetik click olayını yutmasını engeller,
 * pan/pinch-zoom hareketlerini (12px üstü sürükleme) ise bozmaz.
 */
function bindD3TapAndClick(selection, callback) {
  let touchStartX = 0;
  let touchStartY = 0;
  let touchStartTime = 0;

  selection
    .on("touchstart", function(event, d) {
      if (event.touches && event.touches.length === 1) {
        touchStartX = event.touches[0].clientX;
        touchStartY = event.touches[0].clientY;
        touchStartTime = Date.now();
      }
    }, { passive: true })
    .on("touchend", function(event, d) {
      if (!event.changedTouches || event.changedTouches.length !== 1) return;
      const dx = Math.abs(event.changedTouches[0].clientX - touchStartX);
      const dy = Math.abs(event.changedTouches[0].clientY - touchStartY);
      const dt = Date.now() - touchStartTime;
      // Parmak sürüklenmediyse (gerçek bir dokunuş/tap ise) anında seçimi tetikle
      if (dx < 14 && dy < 14 && dt < 650) {
        if (event.cancelable) event.preventDefault();
        event.stopPropagation();
        _lastTouchActionTime = Date.now();
        callback.call(this, event, d);
      }
    })
    .on("click", function(event, d) {
      // touchend az önce tetiklendiyse çift çalışmayı önle
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

function drawD3Map() {
  cleanupD3Map();
  if (DOM.mapBoxTitle) DOM.mapBoxTitle.textContent = "🗺️ Katlanmış Anadolu Yol Haritası";
  if (DOM.btnBackToTurkeyMap) DOM.btnBackToTurkeyMap.classList.add("hidden");

  if (!STATE.geoData) return;

  _d3DrawRafId = requestAnimationFrame(() => {
    _d3DrawRafId = null;
    const container = DOM.d3Container;
    hideMapCompass(container);

    let width = container.clientWidth || container.offsetWidth 
      || container.getBoundingClientRect().width 
      || (container.parentElement && container.parentElement.clientWidth)
      || 800;
    let height = container.clientHeight || container.offsetHeight
      || container.getBoundingClientRect().height
      || 420;
    if (width < 100) width = 800;
    if (height < 100) height = 420;

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
    const projection = d3.geoIdentity()
      .reflectY(true)
      .fitSize([width, height], STATE.geoData);

    const path = d3.geoPath().projection(projection);

    // Ana Zoom Katmanı (GPU katmanı olarak hızlandırıldı)
    const g = svg.append("g").attr("class", "vintage-map-root");

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

    // Zoom Davranışı — requestAnimationFrame ile 60 FPS akıcı pan/zoom
    const zoom = d3.zoom()
      .clickDistance(10)
      .tapDistance(14)
      .scaleExtent([1, 8])
      .on("zoom", (event) => {
        const t = event.transform;
        if (_d3ZoomRafId) cancelAnimationFrame(_d3ZoomRafId);
        _d3ZoomRafId = requestAnimationFrame(() => {
          _d3ZoomRafId = null;
          g.attr("transform", t);
        });
      });
    svg.call(zoom);
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

    let width = container.clientWidth || container.offsetWidth
      || container.getBoundingClientRect().width
      || (container.parentElement && container.parentElement.clientWidth)
      || 800;
    let height = container.clientHeight || container.offsetHeight
      || container.getBoundingClientRect().height
      || 420;
    if (width < 100) width = 800;
    if (height < 100) height = 420;

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
    const projection = d3.geoIdentity()
      .reflectY(true)
      .fitSize([width, height], geoToRender);

    const path = d3.geoPath().projection(projection);
    const g = svg.append("g").attr("class", "vintage-map-root");

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
              .html(`<strong>${d.ad}</strong> (${d.kategori})${d.ilce ? ` · ${d.ilce}` : ""}`);
            updateTooltipPositionRaf(tooltip, event, container);
          })
          .on("mousemove", function(event) {
            updateTooltipPositionRaf(tooltip, event, container);
          })
          .on("mouseleave", function() {
            tooltip.classed("visible", false);
          });

        bindD3TapAndClick(mergedPins, function(event, d) {
          window.location.hash = `#place/${d.id}`;
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

    // Zoom & Pan — requestAnimationFrame ile 60 FPS akıcı pan/zoom
    const zoom = d3.zoom()
      .clickDistance(10)
      .tapDistance(14)
      .scaleExtent([1, 10])
      .on("zoom", (event) => {
        const t = event.transform;
        if (_d3ZoomRafId) cancelAnimationFrame(_d3ZoomRafId);
        _d3ZoomRafId = requestAnimationFrame(() => {
          _d3ZoomRafId = null;
          g.attr("transform", t);
        });
      });
    svg.call(zoom);
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

  drawD3Map();
}

function populateSelects() {
  if (!STATE.geoData) return;
  const cities = STATE.geoData.features.map(f => f.properties.name_tr).sort((a,b) => a.localeCompare(b, 'tr'));
  
  DOM.citySelect.innerHTML = '<option value="">Türkiye Geneli (Tümü)</option>';
  cities.forEach(city => {
    DOM.citySelect.innerHTML += `<option value="${city}">${city}</option>`;
  });
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
    // Sadece o mekana ait olduğu doğrulanmış gerçek fotoğrafı olan mekanları göster
    const verified = list.filter(p => p.img && p.img.trim() !== '');
    // Eski kodla uyum için tags alanını düz alanlardan oluştur
    const mapped = verified.map(p => ({
      ...p,
      ilce: p.ilce || '',
      fromStatic: 'img' in p, // build_images.py ile işlendi mi?
      wiki: p.wiki || p.wikidata || null,
      tags: { wikipedia: p.wiki, wikidata: p.wikidata, image: p.image }
    }));
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

  runIdle(async () => {
    // 1) index.json'u önbelleğe al
    try {
      await fetchCachedJSON("./data/places/index.json");
    } catch (_) {}

    // 2) Öncelikli popüler illerin mekan + ilçe GeoJSON verilerini küçük paketler halinde RAM'e çek
    const allCities = STATE.geoData
      ? STATE.geoData.features.map(f => f.properties.name_tr)
      : priorityCities;

    const orderedQueue = [
      ...priorityCities,
      ...allCities.filter(c => !priorityCities.includes(c))
    ];

    let idx = 0;
    const prefetchNextBatch = () => {
      // Kullanıcı aktif olarak harita/il yüklemesi yapıyorsa sıradaki paketi hafif geciktir
      const batch = orderedQueue.slice(idx, idx + 3);
      idx += 3;
      if (batch.length === 0) return;

      Promise.allSettled(
        batch.map(cityName =>
          Promise.all([
            loadStaticCityData(cityName),
            loadDistrictGeo(cityName)
          ])
        )
      ).finally(() => {
        if (idx < orderedQueue.length) {
          runIdle(prefetchNextBatch, 350);
        }
      });
    };

    prefetchNextBatch();
  }, 400);
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
          <button onclick="loadCityData('${cityName}')" class="btn-primary" style="width: auto;">Tekrar Dene</button>
        </div>`;
      STATE.places = [];
      updateExploreUI();
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



// ================= UI RENDER (EXPLORE LIST) =================
function updateCategoryFilters() {
    const cats = new Set(STATE.places.map(p => p.kategori));
    let opts = '<option value="">Tüm Kategoriler</option>';
    Array.from(cats).sort().forEach(c => {
        opts += `<option value="${c}">${c}</option>`;
    });
    DOM.categoryFilter.innerHTML = opts;
    DOM.mapCategoryFilter.innerHTML = opts;
}

function updateDistrictFilter() {
    // Mekanlardan çıkan benzersiz ilçeleri toplat
    const districts = [...new Set(
        STATE.places
            .map(p => p.ilce)
            .filter(d => d && d.trim() !== '')
    )].sort();

    if (districts.length === 0) {
        DOM.districtSelect.innerHTML = '<option value="">Tüm İlçeler</option>';
        DOM.districtSelect.disabled = true;
        return;
    }

    let opts = '<option value="">Tüm İlçeler</option>';
    districts.forEach(d => {
        opts += `<option value="${d}">${d}</option>`;
    });
    DOM.districtSelect.innerHTML = opts;
    DOM.districtSelect.disabled = false;
    DOM.districtSelect.value = STATE.selectedDistrict || '';
}

function filterPlaces() {
    const search = DOM.searchInput.value.toLowerCase();
    const cat    = DOM.categoryFilter.value;
    const dist   = STATE.selectedDistrict || DOM.districtSelect.value;

    STATE.filteredPlaces = STATE.places.filter(p => {
        const matchSearch = p.ad.toLowerCase().includes(search) || p.ilce.toLowerCase().includes(search);
        const matchCat    = cat  === '' || p.kategori === cat;
        const matchDist   = dist === '' || p.ilce === dist;
        return matchSearch && matchCat && matchDist;
    });

    updateExploreUI();
    syncProvinceMapSelection();
}

function updateExploreUI() {
    DOM.globalStatsLabel.textContent = `${STATE.filteredPlaces.length} Mekan Bulundu`;
    
    if (STATE.filteredPlaces.length === 0) {
        DOM.placesGrid.innerHTML = `
          <div class="empty-state">
            <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
            <p>Seçilen kritele uygun mekan bulunamadı.</p>
          </div>`;
        return;
    }

    const cardsHtml = STATE.filteredPlaces.slice(0, 100).map(place => {
        const inRoute = isPlaceInRoute(place.id);
        return `
        <div class="place-card glass-panel" onclick="window.location.hash='#place/${place.id}'">
            <div class="card-image-wrapper">
                <img class="card-image" src="" alt="${place.ad}"
                     data-wiki="${place.ad}"
                     data-img="${place.img || ''}"
                     data-static="${place.fromStatic ? '1' : ''}"
                     data-wiki2="${place.wiki || ''}"
                     data-wikidata="${place.tags.wikidata || ''}"
                     data-osm-image="${place.tags.image || place.tags['image:0'] || ''}"
                     data-kategori="${place.kategori}"
                     loading="lazy">
            </div>
            <div class="card-content">
                <span class="card-category">${place.kategori}</span>
                <h3 class="card-title">${place.ad}</h3>
                <div class="card-location">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-color)" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                    ${place.ilce ? place.ilce + ', ' : ''}${place.il}
                </div>
                <div class="card-actions-row">
                    <button type="button"
                            class="card-route-btn ${inRoute ? 'added' : ''}"
                            data-route-id="${place.id}"
                            onclick="event.stopPropagation(); window.handleCardRouteClick('${place.id}')">
                        ${inRoute ? '✓ Günlükte (Çıkar)' : '📜 Rotama Ekle'}
                    </button>
                </div>
            </div>
        </div>
        `;
    });

    // Mekan kartları arasına (4. karttan sonra) Polaroid/Seyahatname tarzı In-Feed reklam kartı yerleştir
    if (cardsHtml.length >= 4) {
        const inFeedAdHtml = `
        <div class="vintage-ad-slot vintage-ad-card"
             data-ad-slot="1000000002"
             data-ad-format="fluid"
             aria-label="Sponsorlu Keşif Kartı">
            <div class="vintage-ad-header">
                <span>🧭 SEYAHATNAME NOTU</span>
                <span class="vintage-ad-badge">İLAN</span>
            </div>
            <div class="vintage-ad-body">
                <div class="vintage-ad-placeholder">
                    <span class="vintage-ad-compass">🏕️</span>
                    <strong>${STATE.selectedCity || 'Anadolu'} Keşif &amp; Konaklama Rehberi</strong>
                    <p>Rotanız üzerindeki butik taş konaklar, yerel rehberler ve doğa kampları için ayrılmış özel vitrin.</p>
                </div>
                <ins class="adsbygoogle"
                     style="display:block"
                     data-ad-client="${ADS_CONFIG.client}"
                     data-ad-slot="1000000002"
                     data-ad-format="fluid"></ins>
            </div>
        </div>`;
        cardsHtml.splice(4, 0, inFeedAdHtml);
    }

    DOM.placesGrid.innerHTML = cardsHtml.join('');

    // Trigger lazy loading of Wiki Images
    loadWikiImagesForCards();
    // Grid güncellendiğinde yeni eklenen in-feed reklam yuvasını gecikmeli yükle
    scheduleRefreshAds('explore');
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

async function loadWikiImagesForCards() {
    const images = Array.from(DOM.placesGrid.querySelectorAll('img[data-wiki]'));

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
        if (img.dataset.img) { setImage(img, img.dataset.img, null); return; }
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
            markerZoomAnimation: true
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
            html: `<div class="vintage-pin-seal" title="${place.ad}"><span class="vintage-pin-core">✦</span></div>`,
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
                    ${place.img ? `<img src="${place.img}" alt="${place.ad}" style="width:100%; height:auto; max-height:140px; object-fit:cover; margin-bottom:6px; border:1px solid #8B5A2B;" loading="lazy" onerror="this.remove()"/>` : ''}
                    <h4 style="margin:0 0 4px 0; font-size:15px; font-family:'Playfair Display', serif; color:#3b281e;">${place.ad}</h4>
                    <p style="margin:0 0 8px 0; color:#6e523e; font-size:12px;">${place.kategori}${place.ilce ? ' • ' + place.ilce : ''}</p>
                    <div style="display:flex; gap:4px; flex-wrap:wrap;">
                        <a href="#place/${place.id}" style="display:inline-block; padding:5px 9px; background:#a83228; color:#fdf8ee; border-radius:3px; text-decoration:none; font-size:12px; font-weight:bold;">Detay</a>
                        <button type="button" data-route-id="${place.id}" onclick="window.handleCardRouteClick('${place.id}')" style="padding:5px 9px; background:${inRoute ? '#8B5A2B' : '#2d5a3c'}; color:#fdf8ee; border:none; border-radius:3px; font-size:12px; font-weight:bold; cursor:pointer;">
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
async function renderPlaceDetails(id) {
    DOM.detailTitle.textContent = "Yükleniyor...";
    DOM.detailImageWrapper.innerHTML = "";
    DOM.detailImageWrapper.classList.add("skeleton-loading");
    document.getElementById("btnWikipedia").classList.add("hidden");
    
    // Hafızadan veya Overpass'tan tekli çek (Zaten hafızada var ise anında açar)
    let place = STATE.places.find(p => p.id === id);
    
    if (!place) {
        // Eğer uygulama direkt ID linkiyle açıldıysa fetchingle
        showLoader("Mekan bilgisi getiriliyor...");
        place = await tryFetchSinglePlace(id);
        hideLoader();
    }

    if (!place) {
        DOM.detailTitle.textContent = "Mekan Bulunamadı.";
        return;
    }

    DOM.detailTitle.textContent = place.ad;
    DOM.detailCategory.textContent = place.kategori;
    DOM.detailLocation.textContent = `${place.ilce ? place.ilce + ', ' : ''}${place.il || STATE.selectedCity}`;
    DOM.detailTags.innerHTML = '';
    place.tags = place.tags || {};
    
    // Özellik etiketleri (Türkçe)
    const chips = [place.kategori, place.ilce ? `${place.ilce} ilçesi` : '', place.il || STATE.selectedCity]
        .filter(Boolean);
    if (place.tags.wikipedia || place.tags.wikidata) chips.push('Wikipedia kaydı var');
    chips.forEach(text => {
        const div = document.createElement("div");
        div.className = "detail-tag";
        div.textContent = text;
        DOM.detailTags.appendChild(div);
    });

    DOM.btnDirections.href = `https://www.google.com/maps/dir/?api=1&destination=${place.lat},${place.lon}`;

    // Detay sayfasındaki "Rotama Ekle" butonunu güncelle
    STATE.currentDetailPlace = place;
    syncDetailRouteButton();

    // Fotoğraf ve açıklama: SADECE mekana bağlı kaynaklar
    const showImage = (src) => {
        DOM.detailImageWrapper.classList.remove("skeleton-loading");
        DOM.detailImageWrapper.style.display = '';
        DOM.detailImageWrapper.innerHTML = `<img src="${src}" alt="${place.ad}" style="width:100%; height:100%; object-fit:cover;">`;
        DOM.detailImageWrapper.querySelector('img').onerror = hideImage;
    };
    const hideImage = () => {
        DOM.detailImageWrapper.classList.remove("skeleton-loading");
        DOM.detailImageWrapper.innerHTML = '';
        DOM.detailImageWrapper.style.display = 'none';
    };
    DOM.detailImageWrapper.style.display = '';
    if (place.img) showImage(place.img);

    DOM.detailDescription.textContent = "Bu mekan için Wikipedia açıklaması bulunmuyor.";
    const ref = place.wp || place.tags.wikipedia || '';
    const m = ref.match(/^([a-z]{2,3}):(.+)$/);
    if (m) {
        try {
            const res = await fetch(`https://${m[1]}.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(m[2])}`);
            if (res.ok) {
                const data = await res.json();
                if (data.type !== 'disambiguation') {
                    if (data.extract) DOM.detailDescription.textContent = data.extract;
                    if (data.content_urls && data.content_urls.desktop) {
                        DOM.btnWikipedia.classList.remove("hidden");
                        DOM.btnWikipedia.href = data.content_urls.desktop.page;
                    }
                    if (!place.img && data.thumbnail) showImage(data.thumbnail.source);
                }
            }
        } catch(e) {}
    }
    if (!DOM.detailImageWrapper.querySelector('img')) hideImage();
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
            <div class="journal-item-info" onclick="window.location.hash='#place/${item.id}'">
                <div class="journal-item-title">${item.ad}</div>
                <div class="journal-item-sub">${item.ilce ? item.ilce + ', ' : ''}${item.il} • ${item.kategori}</div>
            </div>
            <button type="button" class="btn-journal-remove" title="Rotadan Çıkar" onclick="window.removeRouteStop('${item.id}')">✕</button>
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
        <div class="place-card glass-panel" onclick="window.location.hash='#place/${place.id}'">
            <div class="card-image-wrapper">
                <span class="distance-stamp">📍 ${distLabel}</span>
                <img class="card-image loaded" src="${place.img || ''}" alt="${place.ad}" loading="lazy">
            </div>
            <div class="card-content">
                <span class="card-category">${place.kategori}</span>
                <h3 class="card-title">${place.ad}</h3>
                <div class="card-location">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-color)" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                    ${place.ilce ? place.ilce + ', ' : ''}${place.il}
                </div>
                <div class="card-actions-row">
                    <button type="button"
                            class="card-route-btn ${inRoute ? 'added' : ''}"
                            data-route-id="${place.id}"
                            onclick="event.stopPropagation(); window.handleCardRouteClick('${place.id}')">
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
    if (DOM.btnGoToMap) {
        DOM.btnGoToMap.addEventListener("click", (e) => {
            e.preventDefault();
            if (!STATE.selectedCity) return;
            window.location.hash = '#map';
            showView('map');
            initOrUpdateLeafletMap();
        });
    }
    const navMapLink = document.querySelector('.nav-link[data-target="map"]');
    if (navMapLink) {
        navMapLink.addEventListener("click", (e) => {
            e.preventDefault();
            if (!STATE.selectedCity) {
                alert("Tam ekran haritayı açmak için lütfen önce haritadan veya listeden bir il seçin.");
                window.location.hash = '#explore';
                showView('explore');
                return;
            }
            window.location.hash = '#map';
            showView('map');
            initOrUpdateLeafletMap();
        });
    }
    DOM.btnBackFromMap.addEventListener("click", () => {
        window.location.hash = '#explore';
        showView('explore');
    });
    DOM.btnBackFromPlace.addEventListener("click", () => {
        window.location.hash = '#explore';
        showView('explore');
    });

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
  setupTheme();
  setupRouter();
  setupEventListeners();
  renderRouteJournal();
  await initD3Map();
  handleRoute();
}

// Start
document.addEventListener("DOMContentLoaded", initApp);
