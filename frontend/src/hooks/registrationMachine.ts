// Клиентский под-FSM онбординга — зеркало specs/student_registration_fsm_v2.md §2б.
// Чистая функция переходов: возвращает следующее состояние или null, если переход
// недопустим (guard не прошёл / событие невозможно в этом состоянии). Бизнес-данные
// (draft) и сайд-эффекты — в useRegistration; здесь только граф состояний.

export type RegState =
  | 'unregistered'
  | 'name_entry'
  | 'grade_entry'
  | 'ogeprep_check'
  | 'course_mismatch'
  | 'consent_gate'
  | 'gate_grade8'
  | 'registered'

export type RegEvent =
  | { type: 'open_pwa' }
  | { type: 'name_submitted'; namePresent: boolean }
  | { type: 'grade_selected'; grade: number; isProduction: boolean }
  | { type: 'ogeprep_yes' }
  | { type: 'ogeprep_no' }
  | { type: 'mismatch_continue' }
  | { type: 'mismatch_leave' }
  | { type: 'submit_registration'; canSubmit: boolean }
  | { type: 'back' }
  | { type: 'cancel_registration' }
  | { type: 'gate_dismiss' }

const OGEPREP_GRADES = new Set([10, 11])

export function transition(state: RegState, event: RegEvent): RegState | null {
  switch (state) {
    case 'unregistered':
      return event.type === 'open_pwa' ? 'name_entry' : null

    case 'name_entry':
      if (event.type === 'name_submitted')
        return event.namePresent ? 'grade_entry' : null
      if (event.type === 'cancel_registration') return 'unregistered'
      return null

    case 'grade_entry':
      if (event.type === 'grade_selected') {
        const { grade, isProduction } = event
        // grade=8: production — жёсткий гейт (D-6); вне production — staging-аффорданс.
        if (grade === 8) return isProduction ? 'gate_grade8' : 'consent_gate'
        if (grade === 9) return 'consent_gate'
        if (OGEPREP_GRADES.has(grade)) return 'ogeprep_check'
        return null
      }
      if (event.type === 'back') return 'name_entry'
      if (event.type === 'cancel_registration') return 'unregistered'
      return null

    case 'ogeprep_check':
      if (event.type === 'ogeprep_yes') return 'consent_gate'
      if (event.type === 'ogeprep_no') return 'course_mismatch'
      if (event.type === 'back') return 'grade_entry'
      if (event.type === 'cancel_registration') return 'unregistered'
      return null

    case 'course_mismatch':
      if (event.type === 'mismatch_continue') return 'consent_gate'
      if (event.type === 'mismatch_leave') return 'unregistered'
      if (event.type === 'cancel_registration') return 'unregistered'
      return null

    case 'consent_gate':
      if (event.type === 'submit_registration')
        return event.canSubmit ? 'registered' : null
      if (event.type === 'back') return 'grade_entry'
      if (event.type === 'cancel_registration') return 'unregistered'
      return null

    case 'gate_grade8':
      return event.type === 'gate_dismiss' ? 'unregistered' : null

    case 'registered':
      return null

    default:
      return null
  }
}
