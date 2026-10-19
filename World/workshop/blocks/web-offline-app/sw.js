// The service worker: keeps a copy of the app on the phone so it opens with no internet.
// Change VERSION whenever you change the app, so phones pick up the new copy next time they're online.
const VERSION = "v1";
const FILES = ["./", "index.html", "manifest.webmanifest", "icon.svg", "css/app.css", "js/app.js"
  /* archie:files */];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
    const copy = res.clone();
    caches.open(VERSION).then((c) => c.put(e.request, copy));
    return res;
  }).catch(() => caches.match("index.html"))));
});
