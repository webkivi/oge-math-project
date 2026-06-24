// ConnectionStub — А6 §2 (D-5). Нет соединения / контент не в кэше. Прогресс не
// теряется (без потери прогресса — v4 D-5); повтор автоматический при возврате сети,
// без ручной кнопки «Повторить» (А6 §5: «возобновление при сети»).
import { ru } from '../i18n/ru'

interface ConnectionStubProps {
  variant?: 'offline' | 'content-missing'
}

export function ConnectionStub({ variant = 'offline' }: ConnectionStubProps) {
  const isOffline = variant === 'offline'
  return (
    <div
      role="status"
      className="flex flex-col gap-2 rounded-card bg-surface p-5 text-center text-body text-ink"
    >
      {isOffline && <p className="text-lead">{ru.system.offlineTitle}</p>}
      <p>{isOffline ? ru.system.offlineBody : ru.system.lessonLoadError}</p>
    </div>
  )
}
