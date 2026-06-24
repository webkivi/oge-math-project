import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PendingNotice } from './PendingNotice'
import { ru } from '../i18n/ru'

describe('PendingNotice', () => {
  it('информирует о R1 («через N минут»), без кнопки действия', () => {
    render(<PendingNotice>{ru.repeat.r1Pending(15)}</PendingNotice>)
    expect(
      screen.getByText('Короткое повторение будет через 15 минут.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('информирует о daily_blocked («завтра»)', () => {
    render(<PendingNotice>{ru.blocked.body}</PendingNotice>)
    expect(screen.getByRole('status')).toHaveTextContent('Новый урок откроется завтра.')
  })
})
