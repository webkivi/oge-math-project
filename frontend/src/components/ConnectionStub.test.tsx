import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ConnectionStub } from './ConnectionStub'

describe('ConnectionStub', () => {
  it('offline: «нет соединения», прогресс на месте (D-5)', () => {
    render(<ConnectionStub variant="offline" />)
    expect(screen.getByText('Нет соединения')).toBeInTheDocument()
    expect(
      screen.getByText('Прогресс на месте. Продолжим, как только сеть вернётся.'),
    ).toBeInTheDocument()
  })

  it('content-missing: контент не загрузился, аккаунт цел', () => {
    render(<ConnectionStub variant="content-missing" />)
    expect(
      screen.getByText('Урок не загрузился. Аккаунт на месте — попробуем ещё раз.'),
    ).toBeInTheDocument()
  })

  it('дефолт — offline', () => {
    render(<ConnectionStub />)
    expect(screen.getByText('Нет соединения')).toBeInTheDocument()
  })
})
