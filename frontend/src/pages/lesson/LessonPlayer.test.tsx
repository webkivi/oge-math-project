import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { LessonPlayer } from './LessonPlayer'
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

describe('LessonPlayer', () => {
  it('проходной экран (theory): MessageCard + «Дальше» → advance', async () => {
    const lesson = makeLesson({
      fsm_state: 'lesson_theory',
      view: 'lesson_message',
      message: {
        message_id: 'm1',
        stage: 'theory',
        text_html: '<p>теория про дроби</p>',
      },
      lesson_progress: { step: 1, total: 5 },
      seq: 1,
      next_actions: ['advance', 'cancel'],
    })
    render(<LessonPlayer lesson={lesson} />)
    expect(screen.getByText('теория про дроби')).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Этап 1 из 5' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Дальше' }))
    expect(lesson.advance).toHaveBeenCalledTimes(1)
  })

  it('вопрос-стадия: QuestionBlock → select с буквой', async () => {
    const lesson = makeLesson({
      fsm_state: 'lesson_training',
      view: 'lesson_question',
      message: {
        message_id: 'm2',
        stage: 'training',
        text_html: '<p>1/2 + 1/4?</p>',
        options: [
          { letter: 'A', text_html: '3/4' },
          { letter: 'B', text_html: '2/6' },
        ],
      },
      lesson_progress: { step: 3, total: 5 },
      seq: 2,
      next_actions: ['answer', 'cancel'],
    })
    render(<LessonPlayer lesson={lesson} />)
    await userEvent.click(screen.getByRole('radio', { name: '3/4' }))
    expect(lesson.select).toHaveBeenCalledWith('A')
  })

  it('wrong-возврат: AnswerFeedback (ловушка) + вопрос для повторной попытки', () => {
    const lesson = makeLesson({
      fsm_state: 'lesson_training',
      view: 'lesson_feedback',
      message: {
        message_id: 'm2',
        stage: 'training',
        text_html: '<p>1/2 + 1/4?</p>',
        options: [{ letter: 'A', text_html: '3/4' }],
      },
      feedback: {
        is_correct: false,
        feedback_html: '<p>забыли общий знаменатель</p>',
        return_target: 'm2',
      },
      lesson_progress: { step: 3, total: 5 },
      seq: 3,
      next_actions: ['answer', 'cancel'],
    })
    render(<LessonPlayer lesson={lesson} />)
    expect(
      screen.getByText('Тут типичная ловушка — в неё попадают многие.'),
    ).toBeInTheDocument()
    expect(screen.getByText('забыли общий знаменатель')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: '3/4' })).toBeInTheDocument()
  })

  it('lesson_failed: DeferCard, «Понятно» → advance (evt_lesson_fail_confirmed)', async () => {
    const lesson = makeLesson({
      fsm_state: 'lesson_failed',
      view: 'lesson_failed',
      message: {
        message_id: 'm3',
        stage: 'lesson_failed',
        text_html: '<p>не вышло</p>',
      },
      seq: 4,
      next_actions: ['advance'],
    })
    render(<LessonPlayer lesson={lesson} />)
    expect(screen.getByText(/Сегодня не зашло/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Понятно' }))
    expect(lesson.advance).toHaveBeenCalledTimes(1)
  })

  it('«Выйти из урока» вызывает exitLesson', async () => {
    const lesson = makeLesson({
      fsm_state: 'lesson_theory',
      view: 'lesson_message',
      message: { message_id: 'm1', stage: 'theory', text_html: '<p>теория</p>' },
      seq: 1,
      next_actions: ['advance', 'cancel'],
    })
    render(<LessonPlayer lesson={lesson} />)
    await userEvent.click(screen.getByRole('button', { name: 'Выйти из урока' }))
    expect(lesson.exitLesson).toHaveBeenCalledTimes(1)
  })

  it('resumable (api §4.6): read-only — без AnswerButtons/«Выйти», только «Продолжить» → startNextLesson', async () => {
    const lesson = makeLesson({
      fsm_state: 'registered',
      view: 'lesson_message',
      message: {
        message_id: 'th2',
        stage: 'theory',
        text_html: '<p>сохранённая позиция</p>',
        options: [{ letter: 'A', text_html: 'не должно быть кликабельно' }],
      },
      seq: 2,
      next_actions: [],
      resumable: true,
    })
    render(<LessonPlayer lesson={lesson} />)
    expect(screen.getByText('сохранённая позиция')).toBeInTheDocument()
    expect(screen.queryByRole('radio')).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Выйти из урока' }),
    ).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Продолжить' }))
    expect(lesson.startNextLesson).toHaveBeenCalledTimes(1)
    expect(lesson.advance).not.toHaveBeenCalled()
    expect(lesson.select).not.toHaveBeenCalled()
  })

  it('EC-01: busy=true блокирует варианты ответа — второй клик не уходит', async () => {
    const lesson = makeLesson(
      {
        fsm_state: 'lesson_training',
        view: 'lesson_question',
        message: {
          message_id: 'm2',
          stage: 'training',
          text_html: '<p>1/2 + 1/4?</p>',
          options: [
            { letter: 'A', text_html: '3/4' },
            { letter: 'B', text_html: '2/6' },
          ],
        },
        lesson_progress: { step: 3, total: 5 },
        seq: 2,
        next_actions: ['answer', 'cancel'],
      },
      { busy: true },
    )
    render(<LessonPlayer lesson={lesson} />)
    await userEvent.click(screen.getByRole('radio', { name: '3/4' }))
    expect(lesson.select).not.toHaveBeenCalled()
    expect(screen.getByRole('radio', { name: '3/4' })).toBeDisabled()
  })

  it('message=null → ничего не рендерит (LessonFlow ещё не дождался данных)', () => {
    const lesson = makeLesson({
      fsm_state: 'lesson_theory',
      view: 'lesson_message',
      message: null,
      seq: 1,
      next_actions: [],
    })
    const { container } = render(<LessonPlayer lesson={lesson} />)
    expect(container).toBeEmptyDOMElement()
  })
})
