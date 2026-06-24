import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AnswerFeedback } from './AnswerFeedback'

describe('AnswerFeedback', () => {
  it('верно: тёплый зелёный (--correct), лид-фраза + разбор из CSV', () => {
    render(<AnswerFeedback isCorrect feedbackHtml="<p>сократили на 2</p>" />)
    expect(screen.getByText('Верно.')).toBeInTheDocument()
    expect(screen.getByText('сократили на 2')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveClass('border-correct')
  })

  it('неверно: «типичная ловушка», тёплая охра (--trap), НЕ красный', () => {
    render(
      <AnswerFeedback
        isCorrect={false}
        feedbackHtml="<p>забыли привести к общему знаменателю</p>"
      />,
    )
    expect(
      screen.getByText('Тут типичная ловушка — в неё попадают многие.'),
    ).toBeInTheDocument()
    const status = screen.getByRole('status')
    expect(status).toHaveClass('border-trap')
    expect(status).not.toHaveClass('border-correct')
  })
})
