// MessageCard — А6 §2. Рендер одного HTML-сообщения урока из CSV (хук/теория/
// образец/финал, student_lesson_api_v1 §4.1 `message.text_html`). ≤6 строк/экран —
// длиной контента, не размером шрифта (А6 §1.2). Изображение (чертёж блок 5) —
// часть text_html, без отдельного состояния компонента. Рендер HTML — через LessonHtml
// (единая точка доверия к CSV-контенту, см. её комментарий).
import { LessonHtml } from './LessonHtml'

interface MessageCardProps {
  textHtml: string
}

export function MessageCard({ textHtml }: MessageCardProps) {
  return (
    <LessonHtml
      html={textHtml}
      className="rounded-card bg-surface p-4 text-body text-ink [&_img]:mt-3 [&_img]:max-w-full [&_img]:rounded-control"
    />
  )
}
