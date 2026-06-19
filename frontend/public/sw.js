// Минимальный service worker: оболочка онбординга кэшируется для офлайна
// (А6 §5, reg api RF-03). Полная офлайн-стратегия урока — отдельная задача.
const CACHE = 'oge-shell-v1'
const SHELL = ['/', '/index.html', '/manifest.json', '/icon.svg']

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)))
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))),
      ),
  )
  self.clients.claim()
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  // Запросы к /api не кэшируем (актуальность + ПД); кэшируем только GET-оболочку.
  if (request.method !== 'GET' || new URL(request.url).pathname.startsWith('/api')) {
    return
  }
  event.respondWith(caches.match(request).then((cached) => cached ?? fetch(request)))
})
