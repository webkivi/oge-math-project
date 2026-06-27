import { useCallback, useEffect, useRef, useState } from 'react'

import {
  advanceLesson,
  answerLesson,
  cancelLesson,
  getCurrentLesson,
  getDay,
  openDay,
  repeatAnswer,
  startLesson,
  warmupAnswer,
  warmupSkip,
  warmupStart,
  type AnswerLetterWire,
  type LessonRender,
} from '../api/lessonClient'
import { ApiError } from '../api/client'

// useLesson — оркестрация дневного потока и урока (specs/student_lesson_api_v1.md).
// FSM — серверный (StudentProfile.fsm_state, v4 §1); этот хук НЕ держит собственную
// клиентскую таблицу переходов — он только отражает последний render-payload сервера
// и шлёт действия (action), а не события (анти-подмена, api §1.1/§2.4). Поэтому
// отдельного «useFSM» не заводим — был бы дублирующим источником истины.
//
// Bootstrap (без отдельного экрана lesson_select, §3.2): сначала E7 (resume) — если
// ученик уже в уроке/тёплая разминка-сессия, остаёмся там; иначе E4 (день, ленивая
// session_end-нормализация §6.1) и, если итог — registered, сразу E5 (открыть день),
// чтобы пользователь не видел промежуточного «registered» — только daily_start.

// Коды §5.2/§5.3, где правильная реакция клиента — тихо перечитать E7 и продолжить,
// а не показывать ошибку (дабл-клик/вторая вкладка/рассинхрон счётчика).
const RESYNC_CODES: ReadonlySet<string> = new Set([
  'stale_message',
  'wrong_action_for_stage',
  'guard_failed',
])

export interface UseLesson {
  render: LessonRender | null
  loading: boolean
  busy: boolean
  offline: boolean
  contentMissing: boolean
  startWarmup: () => Promise<void>
  /** «Открыть урок» при пустой очереди (daily_start) и «Пропустить разминку»
   * внутри morning_warmup — один и тот же транспорт E6 action=skip (api §2.5 п.5);
   * сервер сам деривит evt_warmup_skip/evt_warmup_complete по текущему state. */
  skipWarmup: () => Promise<void>
  warmupSelect: (letter: AnswerLetterWire) => Promise<void>
  startNextLesson: () => Promise<void>
  advance: () => Promise<void>
  select: (letter: AnswerLetterWire) => Promise<void>
  exitLesson: () => Promise<void>
  repeatSelect: (letter: AnswerLetterWire) => Promise<void>
  retry: () => Promise<void>
}

export function useLesson(): UseLesson {
  const [render, setRender] = useState<LessonRender | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [offline, setOffline] = useState(false)
  const [contentMissing, setContentMissing] = useState(false)
  const renderRef = useRef<LessonRender | null>(null)
  renderRef.current = render

  // bootstrap и handleError взаимно рекурсивны (resync-коды перечитывают через
  // bootstrap) — разрываем цикл зависимостей useCallback через ref, а не
  // подавлением eslint-предупреждения (handleError получает стабильную identity).
  const bootstrapRef = useRef<() => Promise<void>>(() => Promise.resolve())

  const handleError = useCallback((err: unknown) => {
    if (err instanceof ApiError) {
      if (RESYNC_CODES.has(err.code)) {
        // Сервер источник истины — перечитываем актуальную позицию (§5.2/§5.3).
        void bootstrapRef.current()
        return
      }
      // lesson_content_unavailable/lesson_not_found и прочие неожиданные коды —
      // НЕ ретраим автоматически (иначе при стабильно неверном коде уйдём в
      // бесконечный цикл bootstrap→ошибка→bootstrap). Один и тот же стаб экрана
      // «контент не загрузился» — честно и достаточно для этого среза.
      setContentMissing(true)
      return
    }
    // Сетевая ошибка (TypeError из fetch) — офлайн, прогресс на сервере не теряется.
    setOffline(true)
  }, [])

  const bootstrap = useCallback(async () => {
    setLoading(true)
    try {
      const resume = await getCurrentLesson()
      if (resume.view !== 'day_hub') {
        setRender(resume)
        setOffline(false)
        setContentMissing(false)
        return
      }
      let hub = await getDay()
      if (hub.fsm_state === 'registered') {
        hub = await openDay()
      }
      setRender(hub)
      setOffline(false)
      setContentMissing(false)
    } catch (err) {
      handleError(err)
    } finally {
      setLoading(false)
    }
  }, [handleError])
  bootstrapRef.current = bootstrap

  useEffect(() => {
    void bootstrap()
  }, [bootstrap])

  // Авто-восстановление при возврате сети (D-5: прогресс не теряется).
  useEffect(() => {
    const onOnline = () => void bootstrap()
    window.addEventListener('online', onOnline)
    return () => window.removeEventListener('online', onOnline)
  }, [bootstrap])

  const run = useCallback(
    (action: () => Promise<LessonRender>) => async () => {
      setBusy(true)
      try {
        const next = await action()
        setRender(next)
        setOffline(false)
        setContentMissing(false)
      } catch (err) {
        handleError(err)
      } finally {
        setBusy(false)
      }
    },
    [handleError],
  )

  const seq = () => renderRef.current?.seq ?? 0
  const currentMessageId = () => renderRef.current?.message?.message_id ?? ''

  const startWarmup = run(() => warmupStart())
  const skipWarmup = run(() => warmupSkip())
  const warmupSelect = (letter: AnswerLetterWire) =>
    run(() => warmupAnswer(currentMessageId(), letter))()
  const startNextLesson = run(() => startLesson(seq()))
  const advance = run(() => advanceLesson(seq()))
  const select = (letter: AnswerLetterWire) =>
    run(() => answerLesson(currentMessageId(), letter, seq()))()
  const exitLesson = run(() => cancelLesson(seq()))
  const repeatSelect = (letter: AnswerLetterWire) =>
    run(() => repeatAnswer(currentMessageId(), letter, seq()))()
  // Повтор после офлайна/ошибки — через bootstrap (resume-aware), а не голый E4:
  // если ученик был внутри урока, getDay() вернул бы day_hub и потерял бы экран (D-5).
  const retry = bootstrap

  return {
    render,
    loading,
    busy,
    offline,
    contentMissing,
    startWarmup,
    skipWarmup,
    warmupSelect,
    startNextLesson,
    advance,
    select,
    exitLesson,
    repeatSelect,
    retry,
  }
}
