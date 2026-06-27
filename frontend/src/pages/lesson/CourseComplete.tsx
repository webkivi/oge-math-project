// course_complete — А6 §3.2. Поздравление; карта знаний/настройки — вне охвата.
import { EmptyState } from '../../components/EmptyState'
import { ru } from '../../i18n/ru'

export function CourseComplete() {
  return <EmptyState>{ru.course.completeBody}</EmptyState>
}
