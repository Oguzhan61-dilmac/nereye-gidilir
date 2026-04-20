// ==========================================
// NEREYE GİDİLİR? - V2 SPA CONTROLLER
// Tüm yapı Vanilla JS ile "Tek Sayfa Uygulaması"nda (SPA) birleşti.
// ==========================================

const STATE = {
  view: 'explore', // 'explore', 'map', 'place'
  geoData: null,   // D3 and BBox calculation from GeoJSON
  selectedCity: '',
  selectedDistrict: '',
  places: [],      // Overpass'tan gelen ham mekanlar
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
    place: document.getElementById("view-place")
  },
  themeBtn: document.getElementById("themeToggle"),
  d3Container: document.getElementById("d3MapContainer"),
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
  btnWikipedia: document.getElementById("btnWikipedia")
};


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

  // Default
  showView('explore');
  // Update nav UI
  document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
  document.querySelector('.nav-link[data-target="explore"]').classList.add('active');
}

function showView(viewId) {
  STATE.view = viewId;
  window.scrollTo(0, 0);
  Object.values(DOM.views).forEach(el => el.classList.remove('active'));
  DOM.views[viewId].classList.add('active');
  
  if(viewId === 'map') {
    document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
    document.querySelector('.nav-link[data-target="map"]').classList.add('active');
    setTimeout(() => { if(STATE.leafletMap) STATE.leafletMap.invalidateSize(); }, 300);
  }
}

// ================= LOADER UTILS =================
function showLoader(msg = "Yükleniyor...") {
  DOM.loaderMsg.textContent = msg;
  DOM.loader.classList.remove("hidden");
}

function hideLoader() {
  DOM.loader.classList.add("hidden");
}

// ================= D3 MAP INITIALIZATION =================
async function initD3Map() {
  try {
    const res = await fetch("./assets/geo/tr_provinces_simplified.geojson");
    if (!res.ok) throw new Error("GeoJSON fetching failed");
    STATE.geoData = await res.json();
    populateSelects();
    drawD3Map();
  } catch (error) {
    console.error("Harita verisi yüklenemedi:", error);
    DOM.d3Container.innerHTML = "<p style='color:red; padding:2rem;'>Harita dosyası (GeoJSON) yüklenemedi.</p>";
  }
}

