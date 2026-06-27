import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { MorningWarmup } from './MorningWarmup'
import type { UseLesson } from '../../hooks/useLesson'
import type { LessonRender } from '../../api/lessonClient'

function makeLesson(
  render: LessonRender,
  overrides: Partial<UseLesson> = {},
): UseLesson {
  return {
    render,
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

describe('MorningWarmup', () => {
  it('рендерит R3-вопрос и шлёт warmupSelect с буквой', async () => {
    const lesson = makeLesson({
      fsm_state: 'morning_warmup',
      view: 'warmup',
      message: {
        message_id: 'r1',
        stage: 'repeat_morning',
        text_html: '<p>сколько будет 2+2?</p>',
        options: [
          { letter: 'A', text_html: '4' },
          { letter: 'B', text_html: '5' },
        ],
      },
      seq: 1,
      next_actions: ['warmup_answer', 'warmup_skip'],
    })
    render(<MorningWarmup lesson={lesson} />)
    await userEvent.click(screen.getByRole('radio', { name: '4' }))
    expect(lesson.warmupSelect).toHaveBeenCalledWith('A')
  })

  it('«Пропустить разминку» вызывает skipWarmup', async () => {
    const lesson = makeLesson({
      fsm_state: 'morning_warmup',
      view: 'warmup',
      message: {
        message_id: 'r1',
        stage: 'repeat_morning',
        text_html: '<p>?</p>',
        options: [],
      },
      seq: 1,
      next_actions: [],
    })
    render(<MorningWarmup lesson={lesson} />)
    await userEvent.click(screen.getByRole('button', { name: 'Пропустить разминку' }))
    expect(lesson.skipWarmup).toHaveBeenCalledTimes(1)
  })

  it('EC-01: busy=true блокирует варианты и «Пропустить» — клик не уходит', async () => {
    const lesson = makeLesson(
      {
        fsm_state: 'morning_warmup',
        view: 'warmup',
        message: {
          message_id: 'r1',
          stage: 'repeat_morning',
          text_html: '<p>сколько будет 2+2?</p>',
          options: [
            { letter: 'A', text_html: '4' },
            { letter: 'B', text_html: '5' },
          ],
        },
        seq: 1,
        next_actions: ['warmup_answer', 'warmup_skip'],
      },
      { busy: true },
    )
    render(<MorningWarmup lesson={lesson} />)
    await userEvent.click(screen.getByRole('radio', { name: '4' }))
    expect(lesson.warmupSelect).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Пропустить разминку' })).toBeDisabled()
  })

  it('message=null (известный гап резюме) → самопочинка через skipWarmup', async () => {
    const lesson = makeLesson({
      fsm_state: 'morning_warmup',
      view: 'warmup',
      message: null,
      seq: 1,
      next_actions: [],
    })
    render(<MorningWarmup lesson={lesson} />)
    await waitFor(() => expect(lesson.skipWarmup).toHaveBeenCalledTimes(1))
  })
})
