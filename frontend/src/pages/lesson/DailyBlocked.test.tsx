import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { DailyBlocked } from './DailyBlocked'

describe('DailyBlocked', () => {
  it('показывает «новый урок откроется завтра»', () => {
    render(<DailyBlocked />)
    expect(
      screen.getByText(
        'Новый урок откроется завтра. Сегодня можно спокойно повторить то, что уже разбирал.',
      ),
    ).toBeInTheDocument()
  })
})
