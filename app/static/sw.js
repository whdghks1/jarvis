const CACHE = "jarvis-ui-v5";
const ASSETS = ["/", "/static/style.css", "/static/app.js", "/static/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))));
});

self.addEventListener("fetch", (event) => {
  const path = new URL(event.request.url).pathname;
  if (event.request.method !== "GET" || path.startsWith("/chat") || path.startsWith("/downloads/")) return;
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
