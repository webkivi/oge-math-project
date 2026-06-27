import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { DailyDone } from './DailyDone'

describe('DailyDone', () => {
  it('показывает «на сегодня всё»', () => {
    render(<DailyDone />)
    expect(
      screen.getByText('На сегодня всё. Можно выдохнуть — встретимся завтра.'),
    ).toBeInTheDocument()
  })
})
