# Спека: Роль «Ученик» и прохождение урока в PWA

**Версия:** v1  
**Дата:** 2026-06-16  
**Автор:** Агент 3 (Архитектор системы)  
**Источники:** Methodology v2.1 > Project Brain v3.2 > CLAUDE.md  
**Область:** ученик end-to-end (регистрация → урок → повторения → mastery). Родитель / учитель / репетитор — вне охвата.  
**Проверяют:** Агент 4 (Критик системы) + validator.py

---

## 0. Открытые развилки (решает фаундер)

| # | Развилка | Почему блокер |
|---|----------|---------------|
| D-1 | Нужна ли возможность смены имени и/или класса после регистрации? | Влияет на наличие операции `write` по ресурсу `user_profile` |
| D-2 | Порог «3 ошибки подряд на закреплении» — применяется ко всему блоку тренировки (Q1–Q3 суммарно) или только к конкретному вопросу? | Методология §2.2.1 говорит «3 ошибки подряд», Brain §5.3 — «на закреплении». Трактовка не однозначна: спека трактует как «3 ошибки на один тренировочный вопрос подряд (внутри одной итерации возврата)». Если иное — уточнить. |
| D-3 | Логика «передышки» (streak freeze): 1 в неделю, но когда именно активируется — автоматически или ученик нажимает кнопку? | Влияет на FSM-переход `streak_freeze_apply`. Спека принимает: **автоматически** — система применяет передышку при первом пропуске, если лимит не исчерпан. |
| D-4 | Утренняя разминка (R3 / review_queue): запускается строго в 08:00 или при первом входе в день? | Влияет на архитектуру push + scheduler. Спека принимает: push в 08:00, но разминка доступна при любом входе до конца учебного дня. |
| D-5 | Что показывать ученику, если он открывает PWA без интернета в момент прохождения урока (не закэшированный контент)? | Офлайн-режим service worker — отдельная спека. Здесь: если контент не в кэше — показать заглушку «нет соединения» без потери прогресса. |

---

## 1. Словарь сущностей

| Сущность | Описание | Ключевые атрибуты | Связи |
|----------|----------|-------------------|-------|
| **User** | Аккаунт пользователя любой роли | `id`, `role` (student/parent/teacher/tutor), `name`, `grade` (только student), `created_at`, `pwa_push_token` | 1:1 → StudentProfile (если role=student) |
| **StudentProfile** | Расширенный профиль ученика | `user_id`, `current_lesson_id`, `course_started_at` | 1:1 → User; 1:N → Progress; 1:1 → Streak; 1:N → ReviewQueue |
| **Lesson** | Метаданные урока (читаются из CSV) | `lesson_id` (string, без точек), `block_id`, `title`, `total_messages` | 1:N → LessonMessage |
| **LessonMessage** | Одно сообщение урока из CSV | `message_id` (с префиксом для блоков 1.2+), `lesson_id`, `stage` (hook/theory/example/training/main_question/main_question_backup/final/lesson_failed/repeat_1h/repeat_evening/repeat_morning), `text` (HTML), `option_a..d`, `correct_answer`, `feedback_a..d`, `return_a..d` | N:1 → Lesson |
| **Progress** | Состояние прохождения урока учеником | `id`, `user_id`, `lesson_id`, `status` (not_started/in_progress/passed/failed_today), `main_question_attempts` (0..3), `training_errors` (JSON: счётчик ошибок по вопросу), `current_message_id`, `started_at`, `completed_at`, `passed_on_attempt` (1/2/null) | N:1 → User; N:1 → Lesson |
| **Streak** | Счётчик непрерывных учебных дней | `user_id`, `current_streak`, `longest_streak`, `last_active_date`, `freeze_used_this_week` (bool) | 1:1 → StudentProfile |
| **ReviewQueue** | Очередь тем для повторения (interval ≥ 1 день) | `id`, `user_id`, `lesson_id`, `reason` (passed_attempt_2 / interval_1d / interval_3d / interval_7d / interval_14d / interval_30d), `due_date`, `done` | N:1 → StudentProfile |
| **ReminderState** | Флаги триггеров push-напоминаний | `user_id`, `last_notified_at`, `skip_days_count`, `freeze_applied_date` | 1:1 → StudentProfile |
| **DailySession** | Агрегат активности за учебный день | `user_id`, `date`, `lessons_completed`, `reviews_completed`, `morning_warmup_done` | N:1 → User |

### Инварианты модели данных

- Регистрация собирает только: **имя** + **класс** (152-ФЗ, минимизация ПД). Никакого телефона/email.
- `lesson_id` никогда не содержит точку (хранится keeper.py).
- `return_X` — дословно совпадает с существующим `message_id` того же урока (хранится keeper.py).
- `correct_answer` — английская заглавная буква A/B/C/D (хранится keeper.py).

---

## 2. Конечный автомат (FSM) — роль «Ученик»

### 2а. Mermaid-диаграмма

