// AnswerButtons — А6 §2. Варианты A–D (тренировка и главный вопрос). Состояния
// default/focus/selected/correct/trap(неверно)/disabled-после-ответа (§1.5). Тач-таргет
// ≥44px. Выбор и итог дублируются НЕ только цветом — буква-метка + ✓/! (§5).
import { LessonHtml } from './LessonHtml'

export type AnswerLetter = 'A' | 'B' | 'C' | 'D'

export interface AnswerOption {
  letter: AnswerLetter
  textHtml: string
}

interface AnswerButtonsProps {
  options: AnswerOption[]
  selectedLetter?: AnswerLetter | null
  status?: 'idle' | 'answered'
  isCorrect?: boolean
  /** Блокирует выбор, пока ответ ещё в полёте к серверу (EC-01 анти-даблклик). */
  disabled?: boolean
  onSelect: (letter: AnswerLetter) => void
}

export function AnswerButtons({
  options,
  selectedLetter = null,
  status = 'idle',
  isCorrect = false,
  disabled = false,
  onSelect,
}: AnswerButtonsProps) {
  const answered = status === 'answered'
  return (
    <div role="radiogroup" aria-label="Варианты ответа" className="flex flex-col gap-3">
      {options.map((option) => {
        const isSelected = option.letter === selectedLetter
        const showCorrect = answered && isSelected && isCorrect
        const showTrap = answered && isSelected && !isCorrect
        return (
          <button
            key={option.letter}
            type="button"
            role="radio"
            aria-checked={isSelected}
            disabled={answered || disabled}
            onClick={() => onSelect(option.letter)}
            className={[
              'flex min-h-12 w-full items-center gap-3 rounded-control border px-4 py-3 text-left text-option text-ink transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusring focus-visible:ring-offset-2',
              'disabled:cursor-not-allowed',
              showCorrect
                ? 'border-2 border-correct bg-correct-bg text-correct-text'
                : showTrap
                  ? 'border-2 border-trap bg-trap-bg text-trap-text'
                  : isSelected
                    ? 'border-2 border-primary bg-sunken'
                    : 'border-line bg-surface hover:bg-sunken disabled:hover:bg-surface',
            ].join(' ')}
          >
            <span
              aria-hidden
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-pill border border-line text-caption"
            >
              {option.letter}
            </span>
            <LessonHtml html={option.textHtml} className="flex-1" />
            {showCorrect && <span aria-hidden>✓</span>}
            {showTrap && <span aria-hidden>!</span>}
          </button>
        )
      })}
    </div>
  )
}
