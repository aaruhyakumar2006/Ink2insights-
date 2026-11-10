/**
 * INK2Insights Service Worker — Phase 4 Offline Queue
 * =====================================================
 * Strategy:
 *  - Cache-first for static assets (HTML, CSS, JS, fonts, images).
 *  - Network-first for API calls, with automatic retry on restoration.
 *  - Background Sync (if supported) for queued /api/extract POSTs.
 *
 * Sync tag: 'ink2i-offline-sync'
 *
 * NOTE: This SW intentionally does NOT cache patient image data.
 *       Raw image blobs are encrypted and stored in IndexedDB by
 *       offline-queue.js — this SW only handles asset caching and
 *       triggers the sync event so queue-draining can run.
 */

const CACHE_VERSION = 'ink2i-v20261107_nav_fix';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/js/app.js',
  '/js/api.js',
  '/js/scanner.js',
  '/js/offline-queue.js',
  '/css/styles.css',
  '/intro/intro.css',
  '/intro/intro.js',
  '/intro/intro-portrait.mp4',
  '/intro/intro-landscape.mp4',
  '/intro/poster-portrait.jpg',
  '/intro/poster-landscape.jpg',
];

// ── Install: pre-cache static shell ─────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => {
      // Cache what we can; ignore failures for assets that may not exist yet
      return Promise.allSettled(
        STATIC_ASSETS.map((url) => cache.add(url).catch(() => {}))
      );
    }).then(() => self.skipWaiting())
  );
});

// ── Activate: remove stale caches ───────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_VERSION)
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── Helper: Support Range requests on cached video assets for offline iOS/Android playback ──
async function handleRangeResponse(request, response) {
  const rangeHeader = request.headers.get('range');
  if (!rangeHeader) return response;

  const arrayBuffer = await response.arrayBuffer();
  const bytes = rangeHeader.replace(/bytes=/, '').split('-');
  const total = arrayBuffer.byteLength;
  const start = parseInt(bytes[0], 10) || 0;
  const end = bytes[1] ? parseInt(bytes[1], 10) : total - 1;

  if (start >= total || end >= total) {
    return new Response('', {
      status: 416,
      headers: { 'Content-Range': `bytes */${total}` }
    });
  }

  const sliced = arrayBuffer.slice(start, end + 1);
  return new Response(sliced, {
    status: 206,
    statusText: 'Partial Content',
    headers: {
      'Content-Type': response.headers.get('Content-Type') || 'video/mp4',
      'Content-Range': `bytes ${start}-${end}/${total}`,
      'Content-Length': sliced.byteLength,
      'Accept-Ranges': 'bytes'
    }
  });
}

// ── Fetch: cache-first for assets, network-first for API ────────────────────
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Never intercept non-GET or API calls (handled by offline-queue.js)
  if (request.method !== 'GET') return;
  if (url.pathname.startsWith('/api/')) return;

  // HTML navigation documents: Network-first with offline cache fallback
  if (request.mode === 'navigate' || url.pathname === '/' || url.pathname.endsWith('.html')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request.url).then((cached) => cached || caches.match('/index.html')))
    );
    return;
  }

  event.respondWith(
    caches.match(request.url).then((cached) => {
      if (cached) {
        if (request.headers.get('range')) {
          return handleRangeResponse(request, cached.clone());
        }
        return cached;
      }
      return fetch(request).then((response) => {
        // Cache successful same-origin responses
        if (
          (response.ok || response.status === 206) &&
          !url.pathname.includes('socket')
        ) {
          if (url.pathname.endsWith('.mp4')) {
            fetch(request.url).then((fullRes) => {
              if (fullRes.ok) {
                caches.open(CACHE_VERSION).then((c) => c.put(request.url, fullRes));
              }
            }).catch(() => {});
          } else if (response.ok && response.type === 'basic') {
            const clone = response.clone();
            caches.open(CACHE_VERSION).then((c) => c.put(request, clone));
          }
        }
        return response;
      }).catch(() => {
        // Offline fallback: serve root shell for navigation requests
        if (request.mode === 'navigate') {
          return caches.match('/index.html');
        }
        return new Response('Offline', { status: 503 });
      });
    })
  );
});

// ── Background Sync: drain the offline queue ────────────────────────────────
self.addEventListener('sync', (event) => {
  if (event.tag === 'ink2i-offline-sync') {
    event.waitUntil(notifyClientsToSync());
  }
});

/**
 * Post a message to all controlled client windows so they can
 * run the queue-drain logic from offline-queue.js.
 * The actual drain (decryption + fetch) must happen in the window
 * context because: (a) WebCrypto keys are non-transferable, and
 * (b) FormData with Blobs cannot be reconstructed in the SW.
 */
async function notifyClientsToSync() {
  const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  for (const client of clients) {
    client.postMessage({ type: 'INK2I_DRAIN_QUEUE' });
  }
}

// ── Push: online restoration notification (fallback for no-SW-sync browsers) ─
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'PING') {
    event.source.postMessage({ type: 'PONG' });
  }
});
