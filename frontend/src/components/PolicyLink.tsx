import type { ReactNode } from 'react'

// PolicyLink — А6 §2. Ссылка на Политику обработки ПД. Состояния default/focus/
// unavailable (§1.5). При недоступности (RF-04) — неактивный текст, не ссылка.
// Текст/версия политики — Z-2 (юрист/А8), здесь только ссылка.
interface PolicyLinkProps {
  href: string
  available?: boolean
  children: ReactNode
}

export function PolicyLink({ href, available = true, children }: PolicyLinkProps) {
  if (!available) {
    return <span className="text-body text-disabled-text">{children}</span>
  }
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="rounded-[4px] text-body text-primary-active underline underline-offset-2 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusring focus-visible:ring-offset-2"
    >
      {children}
    </a>
  )
}
