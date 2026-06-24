import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { LessonHtml } from './LessonHtml'

describe('LessonHtml', () => {
  it('рендерит переданный HTML-контент', () => {
    render(<LessonHtml html="<p>сократили на 2</p>" />)
    expect(screen.getByText('сократили на 2')).toBeInTheDocument()
  })

  it('применяет className к обёртке', () => {
    const { container } = render(<LessonHtml html="<p>текст</p>" className="mt-1" />)
    expect(container.firstChild).toHaveClass('mt-1')
  })
})
