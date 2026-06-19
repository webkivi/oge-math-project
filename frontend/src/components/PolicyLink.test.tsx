import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PolicyLink } from './PolicyLink'

describe('PolicyLink', () => {
  it('доступная политика — внешняя ссылка с href и rel', () => {
    render(<PolicyLink href="/policy">Политика</PolicyLink>)
    const link = screen.getByRole('link', { name: 'Политика' })
    expect(link).toHaveAttribute('href', '/policy')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('недоступная политика (RF-04) — не ссылка, без href и фокуса', () => {
    render(
      <PolicyLink href="/policy" available={false}>
        Политика
      </PolicyLink>,
    )
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText('Политика')).toBeInTheDocument()
  })
})
