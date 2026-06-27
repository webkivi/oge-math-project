// HTTP-клиент дневного потока и урока (раскладка v4 §7: src/api/client.ts).
// Эндпоинты E4–E12 — specs/student_lesson_api_v1.md §1.2/§4. Единый render-блок
// (§4.1): клиент шлёт ТОЛЬКО action+seq (+message_id/selected на вопрос-стадиях),
// семантику (correct/wrong/evt) деривит сервер (§2/§2.4, анти-подмена).

import { ApiError } from './client'

export type AnswerLetterWire = 'A' | 'B' | 'C' | 'D'

export interface LessonMessageWire {
  message_id: string
  stage: string
  text_html: string
  options?: { letter: AnswerLetterWire; text_html: string }[]
}

export interface LessonProgressWire {
  step: number
  total: number
}

export interface FeedbackWire {
  is_correct: boolean
  feedback_html: string
  return_target: string | null
}

export interface DayWire {
  streak_days: number
  warmup_available: boolean
  has_lesson_today: boolean
}

export type LessonView =
  | 'day_hub'
  | 'day_done'
  | 'day_blocked'
  | 'course_complete'
  | 'warmup'
  | 'repeat_pending'
  | 'repeat_question'
  | 'lesson_message'
  | 'lesson_question'
  | 'lesson_feedback'
  | 'lesson_final'
  | 'lesson_failed'

export interface LessonRender {
  fsm_state: string
  view: LessonView
  message: LessonMessageWire | null
  lesson_progress?: LessonProgressWire
  feedback?: FeedbackWire
  seq: number
  next_actions: string[]
  resumable?: boolean
  day?: DayWire
}

async function call(path: string, body?: unknown): Promise<LessonRender> {
  const response = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    credentials: 'same-origin', // принять httpOnly-cookie сессии
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await safeJson(response)
  if (!response.ok) {
    throw new ApiError(response.status, data.error ?? 'unknown', data.field ?? null)
  }
  return data as unknown as LessonRender
}

async function safeJson(
  response: Response,
): Promise<Record<string, unknown> & { error?: string; field?: string | null }> {
  try {
    return await response.json()
  } catch {
    return {}
  }
}

// E4: render дневного хаба + ленивая session_end-нормализация (§6.1).
export function getDay(): Promise<LessonRender> {
  return call('/api/day')
}

// E5: вход в день (registered → daily_start; идемпотентен в пределах дня, §4.2).
export function openDay(): Promise<LessonRender> {
  return call('/api/day/open', {})
}

// E6: утренняя разминка (§2.5).
export function warmupStart(): Promise<LessonRender> {
  return call('/api/day/warmup', { action: 'start' })
}

export function warmupSkip(): Promise<LessonRender> {
  return call('/api/day/warmup', { action: 'skip' })
}

export function warmupAnswer(
  messageId: string,
  selected: AnswerLetterWire,
): Promise<LessonRender> {
  return call('/api/day/warmup', {
    action: 'answer',
    message_id: messageId,
    selected,
  })
}

// E7: render текущего сохранённого сообщения (resume, EC-02). Read-only.
export function getCurrentLesson(): Promise<LessonRender> {
  return call('/api/lesson/current')
}

// E8: старт следующего незавершённого урока (R3-проскок hook на старте).
export function startLesson(seq: number): Promise<LessonRender> {
  return call('/api/lesson/start', { seq })
}

// E9: «Дальше» — сервер деривит evt по текущей стадии (§1.3).
export function advanceLesson(seq: number): Promise<LessonRender> {
  return call('/api/lesson/advance', { action: 'advance', seq })
}

// E10: ответ на вопрос (серверное судейство, §2).
export function answerLesson(
  messageId: string,
  selected: AnswerLetterWire,
  seq: number,
): Promise<LessonRender> {
  return call('/api/lesson/answer', { message_id: messageId, selected, seq })
}

// E11: «Выйти из урока» — прогресс сохранён (S-10).
export function cancelLesson(seq: number): Promise<LessonRender> {
  return call('/api/lesson/cancel', { seq })
}

// E12: ответ в R1/R2 — судим для feedback, переход по факту (§4.8).
export function repeatAnswer(
  messageId: string,
  selected: AnswerLetterWire,
  seq: number,
): Promise<LessonRender> {
  return call('/api/repeat/answer', { message_id: messageId, selected, seq })
}