function drawD3Map() {
  const width = DOM.d3Container.clientWidth || 800;
  const height = DOM.d3Container.clientHeight || 400;

  const svg = d3.select("#d3MapContainer").append("svg")
    .attr("width", "100%")
    .attr("height", "100%")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("preserveAspectRatio", "xMidYMid meet");

  const projection = d3.geoMercator().fitSize([width, height], STATE.geoData);
  const path = d3.geoPath().projection(projection);

  // Gölgelendirme filtresi
  const defs = svg.append("defs");
  const filter = defs.append("filter").attr("id", "drop-shadow").attr("height", "130%");
  filter.append("feDropShadow").attr("dx", "0").attr("dy", "3").attr("stdDeviation", "3").attr("flood-color", "rgba(0,0,0,0.1)");

  const g = svg.append("g").style("filter", "url(#drop-shadow)");

  // Şehir Çizimi
  g.selectAll("path")
    .data(STATE.geoData.features)
    .enter()
    .append("path")
    .attr("class", "country-path")
    .attr("d", path)
    .attr("id", d => `province-${d.properties.name_tr}`)
    .on("click", function(event, d) {
       selectCity(d.properties.name_tr);
    });

  // Zoom Davranışı
  const zoom = d3.zoom().scaleExtent([1, 8]).on("zoom", (event) => g.attr("transform", event.transform));
  svg.call(zoom);
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
  if (!cityName) return; // Türkiye geneli desteklenmiyor limit yüzünden
  
  STATE.selectedCity = cityName;
  DOM.citySelect.value = cityName;
  DOM.globalCityLabel.textContent = cityName;
  
  // D3 Haritasını Güncelle
  d3.selectAll('.country-path').classed('selected', false);
  const targetPath = d3.select(`#province-${cityName}`);
  if (!targetPath.empty()) {
    targetPath.classed('selected', true);
  }

  // Butonları aç
  DOM.btnGoToMap.classList.remove('disabled');
  DOM.searchInput.disabled = false;
  DOM.categoryFilter.disabled = false;

  await loadCityData(cityName);
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

async function loadCityData(cityName) {
  showLoader(`${cityName} turistik verileri OverpassAPI'den çekiliyor...`);
  
  let bbox = calculateCityBBox(cityName);
  let areaDef = ""; let suffix = "";
  if (!bbox) {
     areaDef = `area["boundary"="administrative"]["admin_level"="4"]["name"="${cityName}"]->.searchArea;`;
     suffix = "(area.searchArea)";
  }

  const query = `
      [out:json][timeout:25]${bbox};
      ${areaDef}
      (
          node["tourism"="museum"]${suffix};
          node["historic"="castle"]${suffix};
          node["historic"="ruins"]${suffix};
          node["historic"="archaeological_site"]${suffix};
          node["natural"="waterfall"]${suffix};
          node["natural"="cave_entrance"]${suffix};
          node["tourism"="theme_park"]${suffix};
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

  // Parse Overpass Nodes
  STATE.places = fetchedData.elements.map(el => {
      const t = el.tags || {};
      const name = t["name:tr"] || t.name;
      if (!name) return null;

      let cat = "Diğer";
      if (t.tourism === "museum") cat = "Müze";
      else if (t.historic === "castle") cat = "Kale";
      else if (t.historic === "ruins" || t.historic === "archaeological_site") cat = "Tarihi / Antik Kent";
      else if (t.natural === "waterfall" || t.natural === "cave_entrance") cat = "Doğa Harikası";
      else if (t.tourism === "theme_park") cat = "Eğlence / Tema Park";

      return {
          id: `${el.type}:${el.id}`,
          ad: name,
          il: cityName,
          ilce: t["addr:district"] || t.ilce || "",
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
  
  STATE.places = uniq;
  STATE.filteredPlaces = [...STATE.places];
  
  updateCategoryFilters();
  updateExploreUI();
  
  // Pokud Leaflet haritası arka planda açıksa markerları da güncellemek iyi olur:
  if (STATE.leafletMap && STATE.view === 'map') {
      renderMapMarkers();
  }
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

function filterPlaces() {
    const search = DOM.searchInput.value.toLowerCase();
    const cat = DOM.categoryFilter.value;

    STATE.filteredPlaces = STATE.places.filter(p => {
        const matchSearch = p.ad.toLowerCase().includes(search) || p.ilce.toLowerCase().includes(search);
        const matchCat = cat === "" || p.kategori === cat;
        return matchSearch && matchCat;
    });

    updateExploreUI();
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

    DOM.placesGrid.innerHTML = STATE.filteredPlaces.slice(0, 100).map(place => `
        <div class="place-card glass-panel" onclick="window.location.hash='#place/${place.id}'">
            <div class="card-image-wrapper">
                <img class="card-image" src="./assets/images/default-place.jpg" alt="${place.ad}" data-wiki="${place.ad}" data-wiki2="${place.wiki}" loading="lazy" onerror="this.src='https://placehold.co/600x400/1e293b/FFFFFF?text=Görsel+Yok'">
            </div>
            <div class="card-content">
                <span class="card-category">${place.kategori}</span>
                <h3 class="card-title">${place.ad}</h3>
                <div class="card-location">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-color)" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                    ${place.ilce ? place.ilce + ', ' : ''}${place.il}
                </div>
            </div>
        </div>
    `).join('');

    // Trigger lazy loading of Wiki Images
    loadWikiImagesForCards();
}

async function loadWikiImagesForCards() {
    const images = DOM.placesGrid.querySelectorAll('img[data-wiki]');
    for (const img of images) {
        if(img.dataset.loaded === "true") continue;
        
        let wikiQuery = img.dataset.wiki; // first try name
        if (img.dataset.wiki2 && img.dataset.wiki2.includes('wiki')) {
             wikiQuery = img.dataset.wiki2.split(':').pop(); // extract 'en:Title'
        }
        
        try {
            const res = await fetch(`https://tr.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(wikiQuery)}`);
            if (res.ok) {
                const data = await res.json();
                if (data.thumbnail && data.thumbnail.source) {
                    img.src = data.thumbnail.source;
                    img.dataset.loaded = "true";
                }
            }
        } catch(e) {}
    }
}

// ================= LEAFLET MAP =================
function initOrUpdateLeafletMap() {
    if (!STATE.leafletMap) {
        STATE.leafletMap = L.map('leafletMap').setView([39.0, 35.0], 6);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(STATE.leafletMap);
        STATE.markerCluster = L.markerClusterGroup({
             showCoverageOnHover: false,
             maxClusterRadius: 40
        });
        STATE.leafletMap.addLayer(STATE.markerCluster);
    }
    
    DOM.mapTitle.textContent = `${STATE.selectedCity} Keşif Haritası`;
    renderMapMarkers();
}

