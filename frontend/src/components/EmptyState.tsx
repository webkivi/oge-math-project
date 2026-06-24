// EmptyState — А6 §2. Пустой день / нет уроков сегодня (daily_done/course_complete).
// Приглашение к действию, не «мудборд» (§2) — опциональный слот action; текст —
// на стороне вызывающего экрана (А8 §2: ru.day.doneBody).
import type { ReactNode } from 'react'

interface EmptyStateProps {
  children: ReactNode
  action?: ReactNode
}

export function EmptyState({ children, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-card bg-surface p-6 text-center text-body text-ink">
      <p>{children}</p>
      {action}
    </div>
  )
}
