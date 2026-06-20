import type { ReactNode } from 'react'

import { Onboarding } from './pages/Onboarding'

/**
 * Базовый layout ученической PWA (А6 §1.3): одна колонка, mobile-first, контентная
 * ширина 440px по центру, боковые поля 16px. Сейчас внутри — поток регистрации
 * (пункт 4). Демо-галерея компонентов осталась в src/dev/Gallery.tsx как dev-артефакт.
 */
function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-canvas font-sans text-ink">
      <div className="mx-auto flex min-h-dvh w-full max-w-content flex-col px-4">
        {children}
      </div>
    </div>
  )
}

export default function App() {
  return (
    <AppShell>
      <Onboarding />
    </AppShell>
  )
}
