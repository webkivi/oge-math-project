import { Button } from '../../components/Button'
import type { UseRegistration } from '../../hooks/useRegistration'
import { ru } from '../../i18n/ru'

// Экран gate_grade8 (production, reg_v2 / А6 §3.1). Тёплый, не наказывающий: аккаунт
// НЕ создаётся (D-6). «Понятно» → unregistered (draft уничтожен).
export function GateGrade8({ reg }: { reg: UseRegistration }) {
  return (
    <div className="flex flex-1 flex-col">
      <main className="flex flex-1 flex-col justify-center py-6">
        <p className="text-body text-ink">{ru.reg.gate8.body}</p>
      </main>
      <footer className="pb-[max(16px,env(safe-area-inset-bottom))] pt-2">
        <Button autoFocus onClick={reg.dismissGate}>
          {ru.btn.ok}
        </Button>
      </footer>
    </div>
  )
}
