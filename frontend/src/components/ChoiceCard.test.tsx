import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ChoiceCard } from './ChoiceCard'

describe('ChoiceCard', () => {
  it('вызывает onSelect по клику', async () => {
    const onSelect = vi.fn()
    render(<ChoiceCard onSelect={onSelect}>9 класс</ChoiceCard>)
    await userEvent.click(screen.getByRole('radio', { name: '9 класс' }))
    expect(onSelect).toHaveBeenCalledTimes(1)
  })

  it('selected помечается aria-checked (выбор не только цветом)', () => {
    render(
      <ChoiceCard selected onSelect={() => {}}>
        9 класс
      </ChoiceCard>,
    )
    expect(screen.getByRole('radio', { name: '9 класс' })).toBeChecked()
  })

  it('disabled не вызывает onSelect', async () => {
    const onSelect = vi.fn()
    render(
      <ChoiceCard disabled onSelect={onSelect}>
        8 класс
      </ChoiceCard>,
    )
    await userEvent.click(screen.getByRole('radio', { name: '8 класс' }))
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('selected дублируется нецветовым признаком — видимой галочкой (§5)', () => {
    const mark = () =>
      screen
        .getByRole('radio', { name: '9 класс' })
        .querySelector('[aria-hidden="true"]')
    const { rerender } = render(
      <ChoiceCard selected={false} onSelect={() => {}}>
        9 класс
      </ChoiceCard>,
    )
    expect(mark()).toHaveClass('text-transparent')
    rerender(
      <ChoiceCard selected onSelect={() => {}}>
        9 класс
      </ChoiceCard>,
    )
    expect(mark()).toHaveClass('text-primary')
  })
})
