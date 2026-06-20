import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  ApiError,
  getPdPolicy,
  submitRegistration,
  type RegistrationSuccess,
} from '../api/client'
import { ru } from '../i18n/ru'
import { transition, type RegEvent, type RegState } from './registrationMachine'

// Хук онбординга: держит КЛИЕНТСКИЙ draft (имя/класс/ogeprep/согласие) в памяти,
// генерирует onboarding_session_id (UUIDv4), тянет метаданные политики (E1) и
// выполняет единственный submit (E3) с идемпотентностью по Idempotency-Key.
// ПД на сервер уходят только в submit (152-ФЗ); сам draft на бэкенд не отправляется.

export interface UseRegistration {
  state: RegState
  name: string
  grade: number | null
  ogeprepAnswer: 'yes' | 'no' | null
  consent: boolean
  policyAvailable: boolean
  policyUrl: string | null
  submitting: boolean
  error: string | null
  result: RegistrationSuccess | null
  isProduction: boolean
  canSubmit: boolean
  setName: (value: string) => void
  setConsent: (checked: boolean) => void
  submitName: () => void
  selectGrade: (grade: number) => void
  ogeprepYes: () => void
  ogeprepNo: () => void
  mismatchContinue: () => void
  mismatchLeave: () => void
  back: () => void
  cancel: () => void
  dismissGate: () => void
  submit: () => Promise<void>
}

export function useRegistration(): UseRegistration {
  const [state, setState] = useState<RegState>('name_entry')
  const [name, setNameValue] = useState('')
  const [grade, setGrade] = useState<number | null>(null)
  const [ogeprepAnswer, setOgeprepAnswer] = useState<'yes' | 'no' | null>(null)
  const [consent, setConsentValue] = useState(false)
  const [policyVersion, setPolicyVersion] = useState<string | null>(null)
  const [policyUrl, setPolicyUrl] = useState<string | null>(null)
  const [policyAvailable, setPolicyAvailable] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<RegistrationSuccess | null>(null)

  // Ключ идемпотентности — UUIDv4, один на сессию онбординга (reg api §2.1).
  const sessionId = useRef<string>(crypto.randomUUID())
  const isProduction = import.meta.env.PROD

  // E1: метаданные политики ПД. До загрузки чекбокс согласия недоступен (RF-04).
  // Перезапрашивается и при 409 policy_version_mismatch на submit (RC-08/RC-14).
  // Примечание: 503 (RF-04) и «доступна, но available:false» сворачиваются в один
  // путь (policyVersion=null → canSubmit ложен) — для среза достаточно; различие
  // причины недоступности — на доработку RF-04-UX.
  const refreshPolicy = useCallback(async () => {
    try {
      const policy = await getPdPolicy()
      setPolicyVersion(policy.policy_version)
      setPolicyUrl(policy.policy_url)
      setPolicyAvailable(policy.available)
    } catch {
      setPolicyAvailable(false)
    }
  }, [])

  useEffect(() => {
    void refreshPolicy()
  }, [refreshPolicy])

  const dispatch = useCallback((event: RegEvent) => {
    setState((current) => transition(current, event) ?? current)
  }, [])

  const setName = useCallback((value: string) => setNameValue(value), [])
  const setConsent = useCallback((checked: boolean) => setConsentValue(checked), [])

  const submitName = useCallback(() => {
    dispatch({ type: 'name_submitted', namePresent: name.trim().length > 0 })
  }, [dispatch, name])

  const selectGrade = useCallback(
    (value: number) => {
      setGrade(value)
      setOgeprepAnswer(null) // смена класса сбрасывает уточнение
      dispatch({ type: 'grade_selected', grade: value, isProduction })
    },
    [dispatch, isProduction],
  )

  const ogeprepYes = useCallback(() => {
    setOgeprepAnswer('yes')
    dispatch({ type: 'ogeprep_yes' })
  }, [dispatch])

  const ogeprepNo = useCallback(() => {
    setOgeprepAnswer('no')
    dispatch({ type: 'ogeprep_no' })
  }, [dispatch])

  const mismatchContinue = useCallback(() => {
    dispatch({ type: 'mismatch_continue' })
  }, [dispatch])

  const mismatchLeave = useCallback(() => {
    dispatch({ type: 'mismatch_leave' })
  }, [dispatch])

  const back = useCallback(() => {
    setConsentValue(false) // возврат сбрасывает согласие (reg_v2)
    dispatch({ type: 'back' })
  }, [dispatch])

  const cancel = useCallback(() => {
    dispatch({ type: 'cancel_registration' })
  }, [dispatch])

  const dismissGate = useCallback(() => {
    dispatch({ type: 'gate_dismiss' })
  }, [dispatch])

  const canSubmit = useMemo(
    () =>
      name.trim().length > 0 &&
      grade !== null &&
      consent &&
      policyAvailable &&
      policyVersion !== null,
    [name, grade, consent, policyAvailable, policyVersion],
  )

  const submit = useCallback(async () => {
    if (!canSubmit || submitting || grade === null || policyVersion === null) return
    setSubmitting(true)
    setError(null)
    try {
      const success = await submitRegistration(
        {
          name: name.trim(),
          grade,
          ogeprep_answer: ogeprepAnswer,
          pd_consent_checked: consent,
          policy_version_shown: policyVersion,
        },
        sessionId.current,
      )
      setResult(success)
      // 201/200 → registered; повтор идемпотентен по тому же sessionId (RC-01/RF-07).
      dispatch({ type: 'submit_registration', canSubmit: true })
    } catch (err) {
      // 409 policy_version_mismatch (RC-08/RC-14): перезапрашиваем политику и сбрасываем
      // согласие — ученик переподтверждает актуальную версию (иначе повтор тем же телом
      // снова даст 409 — тупик). Прочее (422; registration_conflict → повтор даёт 200;
      // сеть) → общее сообщение; draft цел, повтор идемпотентен (RF-01/RF-02).
      if (err instanceof ApiError && err.code === 'policy_version_mismatch') {
        await refreshPolicy()
        setConsentValue(false)
      }
      setError(ru.reg.submit.error)
    } finally {
      setSubmitting(false)
    }
  }, [
    canSubmit,
    submitting,
    name,
    grade,
    ogeprepAnswer,
    consent,
    policyVersion,
    dispatch,
    refreshPolicy,
  ])

  return {
    state,
    name,
    grade,
    ogeprepAnswer,
    consent,
    policyAvailable,
    policyUrl,
    submitting,
    error,
    result,
    isProduction,
    canSubmit,
    setName,
    setConsent,
    submitName,
    selectGrade,
    ogeprepYes,
    ogeprepNo,
    mismatchContinue,
    mismatchLeave,
    back,
    cancel,
    dismissGate,
    submit,
  }
}
