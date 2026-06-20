import type { ReactNode } from 'react'

// InfoBanner — А6 §2. Информирует, НЕ блокирует (§1.4): grade=8-предупреждение
// (staging), самооценка grade=9 в consent_gate. Спокойная утопленная подложка,
// не тревожный цвет. role="note" — вспомогательная заметка для скринридера.
interface InfoBannerProps {
  children: ReactNode
}

export function InfoBanner({ children }: InfoBannerProps) {
  return (
    <div
      role="note"
      className="rounded-control bg-sunken px-4 py-3 text-caption text-ink-secondary"
    >
      {children}
    </div>
  )
}
