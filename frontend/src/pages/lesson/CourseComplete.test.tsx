import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { CourseComplete } from './CourseComplete'

describe('CourseComplete', () => {
  it('показывает поздравление с финишем курса', () => {
    render(<CourseComplete />)
    expect(screen.getByText(/Ты дошёл до конца/)).toBeInTheDocument()
  })
})
