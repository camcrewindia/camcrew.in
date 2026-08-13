const CACHE_NAME = 'camcrew-pwa-cache-v1';
const PRECACHE_ASSETS = [
  '/',
  '/index.html',
  '/services.html',
  '/rentals.html',
  '/sales.html',
  '/cart.html',
  '/header.html',
  '/footer.html',
  '/static/css/styles.css',
  '/static/js/header-loader.js',
  '/static/js/footer-loader.js',
  '/static/js/pwa-register.js',
  '/static/manifest.json',
  '/static/img/camcrew_studio_logo_cop_y.png',
  '/static/img/camcrew_studio_logo_cop.png'
];

// Install Event — Pre-cache Core Assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[ServiceWorker] Pre-caching core App Shell');
      return cache.addAll(PRECACHE_ASSETS).catch((err) => {
        console.warn('[ServiceWorker] Pre-cache partial failure:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// Activate Event — Clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            console.log('[ServiceWorker] Clearing old cache:', cache);
            return caches.delete(cache);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch Event — Stale-While-Revalidate with Network Fallback
self.addEventListener('fetch', (event) => {
  // Only intercept GET requests & HTTP/HTTPS requests
  if (event.request.method !== 'GET' || !event.request.url.startsWith('http')) return;

  // Don't cache dynamic API requests or admin routes
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/api/') || url.pathname.includes('admin')) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      const fetchPromise = fetch(event.request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      }).catch(() => {
        // Return cached version if network fails
        return cachedResponse;
      });

      return cachedResponse || fetchPromise;
    })
  );
});
