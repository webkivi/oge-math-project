import type { ReactNode } from 'react'
import { useId } from 'react'

// Checkbox — А6 §2. Согласие на ПД (обязательно). Состояния unchecked/checked/focus/
// disabled (§1.5). Сабмит неактивен, пока unchecked (RC-03); недоступен, пока политика
// не загрузилась (RF-04) — через disabled. Клик по подписи тоже переключает (хит-зона).
interface CheckboxProps {
  checked: boolean
  disabled?: boolean
  onCheckedChange: (checked: boolean) => void
  children: ReactNode
}

export function Checkbox({
  checked,
  disabled = false,
  onCheckedChange,
  children,
}: CheckboxProps) {
  const id = useId()
  return (
    <div className="flex items-start gap-3">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onCheckedChange(event.target.checked)}
        className={[
          'mt-0.5 h-6 w-6 shrink-0 rounded-[6px] border-line accent-primary',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusring focus-visible:ring-offset-2',
          'disabled:cursor-not-allowed disabled:opacity-50',
        ].join(' ')}
      />
      <label
        htmlFor={id}
        className={['text-body', disabled ? 'text-disabled-text' : 'text-ink'].join(
          ' ',
        )}
      >
        {children}
      </label>
    </div>
  )
}
