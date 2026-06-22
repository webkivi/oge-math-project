import { Button } from '../../components/Button'
// TODO[before-pilot]: вернуть import { Checkbox } — БЛОКЕР, 152-ФЗ (см. ниже)
import { InfoBanner } from '../../components/InfoBanner'
import { PolicyLink } from '../../components/PolicyLink'
import { ScreenHeading } from '../../components/ScreenHeading'
import { StepDots } from '../../components/StepDots'
import type { UseRegistration } from '../../hooks/useRegistration'
import { ru } from '../../i18n/ru'

// Экран consent_gate (reg_v2 / А6 §3.1). Опциональный информер для grade=9 (UI-информер
// вне FSM). Чекбокс согласия обязателен и недоступен, пока политика не загрузилась
// (RC-03/RF-04). «Начать» неактивна, пока guard не выполнен; loading блокирует
// повторный сабмит (RC-01). При ошибке submit остаёмся здесь (RF-01/RF-02).
export function ConsentGate({ reg }: { reg: UseRegistration }) {
  return (
    <div className="flex flex-1 flex-col">
      <header className="pt-8">
        <StepDots total={3} current={2} />
        <ScreenHeading className="mt-4">{ru.reg.consent.title}</ScreenHeading>
      </header>
      <main className="flex flex-1 flex-col gap-4 py-6">
        {reg.grade === 9 && <InfoBanner>{ru.reg.consent.informer9}</InfoBanner>}
        <PolicyLink href={reg.policyUrl ?? '#'} available={reg.policyAvailable}>
          {ru.reg.consent.policyLink}
        </PolicyLink>
        {/* TODO[before-pilot]: вернуть согласие ПД — БЛОКЕР перед пилотом, 152-ФЗ. Сейчас отключено для UX-теста фаундера. */}
        {/* <Checkbox
          checked={reg.consent}
          disabled={!reg.policyAvailable}
          onCheckedChange={reg.setConsent}
        >
          {ru.reg.consent.checkbox}
        </Checkbox>
        {!reg.policyAvailable && (
          <p className="text-caption text-trap-text">
            {ru.reg.consent.policyUnavailable}
          </p>
        )} */}
        {reg.error && (
          <p role="alert" className="text-caption text-trap-text">
            {reg.error}
          </p>
        )}
      </main>
      <footer className="flex flex-col gap-3 pb-[max(16px,env(safe-area-inset-bottom))] pt-2">
        <Button onClick={reg.submit} disabled={!reg.canSubmit} loading={reg.submitting}>
          {ru.btn.start}
        </Button>
        <Button variant="ghost" onClick={reg.back}>
          {ru.btn.back}
        </Button>
      </footer>
    </div>
  )
}
