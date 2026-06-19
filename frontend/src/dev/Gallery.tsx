import type { ReactNode } from 'react'
import { useState } from 'react'

import { Button } from '../components/Button'
import { Checkbox } from '../components/Checkbox'
import { ChoiceCard } from '../components/ChoiceCard'
import { PolicyLink } from '../components/PolicyLink'
import { StepDots } from '../components/StepDots'
import { TextField } from '../components/TextField'
import { ru } from '../i18n/ru'

// Демо-галерея компонентов А6 §2 — Storybook-like визуальная проверка состояний.
// Это НЕ экран продукта; в пункте 4 App будет роутить реальные экраны регистрации.
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3 border-b border-line-subtle py-6">
      <h2 className="text-lead text-ink">{title}</h2>
      <div className="flex flex-col gap-3">{children}</div>
    </section>
  )
}

export function Gallery() {
  const [name, setName] = useState('')
  const [grade, setGrade] = useState<number | null>(null)
  const [consent, setConsent] = useState(false)
  const [loading, setLoading] = useState(false)

  return (
    <div className="flex flex-col pb-[max(16px,env(safe-area-inset-bottom))]">
      <p className="pt-4 text-caption text-ink-muted">
        Демо-галерея компонентов А6 §2 — визуальная проверка состояний. Не экран
        продукта.
      </p>

      <Section title="StepDots — индикатор шага">
        <StepDots total={3} current={1} />
      </Section>

      <Section title="Button — варианты и состояния">
        <Button variant="primary">{ru.btn.start}</Button>
        <Button variant="secondary">{ru.btn.back}</Button>
        <Button variant="ghost">Пропустить разминку</Button>
        <Button variant="primary" disabled>
          {ru.btn.next} (disabled)
        </Button>
        <Button
          variant="primary"
          loading={loading}
          onClick={() => {
            setLoading(true)
            window.setTimeout(() => setLoading(false), 1500)
          }}
        >
          {ru.btn.start} (нажми → loading 1.5 c)
        </Button>
        <Button variant="destructive">Удалить аккаунт</Button>
      </Section>

      <Section title="TextField — ввод никнейма">
        <TextField
          label={ru.reg.name.title}
          hint={ru.reg.name.hint}
          placeholder={ru.reg.name.placeholder}
          value={name}
          onValueChange={setName}
        />
        <TextField
          label="Состояние ошибки"
          error={ru.reg.name.errorEmpty}
          placeholder={ru.reg.name.placeholder}
          value=""
          onValueChange={() => {}}
        />
        <TextField
          label="Disabled"
          placeholder={ru.reg.name.placeholder}
          value="Иван"
          onValueChange={() => {}}
          disabled
        />
      </Section>

      <Section title={`ChoiceCard — ${ru.reg.grade.title}`}>
        <ChoiceCard selected={grade === 9} onSelect={() => setGrade(9)}>
          {ru.reg.grade.opt9}
        </ChoiceCard>
        <ChoiceCard selected={grade === 10} onSelect={() => setGrade(10)}>
          {ru.reg.grade.opt10}
        </ChoiceCard>
        <ChoiceCard selected={grade === 11} onSelect={() => setGrade(11)}>
          {ru.reg.grade.opt11}
        </ChoiceCard>
        <ChoiceCard disabled onSelect={() => {}}>
          8 класс (disabled в production)
        </ChoiceCard>
      </Section>

      <Section title="Checkbox + PolicyLink — согласие">
        <Checkbox checked={consent} onCheckedChange={setConsent}>
          {ru.reg.consent.checkbox}
        </Checkbox>
        <PolicyLink href="#policy">{ru.reg.consent.policyLink}</PolicyLink>
        <Checkbox checked={false} disabled onCheckedChange={() => {}}>
          Недоступен, пока политика не загрузилась (RF-04)
        </Checkbox>
        <PolicyLink href="#policy" available={false}>
          {ru.reg.consent.policyLink}
        </PolicyLink>
      </Section>
    </div>
  )
}
