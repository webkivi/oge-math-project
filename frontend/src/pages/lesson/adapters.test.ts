import { describe, expect, it } from 'vitest'

import { toAnswerOptions } from './adapters'
import type { LessonMessageWire } from '../../api/lessonClient'

describe('toAnswerOptions', () => {
  it('маппит snake_case wire-опции в camelCase для AnswerButtons', () => {
    const message: LessonMessageWire = {
      message_id: 'm1',
      stage: 'training',
      text_html: '<p>?</p>',
      options: [
        { letter: 'A', text_html: '1/2' },
        { letter: 'B', text_html: '1/3' },
      ],
    }
    expect(toAnswerOptions(message)).toEqual([
      { letter: 'A', textHtml: '1/2' },
      { letter: 'B', textHtml: '1/3' },
    ])
  })

  it('возвращает пустой массив, если options отсутствуют (не вопрос-стадия)', () => {
    const message: LessonMessageWire = {
      message_id: 'm1',
      stage: 'theory',
      text_html: '<p>теория</p>',
    }
    expect(toAnswerOptions(message)).toEqual([])
  })
})
