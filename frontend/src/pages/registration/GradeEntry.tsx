import { useState } from 'react'

import { Button } from '../../components/Button'
import { ChoiceCard } from '../../components/ChoiceCard'
import { InfoBanner } from '../../components/InfoBanner'
import { ScreenHeading } from '../../components/ScreenHeading'
import { StepDots } from '../../components/StepDots'
import type { UseRegistration } from '../../hooks/useRegistration'
import { ru } from '../../i18n/ru'

// Экран grade_entry (reg_v2 / А6 §3.1). Выбор класса сразу ведёт дальше (9 → consent,
// 10/11 → ogeprep). grade=8 показывается ТОЛЬКО вне production (А6: «в production 8
// отсутствует»); выбор 8 показывает предупреждение и требует явного подтверждения
// (staging-аффорданс). В production гейт grade=8 — на бэкенде (RC-04) и в FSM.
export function GradeEntry({ reg }: { reg: UseRegistration }) {
  const [warn8, setWarn8] = useState(false)
  return (
    <div className="flex flex-1 flex-col">
      <header className="pt-8">
        <StepDots total={3} current={1} />
        <ScreenHeading className="mt-4">{ru.reg.grade.title}</ScreenHeading>
      </header>
      <main className="flex flex-1 flex-col gap-3 py-6">
        <ChoiceCard onSelect={() => reg.selectGrade(9)}>{ru.reg.grade.opt9}</ChoiceCard>
        <ChoiceCard onSelect={() => reg.selectGrade(10)}>
          {ru.reg.grade.opt10}
        </ChoiceCard>
        <ChoiceCard onSelect={() => reg.selectGrade(11)}>
          {ru.reg.grade.opt11}
        </ChoiceCard>
        {!reg.isProduction && (
          <>
            <ChoiceCard selected={warn8} onSelect={() => setWarn8(true)}>
              {ru.reg.grade.opt8}
            </ChoiceCard>
            {warn8 && (
              <>
                <InfoBanner>{ru.reg.grade.warn8Body}</InfoBanner>
                <Button variant="secondary" onClick={() => reg.selectGrade(8)}>
                  {ru.reg.grade.warn8Continue}
                </Button>
              </>
            )}
          </>
        )}
      </main>
      <footer className="pb-[max(16px,env(safe-area-inset-bottom))] pt-2">
        <Button variant="ghost" onClick={reg.back}>
          {ru.btn.back}
        </Button>
      </footer>
    </div>
  )
}
