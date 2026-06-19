import type { ButtonHTMLAttributes, ReactNode } from 'react'

// Button — А6 §2. Варианты: primary (главное), secondary, ghost («Назад»/«Пропустить»),
// destructive (только «Удалить аккаунт»). Состояния §1.5; loading блокирует двойной
// сабмит (RC-01); тач-таргет ≥48px (§5).
type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  loading?: boolean
  children: ReactNode
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-white hover:bg-primary-hover active:bg-primary-active',
  secondary:
    'border border-line bg-surface text-ink hover:bg-sunken active:translate-y-px',
  ghost: 'bg-transparent text-ink-secondary hover:bg-sunken active:translate-y-px',
  destructive: 'bg-destructive text-white hover:opacity-90 active:translate-y-px',
}

export function Button({
  variant = 'primary',
  loading = false,
  disabled,
  children,
  className = '',
  type = 'button',
  ...rest
}: ButtonProps) {
  // loading трактуется как disabled — повторное нажатие «Начать» не уходит (RC-01).
  const isDisabled = disabled || loading
  return (
    <button
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={[
        'inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-control px-4 text-option transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusring focus-visible:ring-offset-2',
        'disabled:cursor-not-allowed disabled:bg-disabled disabled:text-disabled-text disabled:hover:bg-disabled',
        VARIANT_CLASSES[variant],
        className,
      ].join(' ')}
      {...rest}
    >
      {loading ? <Spinner /> : children}
    </button>
  )
}

function Spinner() {
  return (
    <span
      role="status"
      aria-label="Загрузка"
      className="h-5 w-5 animate-spin rounded-pill border-2 border-white/40 border-t-white motion-reduce:animate-none"
    />
  )
}
