/* ArtSpace — service worker (добавлен патчем).
   Страницы и скрипты: сначала сеть, при отсутствии сети — кэш (правки сразу видны).
   Картинки и шрифты: сначала кэш, затем сеть — повторные заходы грузятся мгновенно. */
const V = 'artspace-v1';
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const r = e.request;
  if (r.method !== 'GET') return;
  const u = new URL(r.url);
  const isMedia = r.destination === 'image' || /\.(svg|jpe?g|png|webp|avif)$/i.test(u.pathname) || u.hostname === 'images.unsplash.com';
  const isFont = u.hostname === 'fonts.gstatic.com' || r.destination === 'font';
  if (isMedia || isFont) {
    e.respondWith(caches.open(V).then(c => c.match(r).then(hit => hit || fetch(r).then(res => {
      if (res && (res.ok || res.type === 'opaque')) c.put(r, res.clone());
      return res;
    }).catch(() => hit || Response.error()))));
    return;
  }
  if (u.origin === location.origin) {
    e.respondWith(fetch(r).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(V).then(c => c.put(r, copy)); }
      return res;
    }).catch(() => caches.match(r).then(h => h || caches.match('404.html') || Response.error())));
  }
});