import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useLesson } from './useLesson'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const lessonMessageRender = {
  fsm_state: 'lesson_theory',
  view: 'lesson_message',
  message: { message_id: 'm1', stage: 'theory', text_html: '<p>теория</p>' },
  lesson_progress: { step: 1, total: 5 },
  seq: 4,
  next_actions: ['advance', 'cancel'],
}

const dayHub = (fsmState: string) => ({
  fsm_state: fsmState,
  view: 'day_hub',
  message: null,
  seq: 0,
  next_actions: [],
  day: { streak_days: 2, warmup_available: false, has_lesson_today: true },
})

describe('useLesson', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('resume: E7 уже отдаёт сообщение урока — день/открытие не запрашиваются', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith('/api/lesson/current')) {
        return jsonResponse(200, lessonMessageRender)
      }
      throw new Error('не должен запрашиваться: ' + String(input))
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useLesson())
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.render?.view).toBe('lesson_message')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('resumable=true (api §4.6, fsm_state=registered после cancel) доходит до render как есть', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith('/api/lesson/current')) {
        return jsonResponse(200, {
          fsm_state: 'registered',
          view: 'lesson_message',
          message: { message_id: 'th2', stage: 'theory', text_html: '<p>th2</p>' },
          seq: 2,
          next_actions: [],
          resumable: true,
        })
      }
      throw new Error('не должен запрашиваться: ' + String(input))
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useLesson())
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.render?.resumable).toBe(true)
    expect(result.current.render?.fsm_state).toBe('registered')
    expect(fetchMock).toHaveBeenCalledTimes(1) // не уходит в день — это lesson-view
  })

  it('bootstrap хаба: registered → day → open_day → daily_start', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/lesson/current'))
        return jsonResponse(200, dayHub('registered'))
      if (url.endsWith('/api/day/open')) return jsonResponse(200, dayHub('daily_start'))
      if (url.endsWith('/api/day')) return jsonResponse(200, dayHub('registered'))
      throw new Error('unexpected ' + url)
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useLesson())
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.render?.fsm_state).toBe('daily_start')
  })

  it('сетевая ошибка → offline=true, прогресс (последний render) не теряется', async () => {
    let first = true
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/lesson/current')) {
        if (first) {
          first = false
          return jsonResponse(200, lessonMessageRender)
        }
        throw new TypeError('Failed to fetch')
      }
      throw new TypeError('Failed to fetch')
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useLesson())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.offline).toBe(false)

    // advance() бьёт по сети и падает с TypeError → offline.
    const advanceFetch = vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    })
    vi.stubGlobal('fetch', advanceFetch)
    await result.current.advance()

    await waitFor(() => expect(result.current.offline).toBe(true))
    expect(result.current.render?.view).toBe('lesson_message') // прогресс на месте
  })

  it('lesson_content_unavailable → contentMissing, без бесконечного ретрая', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(503, { error: 'lesson_content_unavailable', field: null }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useLesson())
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.contentMissing).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(1) // не зациклился
  })

  it('действие после ответа обновляет render и seq', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/lesson/current'))
        return jsonResponse(200, lessonMessageRender)
      if (url.endsWith('/api/lesson/advance')) {
        return jsonResponse(200, { ...lessonMessageRender, seq: 5 })
      }
      throw new Error('unexpected ' + url)
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useLesson())
    await waitFor(() => expect(result.current.loading).toBe(false))

    await result.current.advance()
    await waitFor(() => expect(result.current.render?.seq).toBe(5))
  })

  it('stale_message при действии → тихий ресинк через E7 (§5.2/§5.3)', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/lesson/current'))
        return jsonResponse(200, lessonMessageRender)
      if (url.endsWith('/api/lesson/advance')) {
        return jsonResponse(409, { error: 'stale_message', field: null })
      }
      throw new Error('unexpected ' + url)
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useLesson())
    await waitFor(() => expect(result.current.loading).toBe(false))

    await result.current.advance()
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([u]) => String(u).endsWith('/lesson/current'))
          .length,
      ).toBe(2),
    )
    expect(result.current.contentMissing).toBe(false)
    expect(result.current.offline).toBe(false)
  })
})
