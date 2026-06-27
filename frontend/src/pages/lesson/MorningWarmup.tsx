// morning_warmup — А6 §3.2 (WarmupRunner): 3 коротких interleaved-вопроса. «Пропустить
// разминку» — явный evt_warmup_skip-эквивалент (api v1 §2.5 п.5).
//
// Известный гап api v1 §4.6: resume (E7) прямо в morning_warmup не отдаёт активный
// R3-вопрос (Progress.current_message_id не привязан к разминке) — message=null.
// Самопочинка: один раз пробуем «пропустить», чтобы не зависнуть на пустом экране
// (см. spawn_task — предложение добить недостающий render на стороне backend).
import { useEffect, useRef } from 'react'

import { QuestionBlock } from '../../components/QuestionBlock'
import type { UseLesson } from '../../hooks/useLesson'
import { ru } from '../../i18n/ru'
import { toAnswerOptions } from './adapters'

export function MorningWarmup({ lesson }: { lesson: UseLesson }) {
  const message = lesson.render?.message ?? null
  const attemptedSkip = useRef(false)

  useEffect(() => {
    if (message === null && !attemptedSkip.current) {
      attemptedSkip.current = true
      void lesson.skipWarmup()
    }
  }, [message, lesson])

  if (message === null) return null

  return (
    <div className="flex flex-1 flex-col gap-5 py-6">
      <QuestionBlock
        textHtml={message.text_html}
        options={toAnswerOptions(message)}
        disabled={lesson.busy}
        onSelect={lesson.warmupSelect}
      />
      <button
        type="button"
        disabled={lesson.busy}
        onClick={lesson.skipWarmup}
        className="rounded-control text-option text-ink-secondary underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {ru.day.warmupSkip}
      </button>
    </div>
  )
}
