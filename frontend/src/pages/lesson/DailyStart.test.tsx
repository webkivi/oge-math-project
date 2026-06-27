import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { DailyStart } from './DailyStart'
import type { UseLesson } from '../../hooks/useLesson'

function makeLesson(overrides: Partial<UseLesson> = {}): UseLesson {
  return {
    render: null,
    loading: false,
    busy: false,
    offline: false,
    contentMissing: false,
    startWarmup: vi.fn(),
    skipWarmup: vi.fn(),
    warmupSelect: vi.fn(),
    startNextLesson: vi.fn(),
    advance: vi.fn(),
    select: vi.fn(),
    exitLesson: vi.fn(),
    repeatSelect: vi.fn(),
    retry: vi.fn(),
    ...overrides,
  }
}

describe('DailyStart', () => {
  it('есть due-повторения → CTA «Начать разминку», вызывает startWarmup', async () => {
    const lesson = makeLesson({
      render: {
        fsm_state: 'daily_start',
        view: 'day_hub',
        message: null,
        seq: 0,
        next_actions: [],
        day: { streak_days: 3, warmup_available: true, has_lesson_today: true },
      },
    })
    render(<DailyStart lesson={lesson} />)
    expect(screen.getByText('Твой шаг на сегодня')).toBeInTheDocument()
    expect(screen.getByText('3 дня подряд')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Начать разминку' }))
    expect(lesson.startWarmup).toHaveBeenCalledTimes(1)
  })

  it('очередь пуста → CTA «Открыть урок», вызывает skipWarmup', async () => {
    const lesson = makeLesson({
      render: {
        fsm_state: 'daily_start',
        view: 'day_hub',
        message: null,
        seq: 0,
        next_actions: [],
        day: { streak_days: 0, warmup_available: false, has_lesson_today: true },
      },
    })
    render(<DailyStart lesson={lesson} />)
    await userEvent.click(screen.getByRole('button', { name: 'Открыть урок' }))
    expect(lesson.skipWarmup).toHaveBeenCalledTimes(1)
  })
})
