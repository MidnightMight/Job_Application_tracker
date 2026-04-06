/* Job Application Tracker — Service Worker
 *
 * Strategy:
 *   - Static assets (CSS, JS, icons)  → Cache-first, update in background
 *   - Navigation (HTML pages)         → Network-first with cache fallback
 *   - API / POST requests             → Network-only (never cache mutations)
 *
 * The cache name includes a version token so that deploying new code
 * automatically invalidates the previous cache on activate.
 */

const CACHE_NAME = 'job-tracker-v1';

const PRECACHE_URLS = [
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon.svg',
];

// ---------------------------------------------------------------------------
// Install — pre-cache static shell assets
// ---------------------------------------------------------------------------
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE_URLS))
  );
  // Activate immediately without waiting for old tabs to close
  self.skipWaiting();
});

// ---------------------------------------------------------------------------
// Activate — delete stale caches from previous versions
// ---------------------------------------------------------------------------
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    )
  );
  // Take control of all open clients straight away
  self.clients.claim();
});

// ---------------------------------------------------------------------------
// Fetch — serve cached content when offline
// ---------------------------------------------------------------------------
self.addEventListener('fetch', event => {
  const { request } = event;

  // Only handle GET requests; let everything else (POST, PUT, DELETE) pass
  // straight through to the network so mutations are never intercepted.
  if (request.method !== 'GET') return;

  // Skip browser-extension and non-http(s) requests
  if (!request.url.startsWith('http')) return;

  // Skip API calls — always go to the network for live data
  const url = new URL(request.url);
  if (url.pathname.startsWith('/api/')) return;

  // --- Navigation requests (HTML pages) — Network-first ---
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(response => {
          // Cache a clone of successful HTML responses
          if (response.ok) {
            caches.open(CACHE_NAME).then(cache => cache.put(request, response.clone()));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // --- Static assets (CSS, JS, fonts, images) — Cache-first ---
  event.respondWith(
    caches.match(request).then(cached => {
      if (cached) {
        // Return cache immediately; refresh in background (fire-and-forget)
        fetch(request).then(response => {
          if (response.ok) {
            caches.open(CACHE_NAME).then(cache => cache.put(request, response.clone()));
          }
        }).catch(() => {});
        return cached;
      }
      // Not in cache — fetch and cache for next time
      return fetch(request).then(response => {
        if (response.ok) {
          caches.open(CACHE_NAME).then(cache => cache.put(request, response.clone()));
        }
        return response;
      });
    })
  );
});
