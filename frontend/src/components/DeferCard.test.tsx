import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { DeferCard } from './DeferCard'

describe('DeferCard', () => {
  it('показывает текст без вины и кнопку «Понятно»', () => {
    render(<DeferCard onConfirm={() => {}} />)
    expect(screen.getByText(/Сегодня не зашло/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Понятно' })).toBeInTheDocument()
  })

  it('вызывает onConfirm (evt_lesson_fail_confirmed) по клику', async () => {
    const onConfirm = vi.fn()
    render(<DeferCard onConfirm={onConfirm} />)
    await userEvent.click(screen.getByRole('button', { name: 'Понятно' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })
})
