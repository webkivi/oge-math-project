import { Button } from '../../components/Button'
import type { UseRegistration } from '../../hooks/useRegistration'
import { ru } from '../../i18n/ru'

// Экран course_mismatch (только из ogeprep «нет», reg_v2 / А6 §3.1). Информирует,
// НЕ блокирует (§1.4): две равноправные кнопки, уход свободен (RC-12).
export function CourseMismatch({ reg }: { reg: UseRegistration }) {
  return (
    <div className="flex flex-1 flex-col">
      <main className="flex flex-1 flex-col justify-center py-6">
        <p className="text-body text-ink">{ru.reg.mismatch.body}</p>
      </main>
      <footer className="flex flex-col gap-3 pb-[max(16px,env(safe-area-inset-bottom))] pt-2">
        <Button autoFocus onClick={reg.mismatchContinue}>
          {ru.reg.mismatch.continue}
        </Button>
        <Button variant="ghost" onClick={reg.mismatchLeave}>
          {ru.reg.mismatch.leave}
        </Button>
      </footer>
    </div>
  )
}
