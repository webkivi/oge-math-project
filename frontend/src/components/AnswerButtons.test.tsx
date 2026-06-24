import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { AnswerButtons } from './AnswerButtons'
import type { AnswerOption } from './AnswerButtons'

const options: AnswerOption[] = [
  { letter: 'A', textHtml: '1/2' },
  { letter: 'B', textHtml: '1/3' },
  { letter: 'C', textHtml: '2/3' },
  { letter: 'D', textHtml: '3/4' },
]

describe('AnswerButtons', () => {
  it('вызывает onSelect с буквой по клику', async () => {
    const onSelect = vi.fn()
    render(<AnswerButtons options={options} onSelect={onSelect} />)
    await userEvent.click(screen.getByRole('radio', { name: '1/3' }))
    expect(onSelect).toHaveBeenCalledWith('B')
  })

  it('после ответа все варианты заблокированы (disabled-после-ответа)', () => {
    render(
      <AnswerButtons
        options={options}
        status="answered"
        selectedLetter="B"
        isCorrect={false}
        onSelect={() => {}}
      />,
    )
    for (const option of options) {
      expect(screen.getByRole('radio', { name: option.textHtml })).toBeDisabled()
    }
  })

  it('верный ответ помечается ✓ (не только цветом)', () => {
    render(
      <AnswerButtons
        options={options}
        status="answered"
        selectedLetter="C"
        isCorrect
        onSelect={() => {}}
      />,
    )
    const correctButton = screen.getByRole('radio', { name: '2/3' })
    expect(correctButton).toHaveClass('border-correct')
    expect(correctButton).toHaveTextContent('✓')
  })

  it('неверный ответ — «ловушка», помечается ! (тёплая охра, не красный)', () => {
    render(
      <AnswerButtons
        options={options}
        status="answered"
        selectedLetter="A"
        isCorrect={false}
        onSelect={() => {}}
      />,
    )
    const trapButton = screen.getByRole('radio', { name: '1/2' })
    expect(trapButton).toHaveClass('border-trap')
    expect(trapButton).toHaveTextContent('!')
  })

  it('до ответа клик не блокируется', async () => {
    const onSelect = vi.fn()
    render(<AnswerButtons options={options} onSelect={onSelect} />)
    expect(screen.getByRole('radio', { name: '1/2' })).not.toBeDisabled()
    await userEvent.click(screen.getByRole('radio', { name: '1/2' }))
    expect(onSelect).toHaveBeenCalledWith('A')
  })
})
