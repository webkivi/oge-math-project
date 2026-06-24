import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { EmptyState } from './EmptyState'
import { ru } from '../i18n/ru'

describe('EmptyState', () => {
  it('показывает «на сегодня всё» (daily_done), без догоняющих предложений', () => {
    render(<EmptyState>{ru.day.doneBody}</EmptyState>)
    expect(
      screen.getByText('На сегодня всё. Можно выдохнуть — встретимся завтра.'),
    ).toBeInTheDocument()
  })

  it('поддерживает опциональный слот действия — приглашение, не «мудборд»', () => {
    render(
      <EmptyState action={<button type="button">Карта знаний</button>}>
        Текст
      </EmptyState>,
    )
    expect(screen.getByRole('button', { name: 'Карта знаний' })).toBeInTheDocument()
  })
})
