// repeat_1h_pending / repeat_evening_pending — А6 §3.2. Информирование, не действие;
// без точного «через N минут» (api v1 render не отдаёт остаток времени в этом срезе,
// см. ru.repeat.pendingGeneric — намеренно нейтральный текст, не выдуманное число).
import { PendingNotice } from '../../components/PendingNotice'
import { ru } from '../../i18n/ru'

export function RepeatPending() {
  return <PendingNotice>{ru.repeat.pendingGeneric}</PendingNotice>
}
