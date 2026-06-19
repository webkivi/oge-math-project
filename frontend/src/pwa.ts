// Регистрация service worker (PWA-офлайн: А6 §5, Brain §5.1). В dev НЕ регистрируем,
// чтобы кэш SW не мешал горячей перезагрузке Vite; включается только в production-сборке.
export function registerServiceWorker(): void {
  if (import.meta.env.PROD && 'serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {
        // Офлайн-оболочка не критична для первого запуска — молча игнорируем.
      })
    })
  }
}
