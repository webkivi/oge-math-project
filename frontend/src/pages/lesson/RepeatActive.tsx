// repeat_1h_active / repeat_evening_active — А6 §3.2. Один короткий вопрос R1/R2.
// Судейство — только для feedback (api v1 §2.3); переход по факту ответа, не по
// correctness, поэтому backend сразу отдаёт следующий hub/pending-render без
// промежуточного feedback-экрана (см. fsm_service.repeat_answer: message=None).
import { QuestionBlock } from '../../components/QuestionBlock'
import type { UseLesson } from '../../hooks/useLesson'
import { toAnswerOptions } from './adapters'

export function RepeatActive({ lesson }: { lesson: UseLesson }) {
  const message = lesson.render?.message
  if (!message) return null
  return (
    <div className="flex flex-1 flex-col gap-5 py-6">
      <QuestionBlock
        textHtml={message.text_html}
        options={toAnswerOptions(message)}
        disabled={lesson.busy}
        onSelect={lesson.repeatSelect}
      />
    </div>
  )
}
