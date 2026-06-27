// Адаптер wire-формата (snake_case, api v1 §4.1) → формат компонентов А6 §2
// (camelCase). Чисто UI-слой — НЕ часть api/lessonClient.ts (тот не знает о
// конкретных компонентах).
import type { AnswerOption } from '../../components/AnswerButtons'
import type { LessonMessageWire } from '../../api/lessonClient'

export function toAnswerOptions(message: LessonMessageWire): AnswerOption[] {
  return (message.options ?? []).map((option) => ({
    letter: option.letter,
    textHtml: option.text_html,
  }))
}
