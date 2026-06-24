import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { QuestionBlock } from './QuestionBlock'

describe('QuestionBlock', () => {
  it('рендерит текст вопроса и варианты ответа', () => {
    render(
      <QuestionBlock
        textHtml="<p>Сколько будет 1/2 + 1/4?</p>"
        options={[
          { letter: 'A', textHtml: '3/4' },
          { letter: 'B', textHtml: '2/6' },
        ]}
        onSelect={() => {}}
      />,
    )
    expect(screen.getByText('Сколько будет 1/2 + 1/4?')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: '3/4' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: '2/6' })).toBeInTheDocument()
  })

  it('один вопрос = один экран — выбор варианта вызывает onSelect', async () => {
    const onSelect = vi.fn()
    render(
      <QuestionBlock
        textHtml="<p>Вопрос</p>"
        options={[
          { letter: 'A', textHtml: 'да' },
          { letter: 'B', textHtml: 'нет' },
        ]}
        onSelect={onSelect}
      />,
    )
    await userEvent.click(screen.getByRole('radio', { name: 'да' }))
    expect(onSelect).toHaveBeenCalledWith('A')
  })
})
