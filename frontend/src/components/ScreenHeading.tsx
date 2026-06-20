import type { ReactNode } from 'react'
import { useEffect, useRef } from 'react'

// Заголовок экрана с переводом фокуса на себя при монтировании (А6 §5: на смене
// экрана фокус — на заголовок, чтобы клавиатура/скринридер не теряли контекст).
// tabIndex=-1 делает заголовок программно-фокусируемым; визуального кольца не даём —
// это не интерактивный контрол, а точка приземления фокуса для SR.
interface ScreenHeadingProps {
  children: ReactNode
  className?: string
}

export function ScreenHeading({ children, className = '' }: ScreenHeadingProps) {
  const ref = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    ref.current?.focus()
  }, [])
  return (
    <h1
      ref={ref}
      tabIndex={-1}
      className={`text-title text-ink focus-visible:outline-none ${className}`.trim()}
    >
      {children}
    </h1>
  )
}