```mermaid
stateDiagram-v2
    [*] --> unregistered

    unregistered --> onboarding : evt_open_pwa
    onboarding --> registered : evt_submit_registration
    onboarding --> unregistered : evt_cancel_registration

    registered --> daily_start : evt_open_app
    daily_start --> morning_warmup : evt_warmup_available [review_queue не пуста ИЛИ due_date <= today]
    daily_start --> lesson_select : evt_warmup_skip [нет очереди или ученик пропускает]
    morning_warmup --> lesson_select : evt_warmup_complete

    lesson_select --> lesson_hook : evt_start_lesson
    lesson_select --> daily_done : evt_no_lesson_today [все уроки дня пройдены]

    lesson_hook --> lesson_theory : evt_hook_read
    lesson_theory --> lesson_example : evt_theory_read
    lesson_example --> lesson_training : evt_example_read

    lesson_training --> lesson_training : evt_answer_correct [ещё есть тренировочные вопросы]
    lesson_training --> lesson_training : evt_answer_wrong [попыток < 3 на этот вопрос → return_X → следующий вопрос]
    lesson_training --> lesson_main_question : evt_training_complete [все Q1..Q3 пройдены]

    lesson_main_question --> lesson_final : evt_main_correct_attempt1 [1-я попытка верно]
    lesson_main_question --> lesson_theory_review : evt_main_wrong_attempt1 [1-я попытка неверно]
    lesson_theory_review --> lesson_main_question_backup : evt_theory_reviewed
    lesson_main_question_backup --> lesson_final : evt_main_correct_attempt2 [2-я попытка верно]
    lesson_main_question_backup --> lesson_failed : evt_main_wrong_attempt2 [2-я попытка неверно — 3 ошибки израсходованы]

    lesson_final --> repeat_1h_pending : evt_lesson_complete
    lesson_failed --> daily_blocked : evt_lesson_fail_confirmed

    repeat_1h_pending --> repeat_1h_active : evt_1h_elapsed
    repeat_1h_active --> repeat_evening_pending : evt_repeat_1h_answered
    repeat_evening_pending --> repeat_evening_active : evt_evening_time [~21:00]
    repeat_evening_active --> review_queue_scheduled : evt_repeat_evening_answered

    daily_blocked --> registered : evt_next_day [следующий учебный день]
    review_queue_scheduled --> registered : evt_session_end
    daily_done --> registered : evt_session_end

    registered --> streak_update : evt_day_end [end-of-day job]
    streak_update --> registered : evt_streak_updated
```

> **Примечание по FSM:** Состояния `lesson_theory`, `lesson_example`, `lesson_training`, `lesson_main_question`, `lesson_theory_review`, `lesson_main_question_backup`, `lesson_final`, `lesson_failed` — sub-states внутри макро-состояния «в уроке». Для validator.py они развёрнуты плоско (см. YAML ниже).

---

### 2б. YAML-блок для validator.py

