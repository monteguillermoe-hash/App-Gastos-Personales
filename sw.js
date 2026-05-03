/**
 * sw.js — Service Worker para "Gastos Personales 2026"
 *
 * Estrategia:
 *   • Shell de la app (HTML, CSS, JS de Dash/Plotly) → Cache-First
 *   • Llamadas a la API de Google Sheets                → Network-First
 *   • Todo lo demás                                    → Network con fallback a cache
 *
 * Para forzar actualización: cambiá el número de CACHE_VERSION.
 */

const CACHE_VERSION  = "gastos-v1";
const OFFLINE_URL    = "/dashboard/";

// Assets que se pre-cachean al instalar el SW
const PRECACHE_URLS = [
  "/dashboard/",
  "/manifest.json",
  "/assets/icon-192.png",
  "/assets/icon-512.png",
];

// Patrones que SIEMPRE van a la red (datos en tiempo real)
const NETWORK_ONLY_PATTERNS = [
  /googleapis\.com/,
  /sheets\.google/,
  /\/debug/,
];

// ─── Instalación: pre-cacheo del shell ───────────────────────────────────────
self.addEventListener("install", (event) => {
  console.log("[SW] Instalando versión:", CACHE_VERSION);
  event.waitUntil(
    caches
      .open(CACHE_VERSION)
      .then((cache) => {
        console.log("[SW] Pre-cacheando shell de la app");
        // addAll falla si alguna URL devuelve error → usamos add individualmente
        return Promise.allSettled(
          PRECACHE_URLS.map((url) =>
            cache.add(url).catch((err) =>
              console.warn("[SW] No se pudo pre-cachear:", url, err)
            )
          )
        );
      })
      .then(() => self.skipWaiting())   // activa el nuevo SW sin esperar
  );
});

// ─── Activación: limpieza de caches viejas ───────────────────────────────────
self.addEventListener("activate", (event) => {
  console.log("[SW] Activando:", CACHE_VERSION);
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== CACHE_VERSION)
            .map((key) => {
              console.log("[SW] Eliminando cache vieja:", key);
              return caches.delete(key);
            })
        )
      )
      .then(() => self.clients.claim())  // toma control de tabs abiertos
  );
});

// ─── Fetch: lógica de caché según tipo de recurso ────────────────────────────
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Ignorar requests que no son GET
  if (request.method !== "GET") return;

  // Ignorar extensiones de browser (chrome-extension://, etc.)
  if (!["http:", "https:"].includes(url.protocol)) return;

  // Network-Only: datos de Google Sheets y rutas de debug
  if (NETWORK_ONLY_PATTERNS.some((p) => p.test(request.url))) {
    event.respondWith(fetch(request));
    return;
  }

  // Assets estáticos de Dash (JS/CSS de Plotly, Bootstrap, Dash) → Cache-First
  if (
    url.pathname.startsWith("/_dash") ||
    url.pathname.startsWith("/assets/") ||
    /\.(js|css|woff2?|ttf|png|ico|svg)(\?.*)?$/.test(url.pathname)
  ) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Todo lo demás (HTML del dashboard) → Network-First con fallback a cache
  event.respondWith(networkFirst(request));
});

// ─── Estrategia Cache-First ───────────────────────────────────────────────────
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_VERSION);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // Sin red y sin cache → no hay nada que devolver
    return new Response("Asset no disponible offline.", {
      status: 503,
      headers: { "Content-Type": "text/plain" },
    });
  }
}

// ─── Estrategia Network-First ─────────────────────────────────────────────────
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_VERSION);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // Sin red → servimos desde cache
    const cached = await caches.match(request);
    if (cached) return cached;

    // Último recurso: página offline del dashboard
    const offlinePage = await caches.match(OFFLINE_URL);
    return (
      offlinePage ||
      new Response(
        `<html><body style="background:#0d1117;color:#e6edf3;font-family:Arial;
         display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
         <div style="text-align:center">
           <div style="font-size:3rem">📵</div>
           <h2 style="color:#00d4aa">Sin conexión</h2>
           <p>Reconectate para ver los datos actualizados.</p>
         </div></body></html>`,
        { status: 503, headers: { "Content-Type": "text/html" } }
      )
    );
  }
}
