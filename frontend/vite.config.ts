/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev-сервер на :5173; /api проксируется на бэкенд FastAPI (uvicorn :8000), чтобы
// запросы регистрации и httpOnly-cookie работали из PWA без CORS (reg api E1/E2/E3,
// пункт 5 плана — npm run dev + uvicorn вместе).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  test: {
    // Тесты компонентов: jsdom + @testing-library; матчеры jest-dom — в setup.
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
