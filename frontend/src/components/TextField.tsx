import type { InputHTMLAttributes } from 'react'
import { useId } from 'react'

// TextField — А6 §2. Ввод никнейма. Состояния empty/focus/filled/error/disabled (§1.5).
// Контролируемый: trim и валидация — на стороне экрана (RC-02), компонент показывает
// ошибку. Цвет ошибки — тёплая охра (--trap), не тревожный красный (§1.1).
interface TextFieldProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  'onChange' | 'value'
> {
  label?: string
  hint?: string
  error?: string
  value: string
  onValueChange: (value: string) => void
}

export function TextField({
  label,
  hint,
  error,
  value,
  onValueChange,
  disabled,
  id,
  ...rest
}: TextFieldProps) {
  const autoId = useId()
  const fieldId = id ?? autoId
  const hintId = `${fieldId}-hint`
  const errorId = `${fieldId}-error`
  const hasError = Boolean(error)
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label htmlFor={fieldId} className="text-caption text-ink-secondary">
          {label}
        </label>
      )}
      <input
        id={fieldId}
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        disabled={disabled}
        aria-invalid={hasError || undefined}
        aria-describedby={hasError ? errorId : hint ? hintId : undefined}
        className={[
          'min-h-12 rounded-control border bg-surface px-3 text-body text-ink',
          'placeholder:text-ink-muted',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusring focus-visible:ring-offset-1',
          'disabled:cursor-not-allowed disabled:bg-disabled disabled:text-disabled-text',
          hasError ? 'border-trap' : 'border-line',
        ].join(' ')}
        {...rest}
      />
      {hasError ? (
        <p id={errorId} className="text-caption text-trap-text">
          {error}
        </p>
      ) : (
        hint && (
          <p id={hintId} className="text-caption text-ink-muted">
            {hint}
          </p>
        )
      )}
    </div>
  )
}
