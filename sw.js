// =========================================================================
// GEZİ ATLASI (geziatlasi.com.tr) — SERVICE WORKER
// PWA & TWA Offline Desteği & Stale-While-Revalidate / Network-First Önbellekleme
// =========================================================================

const CACHE_NAME = 'gezi-atlasi-v1.1.1';

// Uygulama kabuğu (App Shell) için önbelleğe alınacak kritik statik dosyalar
const PRECACHE_ASSETS = [
  './',
  './index.html',
  './style.css',
  './app.js',
  './about-extra.css',
  './manifest.json',
  './assets/icon-192.png',
  './assets/icon-512.png',
  './assets/geo/tr_provinces_simplified.geojson',
  './data/places/index.json',
  './data/cuisines.json'
];

// 1. Kurulum (Install): Temel uygulama kabuğunu önbelleğe al
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// 2. Etkinleştirme (Activate): Eski sürümlerin önbelleklerini temizle
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((name) => {
          if (name !== CACHE_NAME) {
            return caches.delete(name);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// 3. İstek Yakalama (Fetch):
// - Veri (JSON, GeoJSON) ve HTML navigasyonu için: Network First (Ağ öncelikli, bağlantı yoksa önbellek)
// - Statik dosyalar (CSS, JS, Görseller, Fontlar) için: Stale-While-Revalidate (Önbellekten anında sun, arka planda güncelle)
self.addEventListener('fetch', (event) => {
  const request = event.request;

  // Sadece GET isteklerini işle (POST/Overpass API istekleri önbelleğe alınmaz)
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Reklam (AdSense) ve harici analitik isteklerini Service Worker önbelleğine alma
  if (url.hostname.includes('googlesyndication') || url.hostname.includes('doubleclick') || url.hostname.includes('google-analytics')) {
    return;
  }

  // A) Navigasyon (HTML) veya JSON / GeoJSON veri istekleri -> Network First
  const isDataOrHtml = 
    request.mode === 'navigate' ||
    url.pathname.endsWith('.json') ||
    url.pathname.endsWith('.geojson') ||
    request.headers.get('accept')?.includes('application/json');

  if (isDataOrHtml) {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(request, responseClone);
            });
          }
          return networkResponse;
        })
        .catch(async () => {
          // Çevrimdışı (offline) durumunda önbellekten sun
          const cachedResponse = await caches.match(request);
          if (cachedResponse) return cachedResponse;
          if (request.mode === 'navigate') {
            return caches.match('./index.html');
          }
          return new Response(JSON.stringify({ error: 'offline' }), {
            headers: { 'Content-Type': 'application/json' }
          });
        })
    );
    return;
  }

  // B) Diğer tüm statik varlıklar (JS, CSS, Fontlar, Görseller) -> Stale-While-Revalidate
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      const fetchPromise = fetch(request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const responseClone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseClone);
          });
        }
        return networkResponse;
      }).catch(() => {
        // Ağ hatası durumunda önbellek varsa sorun yok
        return cachedResponse;
      });

      return cachedResponse || fetchPromise;
    })
  );
});