```yaml
role: student
states:
  - id: unregistered
    type: start
  - id: onboarding
    type: normal
  - id: registered
    type: normal
  - id: daily_start
    type: normal
  - id: morning_warmup
    type: normal
  - id: lesson_select
    type: normal
  - id: lesson_hook
    type: normal
  - id: lesson_theory
    type: normal
  - id: lesson_example
    type: normal
  - id: lesson_training
    type: normal
  - id: lesson_main_question
    type: normal
  - id: lesson_theory_review
    type: normal
  - id: lesson_main_question_backup
    type: normal
  - id: lesson_final
    type: normal
  - id: lesson_failed
    type: normal
  - id: repeat_1h_pending
    type: normal
  - id: repeat_1h_active
    type: normal
  - id: repeat_evening_pending
    type: normal
  - id: repeat_evening_active
    type: normal
  - id: review_queue_scheduled
    type: normal
  - id: daily_blocked
    type: normal
  - id: daily_done
    type: normal
  - id: streak_update
    type: normal
  - id: course_complete
    type: end

events:
  - id: evt_open_pwa
  - id: evt_submit_registration
  - id: evt_cancel_registration
  - id: evt_open_app
  - id: evt_warmup_available
  - id: evt_warmup_skip
  - id: evt_warmup_complete
  - id: evt_start_lesson
  - id: evt_no_lesson_today
  - id: evt_hook_read
  - id: evt_theory_read
  - id: evt_example_read
  - id: evt_answer_correct
  - id: evt_answer_wrong
  - id: evt_training_complete
  - id: evt_main_correct_attempt1
  - id: evt_main_wrong_attempt1
  - id: evt_main_correct_attempt2
  - id: evt_main_wrong_attempt2
  - id: evt_theory_reviewed
  - id: evt_lesson_complete
  - id: evt_lesson_fail_confirmed
  - id: evt_1h_elapsed
  - id: evt_repeat_1h_answered
  - id: evt_evening_time
  - id: evt_repeat_evening_answered
  - id: evt_session_end
  - id: evt_next_day
  - id: evt_day_end
  - id: evt_streak_updated
  - id: evt_all_lessons_done

transitions:
  # --- Регистрация ---
  - from: unregistered
    event: evt_open_pwa
    to: onboarding
    guard: null

  - from: onboarding
    event: evt_submit_registration
    to: registered
    guard: "name присутствует AND grade в диапазоне 8..11"

  - from: onboarding
    event: evt_cancel_registration
    to: unregistered
    guard: null

  # --- Вход в приложение ---
  - from: registered
    event: evt_open_app
    to: daily_start
    guard: null

  # --- Утренняя разминка ---
  - from: daily_start
    event: evt_warmup_available
    to: morning_warmup
    guard: "review_queue содержит записи с due_date <= today"

  - from: daily_start
    event: evt_warmup_skip
    to: lesson_select
    guard: "review_queue пуста ИЛИ ученик нажал 'пропустить'"

  - from: morning_warmup
    event: evt_warmup_complete
    to: lesson_select
    guard: null

  # --- Выбор урока ---
  - from: lesson_select
    event: evt_start_lesson
    to: lesson_hook
    guard: "следующий незавершённый урок существует AND status != failed_today"

  - from: lesson_select
    event: evt_no_lesson_today
    to: daily_done
    guard: "нет доступных уроков на сегодня (daily_blocked OR все пройдены)"

  # --- Прохождение урока ---
  - from: lesson_hook
    event: evt_hook_read
    to: lesson_theory
    guard: null

  - from: lesson_theory
    event: evt_theory_read
    to: lesson_example
    guard: null

  - from: lesson_example
    event: evt_example_read
    to: lesson_training
    guard: null

  - from: lesson_training
    event: evt_answer_correct
    to: lesson_training
    guard: "остались непройденные тренировочные вопросы"

  - from: lesson_training
    event: evt_answer_correct
    to: lesson_main_question
    guard: "все тренировочные вопросы (Q1..Q3) пройдены"

  - from: lesson_training
    event: evt_answer_wrong
    to: lesson_training
    guard: "возврат по return_X к теории, затем новый вопрос на тот же навык"

  - from: lesson_training
    event: evt_training_complete
    to: lesson_main_question
    guard: null

  # --- Главный вопрос (mastery learning) ---
  - from: lesson_main_question
    event: evt_main_correct_attempt1
    to: lesson_final
    guard: "main_question_attempts == 0 AND ответ верен"

  - from: lesson_main_question
    event: evt_main_wrong_attempt1
    to: lesson_theory_review
    guard: "main_question_attempts == 0 AND ответ неверен"

  - from: lesson_theory_review
    event: evt_theory_reviewed
    to: lesson_main_question_backup
    guard: null

  - from: lesson_main_question_backup
    event: evt_main_correct_attempt2
    to: lesson_final
    guard: "main_question_attempts == 1 AND ответ верен → добавить урок в review_queue (reason=passed_attempt_2)"

  - from: lesson_main_question_backup
    event: evt_main_wrong_attempt2
    to: lesson_failed
    guard: "main_question_attempts == 2 AND ответ неверен"

  # --- Финал и провал ---
  - from: lesson_final
    event: evt_lesson_complete
    to: repeat_1h_pending
    guard: "записать Progress.status=passed, обновить Streak, запланировать R1/R2/R3 и interval-повторения"

  - from: lesson_failed
    event: evt_lesson_fail_confirmed
    to: daily_blocked
    guard: "записать Progress.status=failed_today, добавить урок в review_queue (reason=interval_1d, due_date=tomorrow)"

  # --- Повторения R1/R2 ---
  - from: repeat_1h_pending
    event: evt_1h_elapsed
    to: repeat_1h_active
    guard: "прошёл 1 час после evt_lesson_complete (scheduler или push)"

  - from: repeat_1h_active
    event: evt_repeat_1h_answered
    to: repeat_evening_pending
    guard: null

  - from: repeat_evening_pending
    event: evt_evening_time
    to: repeat_evening_active
    guard: "текущее время >= 21:00 локального времени ученика"

  - from: repeat_evening_active
    event: evt_repeat_evening_answered
    to: review_queue_scheduled
    guard: "добавить интервальные повторения в review_queue (1/3/7/14/30 дней)"

  # --- Завершение сессии ---
  - from: review_queue_scheduled
    event: evt_session_end
    to: registered
    guard: null

  - from: daily_done
    event: evt_session_end
    to: registered
    guard: null

  - from: daily_blocked
    event: evt_next_day
    to: registered
    guard: "наступил следующий учебный день (scheduler)"

  # --- Streak ---
  - from: registered
    event: evt_day_end
    to: streak_update
    guard: "ежедневный job 23:59 по расписанию"

  - from: streak_update
    event: evt_streak_updated
    to: registered
    guard: "если DailySession.lessons_completed >= 1 ИЛИ reviews_completed >= 1: streak+1; иначе: применить freeze (если доступна) или сбросить streak"

  # --- Завершение курса ---
  - from: lesson_select
    event: evt_all_lessons_done
    to: course_complete
    guard: "все 27 уроков имеют status=passed"

# Комментарии по необработанным событиям:
# evt_open_pwa в состоянии registered: невозможно — пользователь уже зарегистрирован и авторизован
# evt_submit_registration в состоянии registered: невозможно — повторная регистрация не поддерживается
# evt_start_lesson в состоянии daily_blocked: невозможно — заблокировано до следующего дня (mastery learning)
# evt_answer_wrong на главном вопросе 3-й раз без перехода через lesson_theory_review: невозможно — архитектурно исключено (Q4 → Q4b, третьей попытки нет)
```

---

## 3. Матрица прав

### 3а. Markdown-таблица

