// daily_done — А6 §3.2. «На сегодня всё», без догоняющих предложений.
import { EmptyState } from '../../components/EmptyState'
import { ru } from '../../i18n/ru'

export function DailyDone() {
  return <EmptyState>{ru.day.doneBody}</EmptyState>
}
