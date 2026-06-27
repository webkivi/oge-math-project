// daily_start — А6 §3.2. Хаб дня, одна мысль: «твой сегодняшний шаг». CTA зависит от
// наличия due-повторений (day.warmup_available): разминка или прямой переход в урок.
// DayCounterBadge — тихо, вторично (F-1). Карта знаний/Настройки — вне охвата (А6 §2).
import { Button } from '../../components/Button'
import { DayCounterBadge } from '../../components/DayCounterBadge'
import { ScreenHeading } from '../../components/ScreenHeading'
import type { UseLesson } from '../../hooks/useLesson'
import { ru } from '../../i18n/ru'

export function DailyStart({ lesson }: { lesson: UseLesson }) {
  const day = lesson.render?.day

  return (
    <div className="flex flex-1 flex-col">
      <header className="pt-8">
        {day && <DayCounterBadge days={day.streak_days} />}
        <ScreenHeading className="mt-4">{ru.day.start.greeting}</ScreenHeading>
      </header>
      <footer className="flex flex-1 flex-col justify-end gap-3 pb-[max(16px,env(safe-area-inset-bottom))] pt-2">
        <Button
          onClick={day?.warmup_available ? lesson.startWarmup : lesson.skipWarmup}
          loading={lesson.busy}
        >
          {day?.warmup_available ? ru.day.start.ctaWarmup : ru.day.start.ctaLesson}
        </Button>
      </footer>
    </div>
  )
}
