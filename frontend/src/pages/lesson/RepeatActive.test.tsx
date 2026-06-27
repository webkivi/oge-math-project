import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { RepeatActive } from './RepeatActive'
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

describe('RepeatActive', () => {
  it('один вопрос R1/R2 → repeatSelect с буквой', async () => {
    const lesson = makeLesson({
      fsm_state: 'repeat_1h_active',
      view: 'repeat_question',
      message: {
        message_id: 'r2',
        stage: 'repeat_1h',
        text_html: '<p>повтори: 1/2 = ?</p>',
        options: [{ letter: 'A', text_html: '0.5' }],
      },
      seq: 1,
      next_actions: ['answer'],
    })
    render(<RepeatActive lesson={lesson} />)
    await userEvent.click(screen.getByRole('radio', { name: '0.5' }))
    expect(lesson.repeatSelect).toHaveBeenCalledWith('A')
  })

  it('EC-01: busy=true блокирует вариант — клик не уходит', async () => {
    const lesson = makeLesson(
      {
        fsm_state: 'repeat_1h_active',
        view: 'repeat_question',
        message: {
          message_id: 'r2',
          stage: 'repeat_1h',
          text_html: '<p>повтори: 1/2 = ?</p>',
          options: [{ letter: 'A', text_html: '0.5' }],
        },
        seq: 1,
        next_actions: ['answer'],
      },
      { busy: true },
    )
    render(<RepeatActive lesson={lesson} />)
    await userEvent.click(screen.getByRole('radio', { name: '0.5' }))
    expect(lesson.repeatSelect).not.toHaveBeenCalled()
    expect(screen.getByRole('radio', { name: '0.5' })).toBeDisabled()
  })

  it('message=null → ничего не рендерит', () => {
    const lesson = makeLesson({
      fsm_state: 'repeat_1h_active',
      view: 'repeat_question',
      message: null,
      seq: 1,
      next_actions: [],
    })
    const { container } = render(<RepeatActive lesson={lesson} />)
    expect(container).toBeEmptyDOMElement()
  })
})
