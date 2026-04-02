const CACHE_NAME = 'obz-cache-v1';

self.addEventListener('install', (e) => {
  console.log('[PWA] Service Worker instalado.');
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  console.log('[PWA] Service Worker ativado.');
  e.waitUntil(clients.claim());
});

self.addEventListener('fetch', (e) => {
    e.respondWith(fetch(e.request));
});
