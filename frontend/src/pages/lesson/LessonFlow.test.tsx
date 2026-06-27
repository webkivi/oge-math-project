import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { LessonFlow } from './LessonFlow'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('LessonFlow', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('view=day_hub (daily_start) → экран DailyStart', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.endsWith('/api/lesson/current')) {
          return jsonResponse(200, {
            fsm_state: 'registered',
            view: 'day_hub',
            message: null,
            seq: 0,
            next_actions: [],
          })
        }
        if (url.endsWith('/api/day')) {
          return jsonResponse(200, {
            fsm_state: 'registered',
            view: 'day_hub',
            message: null,
            seq: 0,
            next_actions: [],
            day: { streak_days: 0, warmup_available: false, has_lesson_today: true },
          })
        }
        if (url.endsWith('/api/day/open')) {
          return jsonResponse(200, {
            fsm_state: 'daily_start',
            view: 'day_hub',
            message: null,
            seq: 0,
            next_actions: [],
            day: { streak_days: 0, warmup_available: false, has_lesson_today: true },
          })
        }
        throw new Error('unexpected ' + url)
      }),
    )
    render(<LessonFlow />)
    expect(await screen.findByText('Твой шаг на сегодня')).toBeInTheDocument()
  })

  it('view=day_done → экран DailyDone', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(200, {
          fsm_state: 'daily_done',
          view: 'day_done',
          message: null,
          seq: 0,
          next_actions: [],
        }),
      ),
    )
    render(<LessonFlow />)
    expect(
      await screen.findByText('На сегодня всё. Можно выдохнуть — встретимся завтра.'),
    ).toBeInTheDocument()
  })

  it('сеть недоступна → ConnectionStub (offline), без падения приложения', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )
    render(<LessonFlow />)
    expect(await screen.findByText('Нет соединения')).toBeInTheDocument()
  })

  it('lesson_content_unavailable → ConnectionStub (content-missing)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(503, { error: 'lesson_content_unavailable', field: null }),
      ),
    )
    render(<LessonFlow />)
    await waitFor(() =>
      expect(
        screen.getByText('Урок не загрузился. Аккаунт на месте — попробуем ещё раз.'),
      ).toBeInTheDocument(),
    )
  })
})
