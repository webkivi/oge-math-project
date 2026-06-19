import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
import './index.css'
import { registerServiceWorker } from './pwa'

const root = document.getElementById('root')
if (!root) {
  throw new Error('Не найден контейнер #root в index.html')
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

registerServiceWorker()
