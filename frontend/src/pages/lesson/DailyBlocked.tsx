// daily_blocked — А6 §3.2. Новый урок завтра; сегодня — только разминка/повторения.
// Самопетля FSM (evt_open_app → daily_blocked), выход только по evt_next_day (scheduler).
import { PendingNotice } from '../../components/PendingNotice'
import { ru } from '../../i18n/ru'

export function DailyBlocked() {
  return <PendingNotice>{ru.blocked.body}</PendingNotice>
}
