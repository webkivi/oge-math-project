// QuestionBlock — А6 §2. Текст вопроса + AnswerButtons A–D (тренировка и главный
// вопрос). Один вопрос = один экран. Состояния idle/answered проксируются в AnswerButtons.
import { AnswerButtons } from './AnswerButtons'
import type { AnswerLetter, AnswerOption } from './AnswerButtons'
import { LessonHtml } from './LessonHtml'

interface QuestionBlockProps {
  textHtml: string
  options: AnswerOption[]
  selectedLetter?: AnswerLetter | null
  status?: 'idle' | 'answered'
  isCorrect?: boolean
  onSelect: (letter: AnswerLetter) => void
}

export function QuestionBlock({
  textHtml,
  options,
  selectedLetter,
  status,
  isCorrect,
  onSelect,
}: QuestionBlockProps) {
  return (
    <div className="flex flex-col gap-5">
      <LessonHtml
        html={textHtml}
        className="rounded-card bg-surface p-4 text-body text-ink"
      />
      <AnswerButtons
        options={options}
        selectedLetter={selectedLetter}
        status={status}
        isCorrect={isCorrect}
        onSelect={onSelect}
      />
    </div>
  )
}
