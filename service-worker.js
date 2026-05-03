/**
 * service-worker.js — Gastos Personales 2026
 * ─────────────────────────────────────────────────────────────────────────
 * Estrategias por tipo de recurso:
 *
 *  NETWORK-ONLY  → datos de Google Sheets y rutas de debug (siempre frescos)
 *  CACHE-FIRST   → assets estáticos de Dash/Plotly/Bootstrap (cambian poco)
 *  NETWORK-FIRST → HTML del dashboard (querés datos frescos; cache de respaldo)
 *
 * Para forzar actualización completa: incrementá CACHE_VERSION.
 * ─────────────────────────────────────────────────────────────────────────
 */

const CACHE_VERSION = "gastos-v1";

// Shell mínimo que se pre-cachea al instalar
const PRECACHE_URLS = [
    "/dashboard/",
    "/manifest.json",
    "/assets/icon-192.png",
    "/assets/icon-512.png",
];

// Patrones que NUNCA se cachean (datos en tiempo real)
const NETWORK_ONLY = [
    /googleapis\.com/,
    /sheets\.google/,
    /\/debug/,
    /\/_reload-hash/,       // hot-reload de Dash en dev
    /\/_dash-update-component/, // callbacks de Dash
    /\/_dash-dependencies/,
];

// ─── INSTALL: pre-cacheo del shell ───────────────────────────────────────────
self.addEventListener("install", (event) => {
    console.log("[SW] Instalando:", CACHE_VERSION);

    event.waitUntil(
        caches.open(CACHE_VERSION).then((cache) => {
            // addAll() falla completo si una URL da error → usamos add() individual
            return Promise.allSettled(
                PRECACHE_URLS.map((url) =>
                    cache.add(url).catch((err) =>
                        console.warn("[SW] No se pudo pre-cachear:", url, err)
                    )
                )
            );
        }).then(() => {
            console.log("[SW] Pre-cacheo completo. Forzando activación.");
            return self.skipWaiting(); // activa sin esperar que cierren otras tabs
        })
    );
});

// ─── ACTIVATE: limpiar caches de versiones anteriores ────────────────────────
self.addEventListener("activate", (event) => {
    console.log("[SW] Activando:", CACHE_VERSION);

    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter((key) => key !== CACHE_VERSION)
                    .map((key) => {
                        console.log("[SW] Eliminando cache viejo:", key);
                        return caches.delete(key);
                    })
            )
        ).then(() => {
            console.log("[SW] Activo. Tomando control de todas las tabs.");
            return self.clients.claim(); // controla tabs abiertas sin recargar
        })
    );
});

// ─── FETCH: enrutador de estrategias ─────────────────────────────────────────
self.addEventListener("fetch", (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Ignorar todo lo que no sea HTTP/HTTPS (chrome-extension://, etc.)
    if (!["http:", "https:"].includes(url.protocol)) return;

    // Solo interceptar GET
    if (request.method !== "GET") return;

    // ── 1. Network-Only: Google Sheets API, debug, callbacks de Dash ─────────
    if (NETWORK_ONLY.some((pattern) => pattern.test(request.url))) {
        event.respondWith(fetch(request));
        return;
    }

    // ── 2. Cache-First: assets estáticos de Dash, Plotly, Bootstrap, íconos ──
    //    Reconocidos por extensión o por el prefijo /_dash-component-suites/
    if (isStaticAsset(url)) {
        event.respondWith(cacheFirst(request));
        return;
    }

    // ── 3. Network-First: HTML del dashboard y cualquier otra ruta ────────────
    event.respondWith(networkFirst(request));
});

// ─── Detecta si una URL es un asset estático cacheable ───────────────────────
function isStaticAsset(url) {
    const staticExtensions = /\.(js|mjs|css|woff2?|ttf|eot|otf|png|jpg|jpeg|gif|svg|ico|webp)(\?.*)?$/i;
    const dashSuites = /\/_dash-component-suites\//;
    const assetsFolder = /\/assets\//;

    return (
        staticExtensions.test(url.pathname) ||
        dashSuites.test(url.pathname) ||
        assetsFolder.test(url.pathname)
    );
}

// ─── Cache-First ──────────────────────────────────────────────────────────────
// Devuelve desde cache si existe; si no, va a la red y guarda la respuesta.
async function cacheFirst(request) {
    const cached = await caches.match(request);
    if (cached) return cached;

    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(CACHE_VERSION);
            cache.put(request, response.clone()); // guardar para la próxima vez
        }
        return response;
    } catch {
        return new Response("Asset no disponible sin conexión.", {
            status: 503,
            headers: { "Content-Type": "text/plain; charset=utf-8" },
        });
    }
}

// ─── Network-First ────────────────────────────────────────────────────────────
// Intenta red primero; si falla (offline), sirve desde cache.
// Si no hay cache tampoco, muestra una página offline amigable.
async function networkFirst(request) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(CACHE_VERSION);
            cache.put(request, response.clone());
        }
        return response;
    } catch {
        const cached = await caches.match(request);
        if (cached) return cached;

        // Fallback: página offline integrada
        return offlinePage();
    }
}

// ─── Página offline ───────────────────────────────────────────────────────────
function offlinePage() {
    const html = `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sin conexión — Gastos 2026</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0d1117;
      color: #e6edf3;
      font-family: Arial, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 20px;
    }
    .card {
      background: #1a1f2e;
      border: 1px solid #30363d;
      border-radius: 16px;
      padding: 40px 32px;
      text-align: center;
      max-width: 360px;
      width: 100%;
    }
    .icon { font-size: 3rem; margin-bottom: 16px; }
    h1 { color: #00d4aa; font-size: 1.4rem; margin-bottom: 8px; }
    p  { color: #8b949e; font-size: .9rem; line-height: 1.5; margin-bottom: 24px; }
    button {
      background: transparent;
      border: 1px solid #00d4aa;
      color: #00d4aa;
      border-radius: 8px;
      padding: 10px 24px;
      font-size: .95rem;
      cursor: pointer;
      width: 100%;
    }
    button:active { opacity: .7; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">📵</div>
    <h1>Sin conexión</h1>
    <p>No se puede cargar el dashboard ahora.<br>
       Reconectate a internet y volvé a intentar.</p>
    <button onclick="location.reload()">Reintentar</button>
  </div>
</body>
</html>`;

    return new Response(html, {
        status: 503,
        headers: { "Content-Type": "text/html; charset=utf-8" },
    });
}

// ─── Mensaje desde el cliente (ej: forzar actualización) ─────────────────────
self.addEventListener("message", (event) => {
    if (event.data && event.data.type === "SKIP_WAITING") {
        console.log("[SW] SKIP_WAITING recibido. Activando nueva versión.");
        self.skipWaiting();
    }
});
