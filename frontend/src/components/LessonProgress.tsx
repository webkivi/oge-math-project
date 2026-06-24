// LessonProgress — А6 §2/§3.2. Прогресс внутри урока (этап из 6, либо 5 при
// R3-авто-проскоке hook, когда стадии hook нет в CSV — student_lesson_api_v1 §4.5-R3).
// Тонкая полоса/точки; без «осталось N%» давления (§1.3). total — динамический
// (5 или 6), не фиксированный — встречная правка А6 §3.2 на приёмку (api v1 §4.5-R3).
interface LessonProgressProps {
  step: number
  total: number
}

export function LessonProgress({ step, total }: LessonProgressProps) {
  return (
    <div
      role="group"
      aria-label={`Этап ${step} из ${total}`}
      className="flex items-center gap-1.5"
    >
      {Array.from({ length: total }, (_, index) => {
        const isDone = index < step
        return (
          <span
            key={index}
            aria-hidden
            className={[
              'h-1.5 flex-1 rounded-pill transition-colors',
              isDone ? 'bg-primary' : 'bg-line-subtle',
            ].join(' ')}
          />
        )
      })}
    </div>
  )
}
