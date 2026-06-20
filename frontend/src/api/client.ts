// HTTP-клиент регистрации (раскладка v4 §7: src/api/client.ts). Обращается к
// бэкенду через /api (в dev — проксируется Vite на uvicorn :8000). Реализует
// эндпоинты specs/student_registration_api_v1.md E1/E3.

export interface PdPolicyResponse {
  policy_version: string
  policy_url: string
  available: boolean
}

export interface RegistrationRequestBody {
  name: string
  grade: number
  ogeprep_answer: 'yes' | 'no' | null
  pd_consent_checked: boolean
  policy_version_shown: string
}

export interface RegistrationSuccess {
  user_id: string
  role: string
  grade: number
  fsm_state: string
  enrollment_reason: string
  current_lesson_id: string
  next: string
}

// Ошибка бэкенда по контракту §5: { error, field } + HTTP-статус.
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly field: string | null = null,
  ) {
    super(`${status} ${code}`)
    this.name = 'ApiError'
  }
}

// E1: метаданные Политики ПД. 503 → политика недоступна (RF-04).
export async function getPdPolicy(): Promise<PdPolicyResponse> {
  const response = await fetch('/api/pd-policy', {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    const body = await safeJson(response)
    throw new ApiError(response.status, body.error ?? 'pd_policy_unavailable')
  }
  return (await response.json()) as PdPolicyResponse
}

// E3: единственный submit. Идемпотентность — заголовок Idempotency-Key (§2.2).
// 201 (создан) и 200 (идемпотентный повтор) — успех; прочее → ApiError (§5).
export async function submitRegistration(
  body: RegistrationRequestBody,
  idempotencyKey: string,
): Promise<RegistrationSuccess> {
  const response = await fetch('/api/registration', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
    },
    // Допущение: API на том же origin (dev — Vite-прокси; prod — same-origin). При
    // деплое API на другой origin сменить на 'include' + серверный CORS (§6.1).
    credentials: 'same-origin', // принять httpOnly-cookie сессии (§6.1)
    body: JSON.stringify(body),
  })
  const data = await safeJson(response)
  if (response.status === 201 || response.status === 200) {
    return data as RegistrationSuccess
  }
  throw new ApiError(response.status, data.error ?? 'unknown', data.field ?? null)
}

async function safeJson(
  response: Response,
): Promise<{ error?: string; field?: string | null }> {
  try {
    return await response.json()
  } catch {
    return {}
  }
}
