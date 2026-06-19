// StepDots — А6 §2. Индикатор шага регистрации (имя → класс → согласие). Состояния
// текущий/пройден/будущий. Без процентов и давления — просто «где я». Прогресс
// озвучивается скринридеру через aria-label группы (§5).
interface StepDotsProps {
  total: number
  /** Индекс текущего шага (0-based). */
  current: number
  label?: string
}

export function StepDots({ total, current, label = 'Шаг' }: StepDotsProps) {
  return (
    <div
      role="group"
      aria-label={`${label} ${current + 1} из ${total}`}
      className="flex items-center gap-2"
    >
      {Array.from({ length: total }, (_, index) => {
        const isCurrent = index === current
        const isDone = index < current
        return (
          <span
            key={index}
            aria-hidden
            className={[
              'h-2 rounded-pill transition-all',
              isCurrent ? 'w-6 bg-primary' : 'w-2',
              isDone ? 'bg-primary/60' : '',
              !isCurrent && !isDone ? 'bg-line-subtle' : '',
            ].join(' ')}
          />
        )
      })}
    </div>
  )
}
