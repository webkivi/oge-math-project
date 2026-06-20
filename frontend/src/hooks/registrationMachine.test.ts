import { describe, expect, it } from 'vitest'

import { transition } from './registrationMachine'

describe('registrationMachine (reg_v2 §2)', () => {
  it('grade=9 — прямой вход: unregistered → name → grade → consent → registered', () => {
    expect(transition('unregistered', { type: 'open_pwa' })).toBe('name_entry')
    expect(
      transition('name_entry', { type: 'name_submitted', namePresent: true }),
    ).toBe('grade_entry')
    expect(
      transition('grade_entry', {
        type: 'grade_selected',
        grade: 9,
        isProduction: true,
      }),
    ).toBe('consent_gate')
    expect(
      transition('consent_gate', { type: 'submit_registration', canSubmit: true }),
    ).toBe('registered')
  })

  it('пустое имя не пускает дальше (RC-02)', () => {
    expect(
      transition('name_entry', { type: 'name_submitted', namePresent: false }),
    ).toBeNull()
  })

  it('grade=10/11 → ogeprep_check; да → consent, нет → course_mismatch → продолжить', () => {
    expect(
      transition('grade_entry', {
        type: 'grade_selected',
        grade: 10,
        isProduction: true,
      }),
    ).toBe('ogeprep_check')
    expect(transition('ogeprep_check', { type: 'ogeprep_yes' })).toBe('consent_gate')
    expect(transition('ogeprep_check', { type: 'ogeprep_no' })).toBe('course_mismatch')
    expect(transition('course_mismatch', { type: 'mismatch_continue' })).toBe(
      'consent_gate',
    )
    expect(transition('course_mismatch', { type: 'mismatch_leave' })).toBe(
      'unregistered',
    )
  })

  it('grade=8: production → gate_grade8; вне production → consent_gate (staging)', () => {
    expect(
      transition('grade_entry', {
        type: 'grade_selected',
        grade: 8,
        isProduction: true,
      }),
    ).toBe('gate_grade8')
    expect(
      transition('grade_entry', {
        type: 'grade_selected',
        grade: 8,
        isProduction: false,
      }),
    ).toBe('consent_gate')
    expect(transition('gate_grade8', { type: 'gate_dismiss' })).toBe('unregistered')
  })

  it('submit без согласия (canSubmit=false) не создаёт аккаунт (RC-03)', () => {
    expect(
      transition('consent_gate', { type: 'submit_registration', canSubmit: false }),
    ).toBeNull()
  })

  it('back: consent → grade → name; cancel → unregistered', () => {
    expect(transition('consent_gate', { type: 'back' })).toBe('grade_entry')
    expect(transition('grade_entry', { type: 'back' })).toBe('name_entry')
    expect(transition('ogeprep_check', { type: 'back' })).toBe('grade_entry')
    expect(transition('grade_entry', { type: 'cancel_registration' })).toBe(
      'unregistered',
    )
  })

  it('registered — терминал; невозможные события → null', () => {
    expect(transition('registered', { type: 'open_pwa' })).toBeNull()
    expect(
      transition('name_entry', {
        type: 'grade_selected',
        grade: 9,
        isProduction: true,
      }),
    ).toBeNull()
    expect(transition('gate_grade8', { type: 'back' })).toBeNull()
  })

  it('cancel_registration из любого шага формы → unregistered', () => {
    const steps = [
      'name_entry',
      'grade_entry',
      'ogeprep_check',
      'course_mismatch',
      'consent_gate',
    ] as const
    for (const step of steps) {
      expect(transition(step, { type: 'cancel_registration' })).toBe('unregistered')
    }
  })

  it('submit_registration возможен ТОЛЬКО из consent_gate (RC-03)', () => {
    const others = [
      'name_entry',
      'grade_entry',
      'ogeprep_check',
      'course_mismatch',
    ] as const
    for (const step of others) {
      expect(
        transition(step, { type: 'submit_registration', canSubmit: true }),
      ).toBeNull()
    }
    expect(
      transition('consent_gate', { type: 'submit_registration', canSubmit: true }),
    ).toBe('registered')
  })
})