function renderMapMarkers() {
    if (!STATE.markerCluster) return;
    STATE.markerCluster.clearLayers();
    
    let toRender = STATE.places;
    if (DOM.mapCategoryFilter.value) {
        toRender = STATE.places.filter(p => p.kategori === DOM.mapCategoryFilter.value);
    }

    const bounds = L.latLngBounds();

    toRender.forEach(place => {
        if (!place.lat || !place.lon) return;
        
        const popupContent = `
            <div style="font-family: 'Inter', sans-serif; padding:5px;">
                <h4 style="margin:0 0 5px 0; font-size:16px;">${place.ad}</h4>
                <p style="margin:0 0 10px 0; color:#666; font-size:13px;">${place.kategori}</p>
                <a href="#place/${place.id}" style="display:inline-block; padding:6px 12px; background:#ef4444; color:white; border-radius:4px; text-decoration:none; font-size:13px; font-weight:bold;">Detayları Gör</a>
            </div>
        `;

        const icon = L.divIcon({
            className: 'custom-marker',
            html: `<div style="background-color:#ef4444; width:24px; height:24px; border-radius:50%; border:3px solid white; box-shadow:0 2px 5px rgba(0,0,0,0.3);"></div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12]
        });

        const marker = L.marker([place.lat, place.lon], { icon }).bindPopup(popupContent);
        STATE.markerCluster.addLayer(marker);
        bounds.extend([place.lat, place.lon]);
    });

    if (toRender.length > 0) {
        STATE.leafletMap.fitBounds(bounds, { padding: [50, 50] });
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
    
    // Process Tags
    const featureKeys = ['historic', 'tourism', 'natural', 'leisure', 'building', 'religion'];
    featureKeys.forEach(k => {
        if(place.tags[k]) {
            const div = document.createElement("div");
            div.className = "detail-tag";
            div.textContent = `${k}: ${place.tags[k]}`;
            DOM.detailTags.appendChild(div);
        }
    });

    DOM.btnDirections.href = `https://www.google.com/maps/dir/?api=1&destination=${place.lat},${place.lon}`;

    // Get Wiki logic
    let desc = "Açıklama veya Wikipedia verisi bulunamadı.";
    DOM.detailDescription.textContent = desc;

    let wikiQuery = place.ad;
    if (place.tags.wikipedia) wikiQuery = place.tags.wikipedia.split(':').pop();

    try {
        const res = await fetch(`https://tr.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(wikiQuery)}`);
        if (res.ok) {
            const data = await res.json();
            if (data.extract) DOM.detailDescription.textContent = data.extract;
            if (data.empty === false && data.content_urls) {
                document.getElementById("btnWikipedia").classList.remove("hidden");
                document.getElementById("btnWikipedia").href = data.content_urls.desktop.page;
            }
            if (data.thumbnail) {
                DOM.detailImageWrapper.classList.remove("skeleton-loading");
                DOM.detailImageWrapper.innerHTML = `<img src="${data.thumbnail.source}" alt="${place.ad}" style="width:100%; height:100%; object-fit:cover;">`;
            }
        }
    } catch(e) {}

    // Skeleton remove after timeout if no image found
    setTimeout(() => {
        if (DOM.detailImageWrapper.innerHTML === "") {
             DOM.detailImageWrapper.classList.remove("skeleton-loading");
             DOM.detailImageWrapper.innerHTML = `<img src="https://placehold.co/1200x600/1e293b/FFFFFF?text=Görsel+Bulunamadı" style="width:100%; height:100%; object-fit:cover;">`;
        }
    }, 3000);
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


// ================= EVENT LISTENERS =================
function setupEventListeners() {
    DOM.citySelect.addEventListener("change", (e) => selectCity(e.target.value));
    
    // Filter bindings
    DOM.searchInput.addEventListener("input", filterPlaces);
    DOM.categoryFilter.addEventListener("change", filterPlaces);
    
    // Map Filter bindings
    DOM.mapCategoryFilter.addEventListener("change", renderMapMarkers);

    // Back buttons
    DOM.btnBackFromMap.addEventListener("click", () => { window.location.hash = '#explore'; });
    DOM.btnBackFromPlace.addEventListener("click", () => { window.location.hash = '#explore'; });

    // Theme logic
    DOM.themeBtn.addEventListener("click", () => {
        const isDark = document.body.classList.contains("theme-dark");
        if (isDark) {
            document.body.classList.remove("theme-dark");
            document.body.classList.add("theme-light");
            localStorage.setItem("nereye_theme", "light");
            document.querySelector(".icon-moon").classList.remove("hidden");
            document.querySelector(".icon-sun").classList.add("hidden");
        } else {
            document.body.classList.add("theme-dark");
            document.body.classList.remove("theme-light");
            localStorage.setItem("nereye_theme", "dark");
            document.querySelector(".icon-moon").classList.add("hidden");
            document.querySelector(".icon-sun").classList.remove("hidden");
        }
    });
}

function setupTheme() {
    const savedTheme = localStorage.getItem("nereye_theme") || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    if (savedTheme === "dark") {
        document.body.classList.add("theme-dark");
        document.body.classList.remove("theme-light");
        document.querySelector(".icon-moon").classList.add("hidden");
        document.querySelector(".icon-sun").classList.remove("hidden");
    }
}

// Start
document.addEventListener("DOMContentLoaded", initApp);
