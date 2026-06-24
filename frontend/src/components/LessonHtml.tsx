// LessonHtml — общая точка рендера HTML-контента урока из CSV (text_html/feedback_X/
// option-text). Единственное место, где используется dangerouslySetInnerHTML для
// контента урока (MessageCard/QuestionBlock/AnswerButtons/AnswerFeedback) — если
// потребуется санитайзинг на клиенте (defense-in-depth поверх keeper.py), правится
// в одном месте, а не в четырёх. Источник доверия: text_html — авторский контент из
// CSV, проверенный keeper.py (CLAUDE.md §3, v4 §1 lesson_content/read), а НЕ
// пользовательский ввод.
interface LessonHtmlProps {
  html: string
  className?: string
}

export function LessonHtml({ html, className }: LessonHtmlProps) {
  return <div className={className} dangerouslySetInnerHTML={{ __html: html }} />
}
