import { Button } from '../../components/Button'
import { ChoiceCard } from '../../components/ChoiceCard'
import { ScreenHeading } from '../../components/ScreenHeading'
import type { UseRegistration } from '../../hooks/useRegistration'
import { ru } from '../../i18n/ru'

// Экран ogeprep_check (только grade 10/11, reg_v2 / А6 §3.1). Да → consent (впуск
// как пересдача); Нет → course_mismatch (информер, без блокировки).
export function OgeprepCheck({ reg }: { reg: UseRegistration }) {
  return (
    <div className="flex flex-1 flex-col">
      <header className="pt-8">
        <ScreenHeading>{ru.reg.ogeprep.question}</ScreenHeading>
      </header>
      <main className="flex flex-1 flex-col gap-3 py-6">
        <ChoiceCard onSelect={reg.ogeprepYes}>{ru.reg.ogeprep.yes}</ChoiceCard>
        <ChoiceCard onSelect={reg.ogeprepNo}>{ru.reg.ogeprep.no}</ChoiceCard>
      </main>
      <footer className="pb-[max(16px,env(safe-area-inset-bottom))] pt-2">
        <Button variant="ghost" onClick={reg.back}>
          {ru.btn.back}
        </Button>
      </footer>
    </div>
  )
}
