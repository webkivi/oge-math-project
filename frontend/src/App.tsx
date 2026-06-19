import type { ReactNode } from 'react'

/**
 * Базовый layout ученической PWA (А6 §1.3): одна колонка, mobile-first, контентная
 * ширина 440px по центру, боковые поля 16px, нижняя «зона действия» в безопасной зоне.
 * Экраны регистрации и урока (пункты 3–4) лягут внутрь этого каркаса.
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
      <header className="pt-8">
        <h1 className="text-title text-ink">ОГЭ по математике</h1>
        <p className="mt-2 text-lead text-ink-secondary">
          на тройку — по 15 минут в день
        </p>
      </header>

      <main className="flex flex-1 flex-col gap-4 py-6">
        <p className="text-body text-ink">
          Каркас интерфейса готов. Экраны регистрации появятся в следующем пункте.
        </p>

        {/* Демонстрация токенов А6 §1 — визуальная проверка, что дизайн-система применяется. */}
        <section className="rounded-card bg-surface p-4 shadow-sm">
          <p className="text-caption text-ink-muted">Дизайн-токены</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded-pill bg-primary px-3 py-1 text-caption text-white">
              действие
            </span>
            <span className="rounded-pill bg-correct-bg px-3 py-1 text-caption text-correct-text">
              верно
            </span>
            <span className="rounded-pill bg-trap-bg px-3 py-1 text-caption text-trap-text">
              типичная ловушка
            </span>
          </div>
        </section>
      </main>

      <footer className="pb-[max(16px,env(safe-area-inset-bottom))] pt-2">
        {/* Главное действие — состояния hover/active/focus по А6 §1.5; тач-таргет ≥48px. */}
        <button
          type="button"
          className="h-12 w-full rounded-control bg-primary text-option text-white transition-colors hover:bg-primary-hover active:translate-y-px active:bg-primary-active focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusring focus-visible:ring-offset-2"
        >
          Дальше
        </button>
      </footer>
    </AppShell>
  )
}
