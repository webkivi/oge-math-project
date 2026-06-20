import { Button } from '../../components/Button'
import { StepDots } from '../../components/StepDots'
import { TextField } from '../../components/TextField'
import type { UseRegistration } from '../../hooks/useRegistration'
import { ru } from '../../i18n/ru'

// Экран name_entry (reg_v2 / А6 §3.1). «Дальше» неактивна, пока имя пустое (RC-02).
// Назад с первого шага = отмена (по FSM evt_back из name_entry невозможен) — здесь
// первый шаг без «Назад».
export function NameEntry({ reg }: { reg: UseRegistration }) {
  const canProceed = reg.name.trim().length > 0
  return (
    <div className="flex flex-1 flex-col">
      <header className="pt-8">
        <StepDots total={3} current={0} />
        <h1 className="mt-4 text-title text-ink">{ru.reg.name.title}</h1>
      </header>
      <main className="flex-1 py-6">
        <TextField
          value={reg.name}
          onValueChange={reg.setName}
          placeholder={ru.reg.name.placeholder}
          hint={ru.reg.name.hint}
          autoFocus
        />
      </main>
      <footer className="pb-[max(16px,env(safe-area-inset-bottom))] pt-2">
        <Button onClick={reg.submitName} disabled={!canProceed}>
          {ru.btn.next}
        </Button>
      </footer>
    </div>
  )
}