| Роль | Ресурс | Операция | Allow | Условие |
|------|--------|----------|-------|---------|
| student | user_profile (свой) | read | true | user_id совпадает |
| student | user_profile (свой) | write | false | — (см. развилка D-1) |
| student | user_profile (чужой) | read | false | — |
| student | user_profile (чужой) | write | false | — |
| student | lesson_content | read | true | урок принадлежит курсу ученика |
| student | lesson_content | write | false | — |
| student | lesson_content | create | false | — |
| student | lesson_content | delete | false | — |
| student | progress (свой) | read | true | user_id совпадает |
| student | progress (свой) | write | true | только через FSM-переходы (бэкенд), не напрямую |
| student | progress (свой) | create | true | при старте урока |
| student | progress (свой) | delete | false | — |
| student | progress (чужой) | read | false | — |
| student | progress (чужой) | write | false | — |
| student | streak (свой) | read | true | user_id совпадает |
| student | streak (свой) | write | false | только через бэкенд-job |
| student | streak (чужой) | read | false | — |
| student | review_queue (свой) | read | true | user_id совпадает |
| student | review_queue (свой) | write | false | только через FSM-переходы бэкенда |
| student | review_queue (чужой) | read | false | — |
| student | reminder_state (свой) | read | true | user_id совпадает |
| student | reminder_state (свой) | write | false | только через бэкенд (push-токен обновляется service worker) |
| student | daily_session (свой) | read | true | user_id совпадает |
| student | daily_session (свой) | write | false | только через бэкенд-агрегатор |
| student | links | read | false | — (привязки взрослых не видны ученику в PWA в v1) |
| student | links | write | false | — |
| student | links | create | true | генерация своего короткого кода для родителя/репетитора |
| student | links | delete | false | — |
| student | classes | read | false | — |
| student | classes | write | false | — |
| student | push_token (свой) | write | true | при согласии на push в браузере |

### 3б. YAML-блок

```yaml
permissions:
  # --- user_profile ---
  - role: student
    resource: user_profile_own
    operation: read
    allow: true
    guard: "user_id совпадает с аутентифицированным"

  - role: student
    resource: user_profile_own
    operation: write
    allow: false
    guard: null  # развилка D-1 не решена; deny until resolved

  - role: student
    resource: user_profile_own
    operation: create
    allow: true
    guard: "только при регистрации, role=student"

  - role: student
    resource: user_profile_own
    operation: delete
    allow: false
    guard: null

  - role: student
    resource: user_profile_other
    operation: read
    allow: false
    guard: null

  - role: student
    resource: user_profile_other
    operation: write
    allow: false
    guard: null

  - role: student
    resource: user_profile_other
    operation: create
    allow: false
    guard: null

  - role: student
    resource: user_profile_other
    operation: delete
    allow: false
    guard: null

  # --- lesson_content ---
  - role: student
    resource: lesson_content
    operation: read
    allow: true
    guard: "lesson принадлежит курсу; контент только для чтения из CSV"

  - role: student
    resource: lesson_content
    operation: write
    allow: false
    guard: null

  - role: student
    resource: lesson_content
    operation: create
    allow: false
    guard: null

  - role: student
    resource: lesson_content
    operation: delete
    allow: false
    guard: null

  # --- progress ---
  - role: student
    resource: progress_own
    operation: read
    allow: true
    guard: "user_id совпадает"

  - role: student
    resource: progress_own
    operation: write
    allow: true
    guard: "только через FSM-эндпоинты бэкенда; прямой PUT/PATCH на progress запрещён"

  - role: student
    resource: progress_own
    operation: create
    allow: true
    guard: "при старте урока через FSM"

  - role: student
    resource: progress_own
    operation: delete
    allow: false
    guard: null

  - role: student
    resource: progress_other
    operation: read
    allow: false
    guard: null

  - role: student
    resource: progress_other
    operation: write
    allow: false
    guard: null

  - role: student
    resource: progress_other
    operation: create
    allow: false
    guard: null

  - role: student
    resource: progress_other
    operation: delete
    allow: false
    guard: null

  # --- streak ---
  - role: student
    resource: streak_own
    operation: read
    allow: true
    guard: "user_id совпадает"

  - role: student
    resource: streak_own
    operation: write
    allow: false
    guard: "только бэкенд-job (day_end scheduler)"

  - role: student
    resource: streak_own
    operation: create
    allow: false
    guard: "создаётся автоматически при регистрации"

  - role: student
    resource: streak_own
    operation: delete
    allow: false
    guard: null

  - role: student
    resource: streak_other
    operation: read
    allow: false
    guard: null

  - role: student
    resource: streak_other
    operation: write
    allow: false
    guard: null

  - role: student
    resource: streak_other
    operation: create
    allow: false
    guard: null

  - role: student
    resource: streak_other
    operation: delete
    allow: false
    guard: null

  # --- review_queue ---
  - role: student
    resource: review_queue_own
    operation: read
    allow: true
    guard: "user_id совпадает"

  - role: student
    resource: review_queue_own
    operation: write
    allow: false
    guard: "только через FSM-переходы"

  - role: student
    resource: review_queue_own
    operation: create
    allow: false
    guard: "создаётся через FSM"

  - role: student
    resource: review_queue_own
    operation: delete
    allow: false
    guard: null

  - role: student
    resource: review_queue_other
    operation: read
    allow: false
    guard: null

  - role: student
    resource: review_queue_other
    operation: write
    allow: false
    guard: null

  - role: student
    resource: review_queue_other
    operation: create
    allow: false
    guard: null

  - role: student
    resource: review_queue_other
    operation: delete
    allow: false
    guard: null

  # --- reminder_state ---
  - role: student
    resource: reminder_state_own
    operation: read
    allow: true
    guard: "user_id совпадает"

  - role: student
    resource: reminder_state_own
    operation: write
    allow: false
    guard: "управляется бэкендом и service worker"

  - role: student
    resource: reminder_state_own
    operation: create
    allow: false
    guard: null

  - role: student
    resource: reminder_state_own
    operation: delete
    allow: false
    guard: null

  # --- daily_session ---
  - role: student
    resource: daily_session_own
    operation: read
    allow: true
    guard: "user_id совпадает"

  - role: student
    resource: daily_session_own
    operation: write
    allow: false
    guard: "только бэкенд-агрегатор"

  - role: student
    resource: daily_session_own
    operation: create
    allow: false
    guard: null

  - role: student
    resource: daily_session_own
    operation: delete
    allow: false
    guard: null

  # --- links (привязка к взрослым) ---
  - role: student
    resource: links_own_code
    operation: read
    allow: true
    guard: "только свой код — для показа родителю/репетитору"

  - role: student
    resource: links_own_code
    operation: write
    allow: false
    guard: null

  - role: student
    resource: links_own_code
    operation: create
    allow: true
    guard: "генерация короткого кода для привязки взрослого"

  - role: student
    resource: links_own_code
    operation: delete
    allow: false
    guard: null

  - role: student
    resource: links_details
    operation: read
    allow: false
    guard: "ученик не видит список привязанных взрослых в v1"

  - role: student
    resource: links_details
    operation: write
    allow: false
    guard: null

  - role: student
    resource: links_details
    operation: create
    allow: false
    guard: null

  - role: student
    resource: links_details
    operation: delete
    allow: false
    guard: null

  # --- classes ---
  - role: student
    resource: classes
    operation: read
    allow: false
    guard: null

  - role: student
    resource: classes
    operation: write
    allow: false
    guard: null

  - role: student
    resource: classes
    operation: create
    allow: false
    guard: null

  - role: student
    resource: classes
    operation: delete
    allow: false
    guard: null

  # --- push_token ---
  - role: student
    resource: push_token_own
    operation: write
    allow: true
    guard: "при явном согласии пользователя на push-уведомления"

  - role: student
    resource: push_token_own
    operation: read
    allow: false
    guard: "токен не возвращается в API-ответах клиенту"

  - role: student
    resource: push_token_own
    operation: create
    allow: true
    guard: "при регистрации push-подписки"

  - role: student
    resource: push_token_own
    operation: delete
    allow: true
    guard: "при отзыве согласия на push"
```

