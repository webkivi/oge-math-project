// DeferCard — А6 §2. Экран «отложим до завтра» (lesson_failed / daily_blocked).
// Спокойный тон, без вины (§1.3); «Понятно» → evt_lesson_fail_confirmed (v4 §2б).
import { Button } from './Button'
import { ru } from '../i18n/ru'

interface DeferCardProps {
  onConfirm: () => void
}

export function DeferCard({ onConfirm }: DeferCardProps) {
  return (
    <div className="flex flex-col gap-5 rounded-card bg-surface p-5 text-body text-ink">
      <p>{ru.lesson.failed.body}</p>
      <Button variant="primary" onClick={onConfirm}>
        {ru.btn.ok}
      </Button>
    </div>
  )
}
