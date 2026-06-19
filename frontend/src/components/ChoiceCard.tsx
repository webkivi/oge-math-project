import type { ReactNode } from 'react'

// ChoiceCard — А6 §2. Выбор класса (9–11 / staging 8–11) и ответ ОГЭ да/нет.
// Состояния default/hover/selected/focus/disabled (§1.5). Тач-таргет ≥44px (§5).
// Выбор дублируется НЕ только цветом — граница + галочка (доступность, §1.5).
interface ChoiceCardProps {
  selected?: boolean
  disabled?: boolean
  onSelect: () => void
  children: ReactNode
}

export function ChoiceCard({
  selected = false,
  disabled = false,
  onSelect,
  children,
}: ChoiceCardProps) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      disabled={disabled}
      onClick={onSelect}
      className={[
        'flex min-h-12 w-full items-center justify-between gap-3 rounded-control border px-4 py-3 text-left text-option text-ink transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusring focus-visible:ring-offset-2',
        'disabled:cursor-not-allowed disabled:bg-disabled disabled:text-disabled-text',
        selected
          ? 'border-2 border-primary bg-correct-bg'
          : 'border-line bg-surface hover:bg-sunken',
      ].join(' ')}
    >
      <span>{children}</span>
      <span aria-hidden className={selected ? 'text-primary' : 'text-transparent'}>
        ✓
      </span>
    </button>
  )
}