---

## 4. Межролевые сценарии

> Охват v1: только роль «ученик». Сценарии с другими ролями — в будущих спеках.

---

### Сценарий S-01: Регистрация нового ученика

**Участники:** ученик  
**Предусловие:** пользователь открыл PWA впервые, аккаунта нет  

| Шаг | Актор | Действие | Результат |
|-----|-------|----------|-----------|
| 1 | Ученик | Открывает PWA по ссылке | Система: `evt_open_pwa` → состояние `onboarding` |
| 2 | Система | Показывает экран регистрации: поля «Как тебя зовут?» и «В каком ты классе?» (выбор 8–11); показывает ограничения курса (кому подходит, кому нет) | Экран регистрации отображён |
| 3 | Ученик | Вводит имя «Иван», выбирает класс «9» | Форма заполнена |
| 4 | Ученик | Нажимает «Начать» | `evt_submit_registration` |
| 5 | Система | Проверяет: name не пустое, grade в 8..11 | Валидация пройдена |
| 6 | Система | Создаёт User (role=student, name=Иван, grade=9), StudentProfile, Streak (current=0), DailySession | БД обновлена |
| 7 | Система | Переводит в `registered`, показывает первый урок | Состояние `registered` → `daily_start` → `lesson_select` |

**Постусловие:** User и StudentProfile созданы; ПД — только имя и класс.

---

### Сценарий S-02: Прохождение урока, главный вопрос с 1-й попытки

**Участники:** ученик  
**Предусловие:** ученик зарегистрирован; Progress для урока 1.1 — not_started  

| Шаг | Актор | Действие | Результат |
|-----|-------|----------|-----------|
| 1 | Ученик | Открывает PWA | `evt_open_app` → `daily_start` |
| 2 | Система | Проверяет review_queue: пуста | `evt_warmup_skip` → `lesson_select` |
| 3 | Ученик | Нажимает «Начать урок 1.1» | `evt_start_lesson` → `lesson_hook` |
| 4 | Система | Отображает hook-сообщение | — |
| 5 | Ученик | Читает, нажимает «Далее» | `evt_hook_read` → `lesson_theory` |
| 6 | Система | Показывает theory-сообщения (1–2 экрана) | — |
| 7 | Ученик | Читает, нажимает «Далее» | `evt_theory_read` → `lesson_example` |
| 8 | Система | Показывает example | — |
| 9 | Ученик | «Далее» | `evt_example_read` → `lesson_training` |
| 10 | Система | Показывает Q1 (training) | — |
| 11 | Ученик | Отвечает верно на Q1, Q2, Q3 | `evt_answer_correct` × 3 → после Q3: `evt_training_complete` → `lesson_main_question` |
| 12 | Система | Показывает главный вопрос (stage: main_question) | — |
| 13 | Ученик | Отвечает верно с 1-й попытки | `evt_main_correct_attempt1` → `lesson_final` |
| 14 | Система | Показывает финал («День 1 ✓»), обновляет Streak +1, записывает Progress.status=passed, passed_on_attempt=1 | — |
| 15 | Система | `evt_lesson_complete` → `repeat_1h_pending`; планирует R1 (через 1 ч), R2 (~21:00), добавляет в review_queue interval_1d, записывает DailySession | Урок полностью засчитан |

**Постусловие:** Progress.status=passed, passed_on_attempt=1; review_queue содержит записи для interval-повторений; тема в review_queue на следующее утро НЕ добавляется (1-я попытка).

---

