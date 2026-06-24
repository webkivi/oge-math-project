// AnswerFeedback — А6 §2. Реакция на ответ: correct(--correct) / trap(--trap, спокойно,
// «типичная ловушка», НЕ красный — антипринцип §1.3). Лид-фраза — А8 §2 (lesson.feedback);
// feedbackHtml — feedback_X из CSV (return_X-разбор), не интерфейсный текст (А8 §6).
// role="status" — фидбэк озвучивается скринридеру без потери фокуса.
import { ru } from '../i18n/ru'
import { LessonHtml } from './LessonHtml'

interface AnswerFeedbackProps {
  isCorrect: boolean
  feedbackHtml: string
}

export function AnswerFeedback({ isCorrect, feedbackHtml }: AnswerFeedbackProps) {
  const lead = isCorrect ? ru.lesson.feedback.correctLead : ru.lesson.feedback.trapLead
  return (
    <div
      role="status"
      className={[
        'rounded-card border-2 p-4 text-body',
        isCorrect
          ? 'border-correct bg-correct-bg text-correct-text'
          : 'border-trap bg-trap-bg text-trap-text',
      ].join(' ')}
    >
      <p className="flex items-center gap-2 text-lead">
        <span aria-hidden>{isCorrect ? '✓' : '!'}</span>
        {lead}
      </p>
      <LessonHtml html={feedbackHtml} className="mt-1" />
    </div>
  )
}
