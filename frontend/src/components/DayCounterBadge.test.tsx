import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { DayCounterBadge } from './DayCounterBadge'

describe('DayCounterBadge', () => {
  it('склоняет «день/дня/дней» (F-1: тихо, слово только «дни подряд»)', () => {
    render(<DayCounterBadge days={1} />)
    expect(screen.getByText('1 день подряд')).toBeInTheDocument()
  })

  it('склонение для 3', () => {
    render(<DayCounterBadge days={3} />)
    expect(screen.getByText('3 дня подряд')).toBeInTheDocument()
  })

  it('склонение для 5', () => {
    render(<DayCounterBadge days={5} />)
    expect(screen.getByText('5 дней подряд')).toBeInTheDocument()
  })

  it('передышка применена (S-07): другой текст, без чувства долга', () => {
    render(<DayCounterBadge days={5} pauseApplied />)
    expect(
      screen.getByText(
        'Сегодня берём передышку — счётчик дней сохранён, ничего не сгорает.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('5 дней подряд')).not.toBeInTheDocument()
  })
})