### Сценарий S-03: Прохождение урока, главный вопрос со 2-й попытки

**Предусловие:** как S-02, но ученик ошибается на главном вопросе  

| Шаг | Актор | Действие | Результат |
|-----|-------|----------|-----------|
| 1–11 | — | Аналогично S-02 до шага 12 | `lesson_main_question` |
| 12 | Ученик | Отвечает неверно | `evt_main_wrong_attempt1` → `lesson_theory_review`; main_question_attempts=1 |
| 13 | Система | Показывает объяснение ошибки (feedback), затем возвращает к ключевому theory-сообщению (return_X) | — |
| 14 | Ученик | Перечитывает теорию, нажимает «Далее» | `evt_theory_reviewed` → `lesson_main_question_backup` |
| 15 | Система | Показывает резервный главный вопрос (stage: main_question_backup) | — |
| 16 | Ученик | Отвечает верно | `evt_main_correct_attempt2` → `lesson_final` |
| 17 | Система | Показывает финал, Progress.status=passed, passed_on_attempt=2; **добавляет урок в review_queue (reason=passed_attempt_2, due_date=завтра утром)** | Урок засчитан, но тема всплывёт завтра в разминке |

**Постусловие:** Progress.status=passed, passed_on_attempt=2; review_queue содержит запись passed_attempt_2 + стандартные interval-повторения.

---

### Сценарий S-04: Провал урока (3-я ошибка на главном вопросе)

**Предусловие:** ученик уже ошибся на главном вопросе один раз (после S-03 шаг 16 — ошибка)

| Шаг | Актор | Действие | Результат |
|-----|-------|----------|-----------|
| 1 | — | Ученик на `lesson_main_question_backup` | — |
| 2 | Ученик | Отвечает неверно | `evt_main_wrong_attempt2` → `lesson_failed` |
| 3 | Система | Показывает lesson_failed сообщение: «Вернёмся к этому завтра — так лучше запомнится» | — |
| 4 | Ученик | Подтверждает | `evt_lesson_fail_confirmed` → `daily_blocked` |
| 5 | Система | Записывает Progress.status=failed_today; добавляет урок в review_queue (reason=interval_1d, due_date=tomorrow); новые уроки сегодня недоступны | daily_blocked |
| 6 | Scheduler | Следующий учебный день | `evt_next_day` → `registered` |

**Постусловие:** сегодня новых уроков нет; завтра урок повторяется; Streak: если до этого была активность сегодня — не сбрасывается.

---

### Сценарий S-05: Утренняя разминка (R3 / review_queue)

**Предусловие:** ученик пришёл на следующий день; review_queue содержит записи с due_date <= today  

| Шаг | Актор | Действие | Результат |
|-----|-------|----------|-----------|
| 1 | Система | Отправляет push в 08:00 «Утренняя разминка» | — |
| 2 | Ученик | Открывает PWA | `evt_open_app` → `daily_start` |
| 3 | Система | Проверяет review_queue: есть записи с due_date <= today | `evt_warmup_available` → `morning_warmup` |
| 4 | Система | Показывает 3 вопроса interleaved из разных пройденных уроков | — |
| 5 | Ученик | Отвечает (верно/неверно — с объяснением) | — |
| 6 | Система | `evt_warmup_complete` → `lesson_select`; обновляет review_queue (done=true или сдвигает due_date если ошибка) | — |

**Постусловие:** review_queue обновлена; ученик переходит к новому уроку дня.

---

### Сценарий S-06: Тренировочный вопрос с ошибкой и возвратом к теории

**Предусловие:** ученик в состоянии `lesson_training`, отвечает на Q2 неверно  

| Шаг | Актор | Действие | Результат |
|-----|-------|----------|-----------|
| 1 | Ученик | Выбирает неверный вариант на Q2 | `evt_answer_wrong` |
| 2 | Система | Показывает feedback_X для неверного варианта; затем перемещает к сообщению, указанному в return_X (конкретный theory/example) | Состояние остаётся `lesson_training` |
| 3 | Ученик | Перечитывает теорию | — |
| 4 | Система | Показывает новый вопрос на тот же навык (следующий message_id того же навыка или повтор с другим условием) | — |
| 5 | Ученик | Отвечает верно | `evt_answer_correct` → продолжение тренировки |

**Постусловие:** прогресс по тренировке не сбрасывается полностью; ошибка фиксируется в Progress.training_errors.

---

### Сценарий S-07: Streak — пропуск и передышка

**Предусловие:** ученик активен 5 дней подряд; пропускает 1 день; freeze_used_this_week=false  

| Шаг | Актор | Действие | Результат |
|-----|-------|----------|-----------|
| 1 | Scheduler | 23:59 — `evt_day_end` → `streak_update` | — |
| 2 | Система | DailySession за сегодня: lessons_completed=0, reviews_completed=0 | — |
| 3 | Система | freeze_used_this_week=false → автоматически применяет передышку: streak не сбрасывается, freeze_used_this_week=true | Streak сохранён |
| 4 | Ученик | Открывает PWA на следующий день | Видит сообщение «Использую передышку — счётчик сохранён» |

**Постусловие:** streak сохранён; следующий пропуск на той же неделе — streak сбрасывается в 0.

---

## 5. Edge Cases

