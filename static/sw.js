/* TriHumanizer service worker — v1.6.1
 *
 * Offline caching ONLY for static application assets. API responses that
 * contain private user text are NEVER cached.
 */
"use strict";

const CACHE_NAME = "trihumanizer-static-v1.6.1";

const STATIC_ASSETS = [
  "/",
  "/static/styles.css?v=1.6.1",
  "/static/app.js?v=1.6.1",
  "/static/speech.js?v=1.6.1",
  "/static/layout-corrector.js?v=1.6.1",
  "/static/icon-192.png",
  "/static/icon-512.png",
  "/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Never cache API responses (they may contain private user text).
  if (url.pathname.startsWith("/api/")) return;
  // Only same-origin static assets are cached.
  if (url.origin !== self.location.origin) return;
  if (!url.pathname.startsWith("/static/") && url.pathname !== "/" && !url.pathname.endsWith("/manifest.webmanifest")) {
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return response;
      });
    })
  );
});
