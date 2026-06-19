import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { TextField } from './TextField'

describe('TextField', () => {
  it('вызывает onValueChange при вводе', async () => {
    const onValueChange = vi.fn()
    render(<TextField label="Имя" value="" onValueChange={onValueChange} />)
    await userEvent.type(screen.getByLabelText('Имя'), 'И')
    expect(onValueChange).toHaveBeenCalledWith('И')
  })

  it('показывает ошибку и помечает aria-invalid (RC-02)', () => {
    render(
      <TextField label="Имя" value="" error="Впиши имя" onValueChange={() => {}} />,
    )
    const input = screen.getByLabelText('Имя')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByText('Впиши имя')).toBeInTheDocument()
  })

  it('disabled блокирует ввод', () => {
    render(<TextField label="Имя" value="Иван" onValueChange={() => {}} disabled />)
    expect(screen.getByLabelText('Имя')).toBeDisabled()
  })
})
