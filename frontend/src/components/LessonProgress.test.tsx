import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { LessonProgress } from './LessonProgress'

describe('LessonProgress', () => {
  it('озвучивает этап скринридеру через aria-label', () => {
    render(<LessonProgress step={3} total={5} />)
    expect(screen.getByRole('group', { name: 'Этап 3 из 5' })).toBeInTheDocument()
  })

  it('total=5 при авто-проскоке hook (R3, текущий контент Блока 1)', () => {
    const { container } = render(<LessonProgress step={1} total={5} />)
    expect(container.querySelectorAll('[aria-hidden]')).toHaveLength(5)
  })

  it('total=6 при наличии hook-стадии в CSV', () => {
    const { container } = render(<LessonProgress step={1} total={6} />)
    expect(container.querySelectorAll('[aria-hidden]')).toHaveLength(6)
  })
})