| id | Условие (что нестандартного) | Ожидаемое поведение системы |
|----|------------------------------|----------------------------|
| EC-01 | Ученик дважды нажимает «Далее» за доли секунды (дабл-клик) | Фронтенд блокирует кнопку после первого нажатия до получения ответа от бэкенда; повторный evt не создаётся |
| EC-02 | Ученик закрывает браузер в середине урока (между Q1 и Q2) | Progress.current_message_id сохранён при каждом FSM-переходе; при следующем входе урок продолжается с сохранённой позиции |
| EC-03 | Ученик одновременно открыл PWA в двух вкладках и отвечает на один вопрос в обеих | Бэкенд — единственный источник истины; первый запрос фиксирует переход, второй получает 409 Conflict или идемпотентный ответ; состояние не задваивается |
| EC-04 | R1-push приходит, ученик уже в уроке (parallel flow) | R1 остаётся в pending; показывается после завершения текущего урока или при следующем входе |
| EC-05 | Ученик отвечает на R1 неверно | Фиксируется ошибка; review_queue: интервал откатывается на шаг назад (согласно Methodology §2.2); тема снова всплывёт раньше |
| EC-06 | Scheduler day_end запускается дважды за один день (баг infra) | Операция обновления Streak — идемпотентна: проверка `last_active_date == today` блокирует повторное применение |
| EC-07 | Ученик не выдал согласие на push | R1/R2 не отправляются через push; при следующем входе в PWA показывается баннер «Есть незавершённые повторения» |
| EC-08 | CSV для урока содержит отсутствующий return_X (message_id не существует) | keeper.py блокирует такой CSV до деплоя; если дошло до рантайма — движок логирует ошибку, показывает ученику theory с начала урока (safe fallback), не ломает FSM |
| EC-09 | Ученик пытается открыть урок через прямой URL, минуя FSM (daily_blocked) | Бэкенд проверяет Progress.status: если failed_today — возвращает 403 с объяснением «этот урок доступен завтра» |
| EC-10 | 3 дня подряд урок проваливается (passed_attempt_2 или failed_today) | На 3-й день система мягко предлагает «давай освежим основу из предыдущего урока» (Methodology §2.2.1); предыдущий урок добавляется в review_queue |
| EC-11 | Ученик прошёл все 27 уроков | `evt_all_lessons_done` → `course_complete`; показывается финальный экран с прогнозом балла ОГЭ |
| EC-12 | Ученик зарегистрировался, но никогда не запускал урок (ghost user) | Через 14 дней — напоминание от Фаундера (ReminderState); через 30 дней — финальный месседж; данные хранятся, не удаляются |
| EC-13 | lesson_id в CSV содержит точку (баг продюсера) | keeper.py отклоняет CSV до деплоя; PASS не выдаётся; в рантайм не попадает |
| EC-14 | Ученик открывает PWA без интернета | Service worker отдаёт кэшированную shell; если текущий урок закэширован — доступен офлайн; если нет — заглушка «нет соединения», Progress не теряется |
| EC-15 | correct_answer в CSV — строчная буква ('a' вместо 'A') | keeper.py блокирует; движок не получает невалидный CSV |

---

## 6. Режимы отказа

| id | Триггер отказа | Поведение системы | Обратимо? |
|----|---------------|-------------------|-----------|
| F-01 | Бэкенд FastAPI недоступен (сервер упал) | Service worker отдаёт кэш; при попытке FSM-перехода — показывает «нет соединения, попробуй позже»; Progress не мутирует | Да — автоперезапуск Docker Compose; без потери данных |
| F-02 | БД SQLite повреждена (диск / внезапный shutdown) | Бэкенд не стартует; фаундер получает уведомление (healthcheck); данные из последнего бэкапа | Да — восстановление из daily backup; возможна потеря данных за < 24 ч |
| F-03 | CSV урока не загрузился в движок (синтаксическая ошибка) | Движок пропускает повреждённый урок; при попытке старта урока ученик получает «урок временно недоступен»; другие уроки работают | Да — исправить CSV + перезапуск движка |
| F-04 | Push-сервис браузера недоступен (FCM/APNS down) | R1/R2 push не доставляются; при следующем входе в PWA — баннер «есть незавершённые повторения»; Streak не страдает | Да — автоматически, при восстановлении push-сервиса |
| F-05 | Scheduler (day_end / evening_time) не запустился | Streak не обновился, R2 не отправлен; при следующем запуске scheduler — проверяет пропущенные даты и применяет с флагом «запоздало» | Да — при следующем запуске scheduler; Streak может быть скорректирован за пропущенный день |
| F-06 | Бесконечный цикл: return_X указывает на самого себя | keeper.py ловит в статическом анализе (return_X != message_id текущей строки); если прорвалось — движок фиксирует max_retries=5 на одном message_id и переходит к следующему вопросу | Да — исправить CSV |
| F-07 | Двойная запись Progress (race condition при параллельных вкладках) | Бэкенд использует транзакцию + optimistic lock на Progress; проигравший запрос получает 409; фронтенд показывает «попробуй ещё раз» | Да — перезагрузка страницы |
| F-08 | review_queue переполнена (ученик не занимался 30+ дней) | При входе ученика — предлагается не вся очередь сразу, а порция (max 3 на сессию); остаток переносится; не блокирует новые уроки | Да — постепенно разгребается при ежедневных занятиях |
| F-09 | Ученик удаляет PWA с экрана (uninstall) | Данные на бэкенде сохранены; push_token инвалидирован; при повторном входе по ссылке — аккаунт восстанавливается (если есть сессионный токен или логин по имени/коду) | Да — данные не теряются |
| F-10 | Утечка progress другого ученика через API (auth bug) | Все эндпоинты бэкенда проверяют `user_id == authenticated_user_id` на уровне бэкенда (не доверяем фронтенду); матрица прав deny by default | Нет (не должно случиться); при обнаружении — аудит логов, уведомление фаундера, 152-ФЗ |

