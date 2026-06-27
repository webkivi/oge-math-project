import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from './client'
import {
  advanceLesson,
  answerLesson,
  getDay,
  openDay,
  startLesson,
} from './lessonClient'

function stubFetch(status: number, body: unknown) {
  const fetchMock = vi.fn(
    async (_input?: RequestInfo | URL, _init?: RequestInit) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const render = {
  fsm_state: 'daily_start',
  view: 'day_hub',
  message: null,
  seq: 1,
  next_actions: [],
}

describe('lessonClient', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('E4 getDay — GET без тела', async () => {
    const fetchMock = stubFetch(200, render)
    await getDay()
    const [, init] = fetchMock.mock.calls[0]
    expect(init?.method).toBe('GET')
    expect(init?.body).toBeUndefined()
  })

  it('E5 openDay — POST с пустым телом', async () => {
    const fetchMock = stubFetch(200, render)
    await openDay()
    const [, init] = fetchMock.mock.calls[0]
    expect(init?.method).toBe('POST')
    expect(JSON.parse(init!.body as string)).toEqual({})
  })

  it('E8 startLesson — шлёт seq в теле', async () => {
    const fetchMock = stubFetch(200, render)
    await startLesson(7)
    const [, init] = fetchMock.mock.calls[0]
    expect(JSON.parse(init!.body as string)).toEqual({ seq: 7 })
  })

  it('E9 advanceLesson — action+seq', async () => {
    const fetchMock = stubFetch(200, render)
    await advanceLesson(3)
    const [, init] = fetchMock.mock.calls[0]
    expect(JSON.parse(init!.body as string)).toEqual({ action: 'advance', seq: 3 })
  })

  it('E10 answerLesson — message_id+selected+seq, не присылает evt/исход', async () => {
    const fetchMock = stubFetch(200, render)
    await answerLesson('m1', 'B', 5)
    const [, init] = fetchMock.mock.calls[0]
    expect(JSON.parse(init!.body as string)).toEqual({
      message_id: 'm1',
      selected: 'B',
      seq: 5,
    })
  })

  it('ошибка сервера → ApiError с кодом и полем из тела', async () => {
    stubFetch(409, { error: 'stale_message', field: null })
    await expect(advanceLesson(1)).rejects.toMatchObject(
      new ApiError(409, 'stale_message', null),
    )
  })
})
