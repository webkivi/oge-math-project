import { useRegistration } from '../hooks/useRegistration'
import { ru } from '../i18n/ru'
import { ConsentGate } from './registration/ConsentGate'
import { CourseMismatch } from './registration/CourseMismatch'
import { GateGrade8 } from './registration/GateGrade8'
import { GradeEntry } from './registration/GradeEntry'
import { NameEntry } from './registration/NameEntry'
import { OgeprepCheck } from './registration/OgeprepCheck'

// Оркестратор онбординга (раскладка v4 §7: pages/Onboarding.tsx). Держит один
// useRegistration и рендерит экран по текущему состоянию под-FSM reg_v2.
export function Onboarding() {
  const reg = useRegistration()

  switch (reg.state) {
    case 'name_entry':
      return <NameEntry reg={reg} />
    case 'grade_entry':
      return <GradeEntry reg={reg} />
    case 'ogeprep_check':
      return <OgeprepCheck reg={reg} />
    case 'course_mismatch':
      return <CourseMismatch reg={reg} />
    case 'consent_gate':
      return <ConsentGate reg={reg} />
    case 'gate_grade8':
      return <GateGrade8 reg={reg} />
    case 'registered':
      // Плейсхолдер: реальный переход в daily_start/первый урок — v4 (вне среза).
      return (
        <div className="flex flex-1 flex-col justify-center py-6">
          <p className="text-lead text-ink">{ru.reg.done}</p>
        </div>
      )
    case 'unregistered':
    default:
      // Отмена/выход/гейт-dismiss. Тексты этого экрана-заглушки — на доработку А8.
      return (
        <div className="flex flex-1 flex-col items-start justify-center gap-4 py-6">
          <p className="text-body text-ink-secondary">Регистрация не завершена.</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-control text-option text-primary-active underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusring"
          >
            Начать заново
          </button>
        </div>
      )
  }
}
