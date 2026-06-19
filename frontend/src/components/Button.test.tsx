import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Button } from './Button'

describe('Button', () => {
  it('рендерит подпись и вызывает onClick', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Начать</Button>)
    await userEvent.click(screen.getByRole('button', { name: 'Начать' }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('loading блокирует повторный сабмит (RC-01): disabled + aria-busy, onClick не вызывается', async () => {
    const onClick = vi.fn()
    render(
      <Button loading onClick={onClick}>
        Начать
      </Button>,
    )
    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('status')).toBeInTheDocument()
    await userEvent.click(button)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('disabled не вызывает onClick', async () => {
    const onClick = vi.fn()
    render(
      <Button disabled onClick={onClick}>
        Дальше
      </Button>,
    )
    await userEvent.click(screen.getByRole('button'))
    expect(onClick).not.toHaveBeenCalled()
  })
})
