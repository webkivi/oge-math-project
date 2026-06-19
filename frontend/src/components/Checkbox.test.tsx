import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Checkbox } from './Checkbox'

describe('Checkbox', () => {
  it('переключается и вызывает onCheckedChange', async () => {
    const onCheckedChange = vi.fn()
    render(
      <Checkbox checked={false} onCheckedChange={onCheckedChange}>
        Согласие
      </Checkbox>,
    )
    await userEvent.click(screen.getByLabelText('Согласие'))
    expect(onCheckedChange).toHaveBeenCalledWith(true)
  })

  it('disabled не переключается (RF-04)', async () => {
    const onCheckedChange = vi.fn()
    render(
      <Checkbox checked={false} disabled onCheckedChange={onCheckedChange}>
        Согласие
      </Checkbox>,
    )
    const checkbox = screen.getByLabelText('Согласие')
    expect(checkbox).toBeDisabled()
    await userEvent.click(checkbox)
    expect(onCheckedChange).not.toHaveBeenCalled()
  })
})
