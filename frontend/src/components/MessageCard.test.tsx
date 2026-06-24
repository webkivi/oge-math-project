import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { MessageCard } from './MessageCard'

describe('MessageCard', () => {
  it('рендерит HTML-содержимое сообщения', () => {
    render(<MessageCard textHtml="<p>Хук урока про дроби</p>" />)
    expect(screen.getByText('Хук урока про дроби')).toBeInTheDocument()
  })

  it('рендерит изображение внутри текста (чертёж блок 5)', () => {
    render(
      <MessageCard textHtml='<p>Смотри чертёж</p><img src="diagram.png" alt="чертёж" />' />,
    )
    expect(screen.getByRole('img', { name: 'чертёж' })).toBeInTheDocument()
  })
})
