// 小克的家 service worker.
// Caches only the app shell so the home-screen app opens instantly and still
// shows its UI offline. API calls, live streams and uploads always go to the
// network and are never cached.
const SHELL_CACHE = 'xk-shell-v1';
const SHELL = [
  '/',
  '/static/chat-page.js',
  '/static/chat-md.js',
  '/static/chat-code.js',
  '/static/pwa.js',
  '/static/theme.css',
  '/static/vendor/xterm/xterm.css',
  '/static/vendor/xterm/xterm.js',
  '/static/vendor/xterm/addon-fit.js',
  '/static/vendor/xterm/xterm-addon-web-links.js',
  '/static/vendor/xterm/addon-unicode-graphemes.js',
  '/static/vendor/hljs/highlight.min.js',
  '/static/vendor/cropper.min.js',
  '/static/vendor/cropper.min.css',
  '/static/icons/apple-touch-icon.png',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then(cache => Promise.all(SHELL.map(url => cache.add(url).catch(() => {}))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k.startsWith('xk-shell-') && k !== SHELL_CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Network first (so updates land immediately), cache as the offline fallback.
self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;
  const isShell = req.mode === 'navigate' || url.pathname === '/' || url.pathname === '/app' || url.pathname.startsWith('/static/');
  if (!isShell) return;
  event.respondWith(
    fetch(req).then(res => {
      if (res.ok) {
        const copy = res.clone();
        caches.open(SHELL_CACHE).then(c => c.put(req.mode === 'navigate' ? '/' : req, copy));
      }
      return res;
    }).catch(() => caches.match(req.mode === 'navigate' ? '/' : req).then(r => r || Response.error()))
  );
});
