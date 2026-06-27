import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { RepeatPending } from './RepeatPending'

describe('RepeatPending', () => {
  it('информирует о повторении без выдуманного числа минут', () => {
    render(<RepeatPending />)
    expect(
      screen.getByText('Короткое повторение появится здесь немного позже.'),
    ).toBeInTheDocument()
  })
})
