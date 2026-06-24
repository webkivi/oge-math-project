// PendingNotice — А6 §2. Состояния ожидания повторения (r1_pending/evening_pending/
// daily_blocked-самопетля). Информирование, НЕ действие (§3.2) — никакой кнопки
// действия внутри, только текст. Текст — на стороне вызывающего экрана (А8 §2:
// ru.repeat.r1Pending(N) / ru.blocked.body), компонент текст не диктует.
import type { ReactNode } from 'react'

interface PendingNoticeProps {
  children: ReactNode
}

export function PendingNotice({ children }: PendingNoticeProps) {
  return (
    <div
      role="status"
      className="rounded-card bg-sunken p-4 text-body text-ink-secondary"
    >
      {children}
    </div>
  )
}
