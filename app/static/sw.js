// 律师工作台 Service Worker — 仅缓存静态外壳，应用数据始终走网络。
const CACHE = 'legal-copilot-shell-v1';
const SHELL = ['/app/static/manifest.json', '/app/static/icon-192.png', '/app/static/icon-512.png'];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {}));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  // Streamlit 的 WebSocket / 数据请求不缓存；只缓存本应用静态资源
  if (url.pathname.indexOf('/app/static/') !== 0) return;
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req))
  );
});
