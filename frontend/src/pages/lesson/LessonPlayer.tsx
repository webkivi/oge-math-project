// Прохождение урока — А6 §3.2 (hook→theory→example→training→main_question→
// [theory_review→backup]→final). Один render-payload несёт либо вопрос (options
// присутствуют → QuestionBlock), либо проходной экран (MessageCard+«Дальше»), плюс
// опционально feedback сверху (api v1 §4.5: «wrong с возвратом» — feedback+message
// в одном payload). lesson_failed — отдельная ветка (DeferCard, без feedback-рамки).
//
// resumable (api v1 §4.6, fsm_state="registered" после S-10 cancel): E7 отдаёт
// сохранённое сообщение, но текущий fsm_state — registered, НЕ lesson_*. advance/
// select/cancel рассчитаны на lesson_*-стадии (backend/services/fsm_service.py
// _ADVANCE_EVENT/_QUESTION_STATES/_dispatch) и ответят 409 wrong_action_for_stage,
// если их вызвать из registered — единственный документированный путь обратно в
// урок — E8 (startLesson), он находит тот же незавершённый урок по манифесту.
// Поэтому в resumable-режиме экран read-only (без AnswerButtons/«Выйти из урока»),
// единственное действие — «Продолжить» → startNextLesson().
import { AnswerFeedback } from '../../components/AnswerFeedback'
import { Button } from '../../components/Button'
import { DeferCard } from '../../components/DeferCard'
import { LessonProgress } from '../../components/LessonProgress'
import { MessageCard } from '../../components/MessageCard'
import { QuestionBlock } from '../../components/QuestionBlock'
import type { UseLesson } from '../../hooks/useLesson'
import { ru } from '../../i18n/ru'
import { toAnswerOptions } from './adapters'

export function LessonPlayer({ lesson }: { lesson: UseLesson }) {
  const render = lesson.render
  if (render === null || render.message === null) return null
  const { view, message, feedback, lesson_progress: progress, resumable } = render

  if (resumable) {
    return (
      <div className="flex flex-1 flex-col gap-5 py-6">
        <MessageCard textHtml={message.text_html} />
        <Button onClick={lesson.startNextLesson} loading={lesson.busy}>
          {ru.btn.continueLesson}
        </Button>
      </div>
    )
  }

  const isQuestion = (message.options ?? []).length > 0

  return (
    <div className="flex flex-1 flex-col gap-5">
      <header className="flex items-center justify-between pt-6">
        <button
          type="button"
          onClick={lesson.exitLesson}
          className="rounded-control text-option text-primary-active underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusring focus-visible:ring-offset-2"
        >
          {ru.btn.exitLesson}
        </button>
        {progress && <LessonProgress step={progress.step} total={progress.total} />}
      </header>
      <main className="flex flex-1 flex-col gap-5 py-2">
        {view === 'lesson_failed' ? (
          <DeferCard onConfirm={lesson.advance} />
        ) : (
          <>
            {feedback && (
              <AnswerFeedback
                isCorrect={feedback.is_correct}
                feedbackHtml={feedback.feedback_html}
              />
            )}
            {isQuestion ? (
              <QuestionBlock
                textHtml={message.text_html}
                options={toAnswerOptions(message)}
                disabled={lesson.busy}
                onSelect={lesson.select}
              />
            ) : (
              <>
                <MessageCard textHtml={message.text_html} />
                <Button onClick={lesson.advance} loading={lesson.busy}>
                  {ru.btn.next}
                </Button>
              </>
            )}
          </>
        )}
      </main>
    </div>
  )
}
