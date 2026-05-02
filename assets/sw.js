const CACHE_NAME = 'gastos-pwa-cache-v1';
const urlsToCache = [
  '/',
  '/manifest.json',
  '/assets/style.css',
  '/assets/icon-192.png',
  '/assets/icon-512.png'
];

self.addEventListener('install', function(event) {
  // Realiza la instalación y cachea los archivos estáticos básicos
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        console.log('Archivos en caché para PWA');
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', function(event) {
  // Estrategia Stale-While-Revalidate para navegación rápida
  event.respondWith(
    caches.match(event.request)
      .then(function(response) {
        // Cache hit - return response
        if (response) {
          return response;
        }
        return fetch(event.request);
      }
    )
  );
});

self.addEventListener('activate', event => {
  // Limpia cachés antiguos
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});
