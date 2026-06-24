// DayCounterBadge — А6 §2 (F-1). «N дней подряд» — тихий, вторичный элемент: мелко,
// без анимаций-«фейерверков», без сравнения с другими (Methodology §1.3). Заметность —
// развилка фаундера (F-1, НЕ закрыта); дефолт student_lesson_api_v1 §4.1 (R2-№5) —
// тихий/скрытый показ, fail-safe в сторону «без давления». Слово только «дни подряд».
import { ru } from '../i18n/ru'

interface DayCounterBadgeProps {
  days: number
  /** Передышка (S-07): счётчик сохранён, без чувства долга — заменяет обычный текст. */
  pauseApplied?: boolean
}

export function DayCounterBadge({ days, pauseApplied = false }: DayCounterBadgeProps) {
  if (pauseApplied) {
    return <p className="text-caption text-ink-muted">{ru.day.streakPause}</p>
  }
  return (
    <span className="inline-flex items-center rounded-pill bg-sunken px-2.5 py-1 text-caption text-ink-muted">
      {ru.dayCounterBadge(days)}
    </span>
  )
}
