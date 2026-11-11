/* Archie phone app: works offline (the app itself is kept on the phone), receives things shared from
   other apps (Android share menu), and shows notifications sent by your PC. */
const CACHE = "archie-shell-v1";
const SHELL = ["/", "/app.js", "/scan.js", "/style.css", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png", "/badge-96.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

function idbShared(value) {
  return new Promise((res, rej) => {
    const r = indexedDB.open("archie", 1);
    r.onupgradeneeded = () => { const d = r.result; ["blobs", "world", "articles", "shared", "rec"].forEach((n) => { if (!d.objectStoreNames.contains(n)) d.createObjectStore(n); }); };
    r.onsuccess = () => { const tx = r.result.transaction("shared", "readwrite"); tx.objectStore("shared").put(value, "last"); tx.oncomplete = res; tx.onerror = () => rej(tx.error); };
    r.onerror = () => rej(r.error);
  });
}

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin) return;
  if (e.request.method === "POST" && url.pathname === "/share") {          // Android share menu
    e.respondWith((async () => {
      const f = await e.request.formData();
      await idbShared({ at: Date.now(), title: f.get("title") || "", text: f.get("text") || "", url: f.get("url") || "",
        files: f.getAll("files").filter((x) => x && x.size) });
      return Response.redirect("/#shared", 303);
    })());
    return;
  }
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/")) return;
  e.respondWith((async () => {                                              // network first, the copy when offline
    try {
      const r = await fetch(e.request);
      if (r.ok && (SHELL.includes(url.pathname) || url.pathname.startsWith("/fonts/"))) {
        const c = await caches.open(CACHE); c.put(e.request, r.clone());
      }
      return r;
    } catch (err) {
      return (await caches.match(e.request)) || (await caches.match("/")) || Response.error();
    }
  })());
});

self.addEventListener("push", (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = { title: "Archie", body: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(d.title || "Archie", {
    body: d.body || "", icon: "/icon-192.png", badge: "/badge-96.png", tag: d.tag || undefined,
    data: { tab: d.tab || "today", url: d.url || "" }, renotify: true }));
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const tab = (e.notification.data && e.notification.data.tab) || "today";
  const url = e.notification.data && e.notification.data.url;
  if (url) return e.waitUntil(self.clients.openWindow(url));   // an email: straight to it in Gmail
  e.waitUntil((async () => {
    const all = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const c of all) { if ("focus" in c) { c.postMessage({ tab }); return c.focus(); } }
    return self.clients.openWindow("/#" + tab);
  })());
});