---

## 7. Раскладка каталогов

Зафиксирована для реализации данной задачи (ученик end-to-end). Изменение структуры требует обновления этой спеки.

```
oge-math-project/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # env vars, constants
│   ├── db/
│   │   ├── database.py          # SQLite connection, session factory
│   │   ├── models.py            # SQLAlchemy ORM: User, StudentProfile, Progress, Streak, ReviewQueue, ReminderState, DailySession, Links, Classes
│   │   └── migrations/          # Alembic migrations
│   ├── engine/
│   │   ├── csv_loader.py        # Чтение CSV уроков, валидация 19 колонок
│   │   ├── lesson_engine.py     # FSM движок урока: переходы, return_X, stage-логика
│   │   └── scheduler.py         # day_end job, evening push, R1 timer
│   ├── routers/
│   │   ├── auth.py              # Регистрация (name + grade), сессия
│   │   ├── student.py           # FSM-эндпоинты: start_lesson, answer, next_message
│   │   ├── progress.py          # GET progress, streak, review_queue (read-only для клиента)
│   │   └── push.py              # Регистрация push_token
│   ├── services/
│   │   ├── fsm_service.py       # Бизнес-логика переходов FSM (mastery learning rules)
│   │   ├── streak_service.py    # Streak update, freeze logic
│   │   ├── review_service.py    # review_queue: добавление, выборка, обновление интервалов
│   │   └── reminder_service.py  # Триггеры напоминаний
│   ├── auth/
│   │   └── deps.py              # Зависимости: get_current_user, check_student_owns_resource
│   └── tests/
│       ├── test_fsm.py          # FSM-переходы: happy path + edge cases
│       ├── test_mastery.py      # Логика 3 попыток, review_queue
│       ├── test_streak.py       # Streak update, freeze
│       ├── test_permissions.py  # Allow/deny по матрице прав
│       └── test_csv_loader.py   # Загрузка CSV, невалидные файлы
├── frontend/
│   ├── public/
│   │   ├── manifest.json        # PWA manifest
│   │   └── sw.js                # Service worker (офлайн + push)
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Onboarding.tsx   # Регистрация (имя + класс)
│   │   │   ├── DailyStart.tsx   # Главный экран дня
│   │   │   ├── MorningWarmup.tsx
│   │   │   ├── LessonPlayer.tsx # Рендер сообщений урока, кнопки ответов
│   │   │   └── CourseComplete.tsx
│   │   ├── components/
│   │   │   ├── MessageCard.tsx  # Рендер HTML-сообщения из CSV
│   │   │   ├── AnswerButtons.tsx
│   │   │   ├── StreakBadge.tsx
│   │   │   └── ProgressMap.tsx  # Карта знаний (блоки / уроки)
│   │   ├── hooks/
│   │   │   ├── useFSM.ts        # Взаимодействие с FSM-эндпоинтами бэкенда
│   │   │   ├── useLesson.ts
│   │   │   └── usePush.ts       # Запрос разрешения + регистрация push
│   │   ├── api/
│   │   │   └── client.ts        # HTTP-клиент (fetch wrapper)
│   │   └── i18n/
│   │       └── ru.ts            # Пользовательские тексты (не хардкодить в компонентах)
│   ├── vite.config.ts
│   └── tailwind.config.ts
├── content/                     # CSV уроков (уже есть, не трогать без keeper.py PASS)
│   ├── Контент_урок_1_1.csv
│   └── ...
├── tools/
│   ├── keeper.py                # Хранитель CSV (уже есть)
│   └── validator.py             # Валидатор FSM/матрицы прав (создаётся под эту спеку)
├── specs/
│   └── student_lesson_fsm_v1.md  # Этот файл
├── docker-compose.yml
├── .env.example                 # Шаблон переменных окружения (без секретов)
├── CLAUDE.md
├── Methodology_v2_1.md
├── Project_Brain_v3_2.md
└── .gitignore
```

---

## 8. Контракты между модулями (ключевые)

| Пара | Контракт |
|------|----------|
| csv_loader → lesson_engine | Загрузчик отдаёт `List[LessonMessage]`; если keeper.py-проверка провалилась — raises `InvalidCSVError`, урок не регистрируется |
| lesson_engine → fsm_service | FSM-сервис принимает `(user_id, event, payload)`, возвращает `(new_state, side_effects: List[SideEffect])`; side_effects исполняются транзакционно |
| fsm_service → review_service | При evt_lesson_complete или evt_main_correct_attempt2 — вызывает `review_service.enqueue(user_id, lesson_id, reason, due_date)` |
| scheduler → fsm_service | Scheduler вызывает fsm_service с событиями `evt_1h_elapsed`, `evt_evening_time`, `evt_day_end` через внутренний API (не через HTTP) |
| routers → auth/deps | Каждый эндпоинт использует зависимость `get_current_user`; `check_student_owns_resource(user_id, resource_user_id)` проверяет матрицу прав |

---

*Спека v1 закрывает роль «ученик» end-to-end для реализации MVP PWA. Роли родитель/учитель/репетитор, мессенджер-адаптеры — отдельные спеки после валидации ученической поверхности.*
