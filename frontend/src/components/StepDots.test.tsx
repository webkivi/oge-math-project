import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StepDots } from './StepDots'

describe('StepDots', () => {
  it('озвучивает прогресс скринридеру через aria-label группы (§5)', () => {
    render(<StepDots total={3} current={1} />)
    expect(screen.getByRole('group')).toHaveAccessibleName('Шаг 2 из 3')
  })

  it('поддерживает кастомную подпись шага', () => {
    render(<StepDots total={2} current={0} label="Этап" />)
    expect(screen.getByRole('group')).toHaveAccessibleName('Этап 1 из 2')
  })
})
