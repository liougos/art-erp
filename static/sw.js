/* ART RESTORATION ERP — Service Worker */
const CACHE = 'art-erp-v1';
const STATIC = [
  '/static/css/style.css',
  '/static/js/app.js',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js',
];

/* Install: pre-cache static assets */
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(STATIC)).then(() => self.skipWaiting())
  );
});

/* Activate: delete old caches */
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

/* Fetch: network-first for HTML/API, cache-first for static assets */
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  /* Always fetch from network for main app pages (login, data, etc.) */
  if (e.request.mode === 'navigate' || url.pathname.startsWith('/api/')) {
    e.respondWith(
      fetch(e.request).catch(() =>
        caches.match('/') || new Response('Offline — reconnect to the network', {
          headers: { 'Content-Type': 'text/plain' }
        })
      )
    );
    return;
  }

  /* Cache-first for static assets (CSS, JS, fonts) */
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request).then(res => {
      if (res.ok && (url.pathname.startsWith('/static/') || url.hostname.includes('cdn.jsdelivr'))) {
        caches.open(CACHE).then(c => c.put(e.request, res.clone()));
      }
      return res;
    }))
  );
});
