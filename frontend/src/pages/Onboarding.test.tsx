import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Onboarding } from './Onboarding'

// Мокаем глобальный fetch: E1 (pd-policy), E3 (registration) и стык с дневным
// потоком (E7/E4/E5, LessonFlow) — после 201 Onboarding передаёт управление
// LessonFlow, который сразу бутстрапится (specs/student_lesson_api_v1.md §1.2).
// status задаётся per-test, чтобы проверить 201 (успех) и 422 (ошибка, consent).
function stubFetch(registrationStatus: number) {
  const dayHubRender = (fsmState: string) => ({
    fsm_state: fsmState,
    view: 'day_hub',
    message: null,
    seq: 0,
    next_actions: [],
    day: { streak_days: 0, warmup_available: false, has_lesson_today: true },
  })
  const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith('/api/pd-policy')) {
      return new Response(
        JSON.stringify({
          policy_version: 'v1',
          policy_url: '/policy',
          available: true,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    }
    if (url.endsWith('/api/registration')) {
      const body =
        registrationStatus === 201
          ? {
              user_id: '1',
              role: 'student',
              grade: 9,
              fsm_state: 'registered',
              enrollment_reason: 'grade9_direct',
              current_lesson_id: '1_1',
              next: 'daily_start',
            }
          : { error: 'consent_required', field: 'pd_consent_checked' }
      return new Response(JSON.stringify(body), {
        status: registrationStatus,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    if (url.endsWith('/api/lesson/current')) {
      return new Response(JSON.stringify(dayHubRender('registered')), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    if (url.endsWith('/api/day')) {
      return new Response(JSON.stringify(dayHubRender('registered')), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    if (url.endsWith('/api/day/open')) {
      return new Response(JSON.stringify(dayHubRender('daily_start')), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    return new Response('{}', { status: 404 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

// TODO[before-pilot]: вернуть клик по checkbox после возврата согласия ПД (152-ФЗ)
async function walkToConsentGrade9(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByRole('textbox'), 'Иван')
  await user.click(screen.getByRole('button', { name: 'Дальше' }))
  await user.click(screen.getByRole('radio', { name: '9 класс' }))
  // Чекбокс согласия ПД временно отключён — ждём загрузку политики (canSubmit)
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Начать' })).toBeEnabled(),
  )
}

describe('Onboarding — поток регистрации', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  describe('grade=9 happy path → 201 → registered', () => {
    let fetchMock: ReturnType<typeof stubFetch>
    beforeEach(() => {
      fetchMock = stubFetch(201)
    })

    it('доходит до registered и шлёт submit с Idempotency-Key и draft', async () => {
      const user = userEvent.setup()
      render(<Onboarding />)
      await walkToConsentGrade9(user)
      await user.click(screen.getByRole('button', { name: 'Начать' }))

      // Передача в LessonFlow: registered → (E7 day_hub) → E4/E5 → daily_start.
      expect(await screen.findByText('Твой шаг на сегодня')).toBeInTheDocument()

      const submitCall = fetchMock.mock.calls.find(([url]) =>
        String(url).endsWith('/api/registration'),
      )
      expect(submitCall).toBeDefined()
      const init = submitCall![1]
      expect(init).toBeDefined()
      const headers = init!.headers as Record<string, string>
      expect(headers['Idempotency-Key']).toBeTruthy()
      // TODO[before-pilot]: вернуть чекбокс → pd_consent_checked берётся из consent state (не hardcode true).
      // Также добавить тест RC-03: бэкенд отклоняет pd_consent_checked=false (422).
      expect(JSON.parse(init!.body as string)).toMatchObject({
        name: 'Иван',
        grade: 9,
        ogeprep_answer: null,
        pd_consent_checked: true,
        policy_version_shown: 'v1',
      })
    })
  })

  describe('ошибка submit (422) → сообщение, остаёмся в consent_gate', () => {
    beforeEach(() => {
      stubFetch(422)
    })

    it('показывает ошибку и НЕ уходит в registered', async () => {
      const user = userEvent.setup()
      render(<Onboarding />)
      await walkToConsentGrade9(user)
      await user.click(screen.getByRole('button', { name: 'Начать' }))

      expect(await screen.findByRole('alert')).toBeInTheDocument()
      expect(screen.queryByText('Твой шаг на сегодня')).not.toBeInTheDocument()
      // Остаёмся на экране согласия — кнопка «Начать» на месте.
      expect(screen.getByRole('button', { name: 'Начать' })).toBeInTheDocument()
    })
  })
})
