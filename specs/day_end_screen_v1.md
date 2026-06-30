# Аддендум: экран «День N завершён» — render-контракт и поведение

**Версия:** v1
**Дата:** 2026-06-30
**Автор:** Агент 3 (Архитектор системы)
**Тип документа:** ПОВЕДЕНЧЕСКО-ТРАНСПОРТНЫЙ аддендум поверх принятых `student_lesson_fsm_v4.md` и `student_lesson_api_v1.md`. НЕ вводит новых FSM-состояний/событий/переходов; не переоткрывает матрицу прав v4 §3 и failure-режимы v4 §6. Расширяет render-payload `view ∈ {day_done, day_blocked, course_complete}` (api v1 §4.1) новым опциональным блоком `day_summary`, задаёт таксономию экранов конца дня и условия деривации полей. Цель — заместить текущий пустой экран «Всё на сегодня закончено» (тупиковый исход без контекста) на содержательный экран «День N завершён» с прогрессом курса, агрегатом дня, превью завтрашнего урока и опциональным CTA на push.
**Источники (строгий приоритет):** Methodology v2.1 > Project Brain v3.2 > `specs/student_lesson_fsm_v4.md` (§2б, §3, §6) > `specs/student_lesson_api_v1.md` (§4 render, §6.1 `evt_session_end`-нормализация, §3.3 манифест) > `specs/A6_UI_дизайн-система_ученик_v1.md` (§2 инвентарь компонентов, §3.2 `daily_done`/`daily_blocked`/`course_complete`, F-1 счётчик дней) > CLAUDE.md (§1 спека-до-кода, §3 контракты данных, §6 152-ФЗ, §7 границы).
**Образец стиля/дисциплины:** `student_lesson_api_v1.md` (§0 о неприменимости FSM-YAML, §3.4 правки контракта на приёмку, §4.1 общий render-блок, §9 самопроверка).
**Потребители render-payload:** A6 `EmptyState` / `DeferCard` / `ProgressMap` / `DayCounterBadge` / `PendingNotice` (§3.2), A8 микрокопи «`day.end.*`», «`course.complete.*`» (зона А8, тексты ЗДЕСЬ не пишутся — задаются места и смысл).
**Область:** render-контракт и поведение экранов завершения дня в FSM v4 — `daily_done`, `daily_blocked` (как «день закрыт неудачей»), `course_complete` (как «день, на котором ученик закрыл курс»). НЕ переоткрывает прохождение урока, R1/R2, повторения, регистрацию. Pending-состояния (`repeat_1h_pending`/`repeat_evening_*`) — НЕ «конец дня», см. §2 (граница). Роли родитель/учитель/репетитор — вне охвата.
**Стыковка:** ВХОД — `student_lesson_api_v1.md` §4 (общий `render`-блок и view-дискриминаторы) + §6.1 (lazy-нормализация `evt_session_end` на E4 для `daily_done`/`review_queue_scheduled`). Этот аддендум **дополняет** §4.1 опциональным блоком `day_summary`, **не меняя** существующих обязательных полей, view-дискриминаторов и контракта секвенирования.
**Проверяют:** Агент 4 (Критик системы) + validator.py (validator неприменим к этому документу — см. §0, как api v1).

> **РЕВИЗИЯ R2 (2026-06-30, по второму проходу А4 «GO WITH REVISIONS — правки косметические, блокеров нет», 5 новых уточнений):** все 5 — точечные доводки без переоткрытия несущих контрактов: (Р2-К1) §3.3 — `block_completed_today` явно ОТСУТСТВУЕТ на view=`day_blocked` серверным инвариантом (симметрично инварианту для `course_complete`); (Р2-К2) §5.5 (EC-DE-05) — при включённом DE-5 повторные заходы в `day_done` тем же днём отдают тот же `next_lesson_preview` с `retry=false` (без перерасчёта); (Р2-К3) §4.8 — указан конкретный F-уровень для алерта `system_paused`: **новый F-12 «course manifest desync»**, по тяжести аналогичен F-06 (битый return_X в keeper), канал доставки — то же что для F-01..F-11 (по контракту infra); (Р2-К4) §7 DE-4 — явное разделение «обязательное предусловие для полноценного варианта vs degraded-режим без `title` допустим ВРЕМЕННО, не как продакшен-цель» (снимает интерпретацию «можно жить навсегда без `title`»); (Р2-К5) §3.2 + §4.7 — `course_completion.completed_at` явно помечен как **UTC-instant** (datetime, а не date), локализацию делает клиент — согласовано с инвариантом §4.1 «`today` — в локальном TZ ученика» (правило локального TZ касается date-полей, а не UTC-datetime-меток событий). Несущие контракты v4 §2б/§3б, api v1 §4.1 и все правки R1 — НЕ тронуты ни одной из 5 правок R2.

> **РЕВИЗИЯ R1 (2026-06-30, по ревью А4 «GO WITH REVISIONS», 5 блокеров + 10 замечаний):** внесены 5 правок по блокерам Б-1..Б-5 + 8 правок по замечаниям (З-1..З-10 — учтены все, кроме З-3 в части визуального макета: это зона A6/A8, помечено на встречную сверку). Несущая идея (расширение render `view ∈ {day_done, day_blocked, course_complete}` опциональным `day_summary` без правок FSM v4) НЕ тронута. (Б-1) `next_lesson_preview` на `day_done` сделан **опциональным**, добавлен флаг `not_pushy_tone=true` (требование тона), встречная правка A6 §3.2 поднята до уровня СУЩЕСТВЕННОЙ (симметрично api v1 R3 с `LessonProgress`-ремапом); добавлена развилка DE-5 «нужно ли превью завтрашнего урока в `day_done`». (Б-2) `freeze_applied_today` унифицировано на ОДИН источник — `ReminderState.freeze_applied_date == today` (датный «сегодня применена»); §3.2 и §4.5 синхронизированы; убрана фраза «определяется при реализации». (Б-3) `longest_streak_days` сделано **опциональным**, в дефолте НЕ отдаётся; добавлена развилка DE-6 «выводить ли «лучшую серию» поверх F-1». (Б-4) `LESSON_TITLES` переклассифицирована из «правки на приёмку» в **ОБЯЗАТЕЛЬНОЕ ПРЕДУСЛОВИЕ** реализации (без неё фича не запускается, §8.2); рекомендация TODO-заглушки «Урок {lesson_id}» в коде УДАЛЕНА; `next_lesson_preview.title` сделан опциональным внутри под-блока — fallback на серверной стороне «отсутствие title → клиент рендерит превью без заголовка (текст A8)», не клиентская заглушка. (Б-5) для EC-DE-04 (рассинхрон манифеста) введён диагностический флаг `day_summary.system_paused = true` с серверной деривацией; клиент рендерит честное «временно недоступно» вместо тихого `day_done` — устраняет бесконечную петлю «на сегодня всё». Замечания З-1 (TZ), З-2 (EC-17 → day_blocked render), З-4 (keeper-валидация консистентности LESSON_TITLES/COURSE_BLOCKS/COURSE_MANIFEST), З-5 (фронт-схема open/extensible), З-6 (`block_completed_today` НЕ отдаётся на `course_complete` — серверный инвариант), З-7 (возврат в `course_complete` через неделю), З-8 (ПД-классификация `oge_score_estimate`), З-9 (`lessons_completed_today` всегда по passed-уроку, независимо от view), З-10 (`seq` не зависит от `day_summary`) — учтены. З-3 (визуальное отделение CTA от блока итогов) — зона A6/A8, помечена на встречную сверку, серверный контракт push_cta не меняется. Несущие контракты v4 §2б/§3б, api v1 §4.1 (общий render-блок, view-дискриминаторы), `lesson_engine.py` — НЕ тронуты ни одной из правок R1.

---

## 0. Применимость и что НЕ меняется

Аддендум **поведенческо-транспортный**: расширяет `render`-payload и задаёт деривацию новых полей по существующим источникам. Соответственно:

- **FSM-составляющая не вводится и не меняется.** Состояния `daily_done`, `daily_blocked`, `course_complete`, переходы `lesson_select --evt_no_lesson_today--> daily_done`/`daily_blocked`, `lesson_select --evt_all_lessons_done--> course_complete`, `daily_done --evt_session_end--> registered`, `daily_blocked --evt_next_day--> registered`, `course_complete --evt_open_app--> registered`/`--evt_delete_account--> unregistered` — дословно как в v4 §2б. Новый FSM-YAML НЕ вводится; источник истины автомата — v4 §2б и `backend/engine/lesson_engine.py`.
- **Матрица прав v4 §3 не переписывается.** Все читаемые в `day_summary` ресурсы (`progress_own`, `streak_own`, `daily_session_own`, `review_queue_own`, `reminder_state_own`, `lesson_content`) — `read: true` для аутентифицированного владельца; ни одного нового `allow`-значения не вводится. YAML-блок прав НЕ дублируется (источник — v4 §3б).
- **Edge cases / failure modes v4 не переоткрываются.** Аддендум только биндит EC-11 (course_complete) и EC-22 (`daily_blocked + evt_open_app`) на конкретный render; добавляет fail-safe для аномалии «next_unpassed_lesson=None при не-passed=27» (§5.4) — это не новый failure-режим, а явное поведение в уже существующей вырожденной ситуации (рассинхрон манифеста §3.4-bis api v1).
- **`render`-блок api v1 §4.1 расширяется ОБРАТНО-СОВМЕСТИМО.** Все существующие поля (`fsm_state`, `view`, `message?`, `lesson_progress?`, `feedback?`, `seq`, `day?`, `next_actions`) — без изменений. Добавляется ОДНО новое опциональное поле верхнего уровня — `day_summary?`. Старый клиент, не знающий о `day_summary`, продолжает рендерить пустой `EmptyState` (текущее поведение); новый клиент рендерит экран «День N завершён». Дискриминатором богатого экрана служит наличие `day_summary` в payload, а не новый `view`.
- **Проверяемые А4 артефакты этого документа** — таблицы: таксономия view конца дня (§1), граница «конец дня vs pending» (§2), схема `day_summary` (§3), деривация полей по источникам (§4), edge cases (§5), границы push-CTA + ссылка на отдельную спеку (§6), открытые развилки фаундеру (§7). Самодостаточны для ревью без FSM-YAML/permissions-YAML.

> Если validator.py настроен искать YAML-блоки `role/states/...` или `permissions:` — в этом аддендуме их нет НАМЕРЕННО (та же дисциплина, что api v1 §0). validator по ЭТОМУ документу НЕПРИМЕНИМ — это ожидаемо.

### 0.1 Что аддендум РЕШАЕТ и что НЕ решает (мандат)

| # | Решено здесь | Раздел |
|---|---|---|
| 1. FSM меняется или только render? | Только render. Обоснование — §1. | §0, §1 |
| 2. Какие новые поля в render-объекте? | Единый опциональный блок `day_summary` с под-блоками. Состав и источники — §3, §4. | §3, §4 |
| 3. Edge cases (первый день, конец блока, конец курса, отсутствие следующего урока) | §5 (включая аномалию рассинхрона манифеста и идемпотентность повторного входа). | §5 |
| 4. CTA «Включить напоминание» — API E или отдельная спека? | Флаг `push_cta` в этой спеке; контракт подписки/токена — отдельная спека `push_subscription_api_v1` (роутер `push.py` в v4 §7). | §6 |

**Открытые развилки фаундера НЕ закрываются дизайном** (§7): DE-1 «особое поздравление при завершении блока», DE-2 «контент `course_complete` + источник `oge_score_estimate`», DE-3 «политика частоты push-CTA», DE-4 «тон `next_lesson_preview` в `daily_blocked`». Дефолты, помеченные fail-safe, предложены, но не закреплены — закрепляет фаундер.

---

## 1. Таксономия экранов конца дня и обоснование «без нового FSM-состояния»

### 1.1 Почему НЕТ нового FSM-состояния

Гипотеза «нужно новое состояние `day_end`» проверена и отвергнута. FSM v4 §2б уже различает ТРИ семантически разных терминала дня:

| FSM-состояние v4 | Семантика дня | Текущий `view` (api v1 §4.1) |
|------------------|---------------|------------------------------|
| `daily_done` | День закрыт штатно: новых уроков нет (либо все на сегодня пройдены, либо `review_queue_scheduled` нормализован в `registered`→`daily_start`→`lesson_select`→`no_lesson_today`) | `day_done` |
| `daily_blocked` | День закрыт неудачей: текущий урок провалён (`failed_today`), новые уроки сегодня заблокированы; единственный выход — `evt_next_day` (scheduler) | `day_blocked` |
| `course_complete` | Курс закрыт: все 27 уроков `passed`. НЕ терминал FSM — `evt_open_app → registered` (для настроек/удаления), `evt_delete_account → unregistered` (v4 §2б, §3 `user_account_own/delete`) | `course_complete` |

Эти три состояния НЕ взаимозаменимы: у них разные guards входа (`evt_no_lesson_today reason=...` / `evt_all_lessons_done`), разные выходы (`evt_session_end` / `evt_next_day` / `evt_open_app|evt_delete_account`), разные права-следствия (`course_complete` допускает `evt_delete_account` напрямую, остальные — через `registered`). Слияние их в одно «day_end»-состояние сломало бы guard-таблицу v4 §2б и матрицу прав (евент `evt_delete_account` из объединённого `day_end` потребовал бы новой ячейки матрицы или дублирующей `evt_session_end` нормализации). Это не пройдёт validator.py и переоткроет принятый артефакт без выигрыша.

**«Пустой экран “Всё на сегодня закончено”» — это не дефект FSM, а дефект render-payload.** Api v1 §4 определяет дискриминаторы `view: "day_done"`, `view: "day_blocked"`, `view: "course_complete"`, но НЕ задаёт содержательных полей под них (только общий блок `day?` со `streak_days`/`warmup_available`/`has_lesson_today`, который не несёт «сколько сделано», «что завтра», «куда в курсе»). Аддендум закрывает этот дефицит через расширение render-блока (§3), не трогая FSM.

### 1.2 Таксономия экранов конца дня (3 view, без новых)

| View (api v1) | FSM-источники | Тон (Methodology §1.3) | Обязательные блоки `day_summary` (§3) | Опциональные флаги |
|---------------|---------------|-------------------------|----------------------------------------|---------------------|
| `day_done` | `daily_done` (включая lazy-нормализованный из `review_queue_scheduled`, api v1 §6.1) | спокойное завершение, без подгоняющего «ещё урок»; «на сегодня всё» | `day_recap`, `course_progress`, `streak_today` | `next_lesson_preview?` (R1: опционально, DE-5; см. ниже), `push_cta?`, `block_completed_today?`, `system_paused?` (R1, диагностика) |
| `day_blocked` | `daily_blocked` (после `evt_lesson_fail_confirmed`) | без вины, без наказания; «сегодня не зашло — завтра попробуем» (A6 `DeferCard`) | `day_recap`, `course_progress`, `next_lesson_preview` (= тот же урок, что провалили; помечен `retry=true`), `streak_today` | `push_cta?` |
| `course_complete` | `course_complete` (`evt_all_lessons_done` после прохождения последнего из 27) | торжественное завершение курса; без приторности; ученик может перейти к настройкам/удалению аккаунта | `day_recap`, `course_progress` (`lessons_passed=27`), `course_completion` (новый под-блок: `completed_at`, `oge_score_estimate?`) | `push_cta?` (обычно false на этом view — см. §6.2) |

> **`next_lesson_preview` на `day_done` — ОПЦИОНАЛЬНОЕ, с требованием тона (R1-Б1).** В исходной v1 поле было обязательным, что вступало в прямой конфликт с A6 §3.2 (принятый артефакт, дословно описывает `daily_done` как «`EmptyState`: «на сегодня всё, отдыхай. **Спокойно, без догоняющих предложений «ещё урок»**»»). По ревью Критика поле:
>   - стало опциональным (`?`): сервер ВПРАВЕ не отдавать его на `day_done`, и в дефолте до закрытия DE-5 фаундером — **НЕ отдаёт** (fail-safe в сторону A6, симметрично api v1 R2-№5 `streak_days`);
>   - если фаундер по DE-5 решает «отдавать» — сервер включает поле, НО с требованием тона `not_pushy_tone=true` (см. §3.2 — серверный сигнал клиенту: рендер должен быть «завтра возьмём X», НЕ «вперёд к следующему уроку»); финальная формулировка — A8;
>   - встречная правка A6 §3.2 поднята до уровня СУЩЕСТВЕННОЙ (симметрично api v1 R3 с `LessonProgress`-ремапом), помечена в §8.1 (см. ниже).
> **`next_lesson_preview` отсутствует в `course_complete`** (курс пройден, следующего урока нет): под-блок просто не возвращается. Клиент рендерит `course_completion` вместо превью.
> **`day_blocked` несёт `next_lesson_preview` для ТОГО ЖЕ урока, который провалили** (он будет повторён завтра — v4 EC-10 / EC-22 / S-04): отличается от `day_done` (даже если там включено по DE-5) флагом `retry=true` и тоном (зона A8, не render). Это не дублирует FSM-`failed_today` → `not_started`-переход (его делает scheduler `evt_next_day`); render лишь показывает «завтра вернёмся к этому».

---

## 2. Граница «конец дня» vs «pending в течение дня» (что НЕ попадает сюда)

Аддендум покрывает ИСКЛЮЧИТЕЛЬНО три view §1.2. Pending-состояния — это **середина дня**, а не конец, и имеют собственные render'ы по api v1:

| FSM-состояние | view | Кто рендерит | Почему НЕ «конец дня» |
|---------------|------|--------------|------------------------|
| `repeat_1h_pending` | `repeat_pending` (api v1 §4.9) | A6 `PendingNotice` «R1 будет через N минут» | Урок дня пройден, но дневной цикл не закрыт: впереди R1, потом R2 — это ОБЯЗАТЕЛЬНЫЕ интервалы; пометить день закрытым сейчас = ввести ученика в заблуждение и сбить ретеншн §2.2 Methodology. |
| `repeat_1h_active` | `repeat_question` (api v1 §4.9) | A6 `QuestionBlock` (R1-вопрос) | Активный вопрос, не экран дня. |
| `repeat_evening_pending` | `repeat_pending` | A6 `PendingNotice` «вечернее повторение ждёт» | См. выше. |
| `repeat_evening_active` | `repeat_question` | A6 `QuestionBlock` (R2-вопрос) | Активный вопрос. |
| `review_queue_scheduled` | — (lazy-нормализуется в `day_done` на E4 — api v1 §6.1) | После нормализации — рендерится по правилам `day_done` этого аддендума | Сам по себе render НЕ показывается клиенту: ученик при заходе сразу получает `day_done` (R1-№1 api v1). |

**Транспортное правило:** `day_summary` присутствует в payload ТОЛЬКО при `view ∈ {day_done, day_blocked, course_complete}`. Во всех остальных view (`lesson_*`, `repeat_*`, `warmup`, `connection_stub`, `day_hub` в начале дня) `day_summary` ОТСУТСТВУЕТ — это инвариант (сервер не отдаёт, клиент не ожидает). Это снимает у кодера соблазн «вернуть превью завтра и на repeat_evening_pending — пусть ученик заранее знает».

> **Граничный случай — `view: "day_hub"` в начале дня после `evt_open_app`** (E5, api v1 §4.2): это НЕ конец дня (день только начался) → `day_summary` отсутствует; рендерится обычный хаб с `day.streak_days`/`day.warmup_available`/`day.has_lesson_today`. Различение `day_hub`-начало-дня vs `day_done`-конец-дня — по `view` (как и было в api v1), новых дискриминаторов не вводится.

---

## 3. Расширение render-payload: блок `day_summary`

### 3.1 Где добавляется

В общий `render`-блок api v1 §4.1 добавляется ОДНО новое поле верхнего уровня:

```json
{
  "fsm_state": "...",
  "view": "day_done" | "day_blocked" | "course_complete",
  "message": null,
  "lesson_progress": null,
  "feedback": null,
  "seq": <int>,
  "day": { ... },          // существующий блок (api v1 §4.1)
  "next_actions": [ ... ],
  "day_summary": { ... }   // НОВОЕ, опционально; присутствует ТОЛЬКО при view ∈ {day_done, day_blocked, course_complete}
}
```

### 3.2 Схема `day_summary` (JSON)

```json
{
  "day_number": 12,                        // integer, ≥1: номер активного учебного дня ученика (= число различных дат в DailySession.date, считая сегодняшнюю), §4.1. ВСЕ даты в day_summary деривируются в ЛОКАЛЬНОМ TZ ученика (R1-З1; см. §4.1)
  "day_recap": {
    "lessons_completed_today": 1,          // integer, 0..N: уроки, прошедшие сегодня (Progress.completed_at::date == today AND status=passed); §4.2. ВСЕГДА считается по passed-урокам, независимо от view (R1-З9 инвариант — например на view=day_blocked при ранее пройденном утреннем уроке значение = 1, не 0)
    "lessons_failed_today": 0,             // integer, 0|1: на view=day_blocked = 1, иначе 0 (FSM-инвариант: один failed_today/день); §4.2
    "reviews_completed_today": 3           // integer, 0..N: R1+R2+R3-warmup-ответы, отвеченные сегодня (= DailySession.reviews_completed); §4.2
  },
  "course_progress": {
    "lessons_passed_total": 12,            // integer, 0..27: число уроков с Progress.status=passed по всему манифесту (§3.3 api v1)
    "lessons_total": 27,                   // integer, =config.TOTAL_LESSONS; для контроля рассинхрона
    "current_block": {                     // ? присутствует, ЕСЛИ известно (зависит от §3.3-приёмки фаундера, см. §4.3)
      "block_id": "1",                     // string, идентификатор блока (см. DE-открытое в §7 и §4.3)
      "block_title": "Числа и вычисления", // string, человекочитаемое название блока (зона контента/keeper, см. §4.3)
      "lessons_in_block": 9,               // integer
      "lessons_passed_in_block": 5         // integer, 0..lessons_in_block
    }
  },
  "next_lesson_preview": {                 // ? ОПЦИОНАЛЬНО (R1-Б1):
                                           //   - на view=day_done: ОТСУТСТВУЕТ по дефолту (fail-safe в сторону A6 §3.2 «без догоняющих»); включается ТОЛЬКО при закрытии DE-5 фаундером
                                           //   - на view=day_blocked: ПРИСУТСТВУЕТ (тот же урок, retry=true)
                                           //   - на view=course_complete: ОТСУТСТВУЕТ (курс пройден)
    "lesson_id": "1_6",                    // string из единого пространства lesson_id (api v1 §3.4-bis)
    "title": "Сравнение дробей",           // ? ОПЦИОНАЛЬНО внутри под-блока (R1-Б4): отсутствует, если для lesson_id нет записи в LESSON_TITLES; клиент рендерит превью БЕЗ заголовка (текст A8, не клиентская заглушка в коде)
    "block_id": "1",                       // ? string; отсутствует, если COURSE_BLOCKS не задан (DE-блоки в §7)
    "retry": false,                        // boolean: true при view=day_blocked (тот же урок повторяется завтра); false при day_done
    "not_pushy_tone": true                 // boolean (R1-Б1): серверный сигнал клиенту «рендерить превью НЕ догоняющим тоном» («завтра возьмём X», НЕ «вперёд к следующему уроку»); всегда true для дисциплины тона (Methodology §1.3 через A6 §3.2); финальная формулировка — A8
  } | null,
  "streak_today": {
    "current_streak_days": 5,              // integer, ≥0: Streak.current_streak ПОСЛЕ применения сегодняшнего streak_update (§4.5)
    "freeze_applied_today": false,         // boolean (R1-Б2): true ⇔ ReminderState.freeze_applied_date == today (датный «сегодня применена»). НЕ путать с Streak.freeze_used_this_week (булев недельный лимит, остаётся true до понедельника). Единый источник истины — ReminderState.freeze_applied_date; §4.5
    "longest_streak_days": 12              // ? ОПЦИОНАЛЬНО (R1-Б3): по дефолту НЕ отдаётся; включается ТОЛЬКО при закрытии DE-6 фаундером (расширенная F-1 — «выводить ли «лучшую серию»»). Fail-safe в сторону Methodology §1.3 — без давящих сравнений с прошлой версией себя; симметрично api v1 R2-№5 «отсутствие = тихо»
  },
  "push_cta": {                            // ? присутствует ТОЛЬКО если сервер деривит show=true (§6.1); иначе блок ОТСУТСТВУЕТ
    "show": true,                          // boolean (всегда true в присутствующем блоке; отсутствие блока = «не предлагать»)
    "reason": "after_first_lesson"         // enum: "after_first_lesson" | "after_streak_at_risk" | "default_re_offer"; для микрокопии (A8, §6.1)
  },
  "block_completed_today": {               // ? присутствует ТОЛЬКО на view=day_done, ЕСЛИ сегодняшний последний пройденный урок закрыл блок (§5.3); DE-1 в §7. На view=course_complete НЕ ОТДАЁТСЯ (R1-З6 серверный инвариант), даже если технически условие выполнено — курс-finish доминирует над block-finish; этот инвариант обеспечивает СЕРВЕР, не клиент
    "block_id": "1",
    "block_title": "Числа и вычисления"
  } | null,
  "course_completion": {                   // ? присутствует ТОЛЬКО на view=course_complete; на day_done/day_blocked ОТСУТСТВУЕТ
    "completed_at": "2026-09-15T14:23:00Z",// ISO-8601 UTC-instant (R2-К5): datetime завершения курса (= timestamp последнего passed-урока); НЕ обновляется при повторных заходах в course_complete (см. EC-DE-09). Это event-timestamp (UTC), а не date-поле; локализацию в TZ ученика делает КЛИЕНТ при рендере (инвариант §4.1 «локальный TZ» касается date-полей вроде `today` для `lessons_completed_today`, не event-datetime-меток)
    "oge_score_estimate": null             // ? integer 3..5 ИЛИ null: прогноз балла ОГЭ (EC-11). DE-2 в §7 — методика расчёта НЕ закрыта; пока null. ВНИМАНИЕ (R1-З8, 152-ФЗ): любая методика, агрегирующая поведение несовершеннолетнего в персональный психометрический срез, требует ПД-классификации ДО включения в render — это юридическое решение, не код и не архитектура (см. §7 DE-2)
  },
  "system_paused": false                   // ? boolean (R1-Б5): диагностический флаг рассинхрона COURSE_MANIFEST ↔ Progress (EC-DE-04). По дефолту ОТСУТСТВУЕТ. Присутствует со значением true ТОЛЬКО когда сервер детектирует вырожденную ситуацию «next_unpassed_lesson()==None И lessons_passed_total < lessons_total» (см. §4.8). Клиент при system_paused=true рендерит честное «временно недоступно, мы уже разбираемся» (текст A8) ВМЕСТО тихого day_done-EmptyState. Устраняет бесконечную UX-петлю «на сегодня всё» при контрактном баге; параллельно сервер пишет лог-алерт фаундеру (F-уровень)
}
```

### 3.3 Типы и инварианты

| Поле | Тип | Инвариант |
|------|-----|-----------|
| `day_number` | integer ≥ 1 | строго монотонно растёт между разными датами активности; не сбрасывается при пропусках/передышках (`Streak.current_streak` ≠ `day_number`) |
| `day_recap.lessons_completed_today` | integer ≥ 0 | ВСЕГДА считается по passed-урокам (`count Progress WHERE status=passed AND completed_at::date=today`), независимо от view (R1-З9). На view=`day_blocked` значение = N (количество пройденных утром/днём passed-уроков ДО провала), НЕ обязательно 0; на view=`day_done` ≥ 0 (может быть 0 в чисто-review-день) |
| `day_recap.lessons_failed_today` | integer ∈ {0, 1} | FSM-инвариант: ≤1 провал в день (после `failed_today` → `daily_blocked` новые уроки заблокированы); при view=`day_blocked` = 1, иначе = 0 |
| `course_progress.lessons_passed_total` | integer 0..lessons_total | при view=`course_complete` обязательно = `lessons_total` |
| `course_progress.current_block` | object/`null` | присутствует только если §3.3 api v1 приёмка фаундера задаёт декомпозицию манифеста на блоки (см. §4.3); иначе ОТСУТСТВУЕТ (под-блок не выдумывать) |
| `next_lesson_preview` | object/`null`/ОТСУТСТВУЕТ | (R1-Б1) **по дефолту ОТСУТСТВУЕТ на `day_done` до закрытия DE-5** (fail-safe в сторону A6 §3.2); присутствует на `day_blocked` (объект с `retry=true`); `null`/ОТСУТСТВУЕТ на `course_complete` (курс пройден); ОТСУТСТВУЕТ при `system_paused=true` (рассинхрон манифеста, §5.4) |
| `next_lesson_preview.title` | string/ОТСУТСТВУЕТ | (R1-Б4) опционально внутри под-блока: отсутствует, если для `lesson_id` в `LESSON_TITLES` нет записи; клиент рендерит превью без заголовка (текст A8 — не клиентская заглушка в коде); НЕ возвращать TODO-строки «Урок {lesson_id}» из сервера |
| `next_lesson_preview.block_id` | string/ОТСУТСТВУЕТ | отсутствует, если COURSE_BLOCKS не задан (DE-блоки в §7) |
| `next_lesson_preview.retry` | boolean | `true` ⇔ view=`day_blocked`; `false` иначе (включая `day_done` при включённом DE-5) |
| `next_lesson_preview.not_pushy_tone` | boolean | (R1-Б1) ВСЕГДА `true` — серверный сигнал клиенту: рендерить превью НЕ догоняющим тоном («завтра возьмём X», НЕ «вперёд к следующему уроку»); финальная формулировка — A8 |
| `streak_today.current_streak_days` | integer ≥ 0 | значение ПОСЛЕ применения сегодняшнего streak_update; на повторном заходе того же дня — идемпотентно (v4 EC-06) |
| `streak_today.freeze_applied_today` | boolean | (R1-Б2) `true` ⇔ `ReminderState.freeze_applied_date == today` (датный «сегодня применена»). НЕ путать с `Streak.freeze_used_this_week` (булев недельный лимит, остаётся `true` всю неделю до scheduler-сброса в понедельник). Единый источник — `ReminderState.freeze_applied_date`; см. §4.5 |
| `streak_today.longest_streak_days` | integer/ОТСУТСТВУЕТ | (R1-Б3) **по дефолту ОТСУТСТВУЕТ** до закрытия DE-6 (расширенная F-1); при включении гарантирует `≥current_streak_days`; fail-safe в сторону Methodology §1.3 |
| `push_cta` | object/отсутствует | присутствие = предложить; отсутствие = не предлагать (§6.1); `show: false` НЕ ОТПРАВЛЯЕТСЯ (для краткости и однозначности) |
| `block_completed_today` | object/`null`/ОТСУТСТВУЕТ | (R1-З6, R2-К1) присутствует ТОЛЬКО при view=`day_done` И если сегодняшний последний passed-урок — последний урок блока (§5.3); на view=`course_complete` ОТСУТСТВУЕТ серверным инвариантом (course-finish доминирует); на view=`day_blocked` ОТСУТСТВУЕТ серверным инвариантом (на провальном дне нет «закрытия блока» — методически и фактически — у `day_blocked` нет нового passed-урока сегодняшним финалом) |
| `course_completion` | object/отсутствует | присутствует ТОЛЬКО при view=`course_complete`; на остальных view ОТСУТСТВУЕТ |
| `course_completion.completed_at` | ISO-8601 datetime | НЕ обновляется при повторных заходах в `course_complete` (см. EC-DE-09) — всегда timestamp фактического завершения курса |
| `course_completion.oge_score_estimate` | integer 3..5 / `null` | `null` пока DE-2 (§7) не закрыта фаундером и методика расчёта не задана; включение требует ПД-классификации по 152-ФЗ (R1-З8) |
| `system_paused` | boolean/ОТСУТСТВУЕТ | (R1-Б5) по дефолту ОТСУТСТВУЕТ; `true` ТОЛЬКО при детекте рассинхрона `next_unpassed_lesson()==None И lessons_passed_total < lessons_total` (§4.8). При `system_paused=true` сервер ОБЯЗАН НЕ отдавать `next_lesson_preview` и `block_completed_today` (избегаем ложного контекста) |

> **Дополнительный инвариант контракта (R1-З10):** `day_summary` НЕ влияет на `seq`-сверку api v1 §5.2. Поле `seq` остаётся производным от FSM-курсора урока (`(stage, индекс сообщения в стадии)`) — `day_summary` — это read-only-агрегат, не command-курсор; изменение значений `day_recap.lessons_completed_today` или `current_streak_days` между заходами `seq` НЕ инкрементирует. На view'ах конца дня (`day_done`/`day_blocked`/`course_complete`) `seq` транспортируется по правилам api v1, дедупликация перехода в эти view — обычная (E4/E9/E10 в зависимости от триггера).

> **Поля, которые `day_summary` НЕ дублирует из api v1 §4.1:** `day.streak_days` (есть в общем блоке `day`, но в `day_summary` он богаче — `streak_today.*`; на view'ах `day_done`/`day_blocked`/`course_complete` клиент берёт `streak_today`, на хабе начала дня — `day.streak_days`); `day.warmup_available`/`day.has_lesson_today` остаются в `day` и относятся к «завтра/сейчас», не к «итогу сегодня». Дублирования значений нет: общий блок `day` сохраняется, `day_summary` его дополняет.

---

## 4. Деривация полей `day_summary` (источники, без новых таблиц)

Все поля выводятся из УЖЕ существующих источников v4 §1 (ORM-модели в `backend/db/models.py`) и api v1 §3.3 (`COURSE_MANIFEST`). Новой ORM-таблицы/колонки `day_summary` НЕ требует — это derive-only payload.

### 4.1 `day_number`

Источник: `DailySession` (v4 §1). Деривация: `day_number = count(DISTINCT DailySession.date WHERE user_id = current_user AND date <= today)`. Альтернатива (более дешёвая): `(today - StudentProfile.course_started_at::date).days + 1`, НО она считает календарные дни, а не активные; методологически правильнее — активные (см. Methodology §1.1 «петля привычки» — счёт идёт по дням, когда ученик что-то делал, не по календарю).

**Решение:** считать по уникальным датам `DailySession`. Это согласуется с `Streak` (тоже по `DailySession`), не зависит от длительности пауз и переносит понятие «день N» с «день календаря» на «день учебной активности».

> **Граничный случай:** если ученик пропустил день и `DailySession` за тот день не создавалась, `day_number` за сегодня будет = (число активных дней до) + 1 — пропущенные дни в счёт не идут. Это согласовано с тоном Methodology §1.3 «без наказания за пропуски» (счёт ведём по сделанному, не по упущенному).

> **Часовой пояс (R1-З1, ЯВНО):** все «сегодня»/«date»/«today» в деривации `day_summary` (`day_number`, `day_recap.lessons_completed_today`/`reviews_completed_today`, `streak_today.freeze_applied_today`, `block_completed_today`) — это **ЛОКАЛЬНЫЙ TZ ученика**, не UTC. Источник TZ — `StudentProfile` (поле `tz` — ПОМЕЧЕНО на правку контракта данных: текущая v4 §1 модель `StudentProfile` поля `tz` НЕ имеет; добавить как nullable string IANA-id, например `Europe/Moscow`; до приёмки fail-safe — `tz = "Europe/Moscow"` как дефолт, согласован с целевой аудиторией РФ). Сценарий «ученик прошёл урок в 23:55 локально, R1 наступает в 01:05 локально следующего дня»: `Progress.completed_at` фиксируется UTC-instant'ом, в деривации `lessons_completed_today` для экрана вечером 27-го числа — фильтр `completed_at AT TIME ZONE student.tz :: date == today (student.tz)`; то же для R1-ответа, попадающего уже в 28-е число — `reviews_completed_today` экрана дня 28-го учитывает его как сегодняшний review дня 28. То есть граница смены дня согласована с TZ ученика, не с UTC и не с сервером. **Помечено как ПРАВКА КОНТРАКТА ДАННЫХ на приёмку** (v4 §1 +поле `StudentProfile.tz`) — без неё все деривации работают на дефолт `Europe/Moscow`.

### 4.2 `day_recap.*`

Источники: `Progress` + `DailySession`.

- `lessons_completed_today` = `count(Progress WHERE user_id = current_user AND status = passed AND completed_at::date = today)`.
- `lessons_failed_today` = `1 IF (view == "day_blocked") ELSE 0`. Эквивалентно `count(Progress WHERE status = failed_today AND user_id = current_user)`, который по FSM-инварианту ≤ 1.
- `reviews_completed_today` = `DailySession.reviews_completed` (агрегат уже считается scheduler/fsm_service по v4 §1 — поле существующее).

### 4.3 `course_progress.*`

Источники: `COURSE_MANIFEST` (api v1 §3.3) + `Progress` для текущего ученика.

- `lessons_passed_total` = `count(Progress WHERE user_id = current_user AND status = passed AND lesson_id IN COURSE_MANIFEST)`. Фильтр `IN COURSE_MANIFEST` нужен потому, что у ученика могут быть `Progress`-записи на старые `lesson_id`, не входящие в текущий курс (если контракт `lesson_id`-пространства менялся — §3.4-bis api v1); считать строго по манифесту, иначе число «13 из 27» может стать «15 из 27» некорректно.
- `lessons_total` = `config.TOTAL_LESSONS` (= 27). Явно дублирует серверную константу, чтобы клиент не зашивал «27» в код (если когда-то изменится — изменится автоматически).
- `current_block` — **зависит от продуктового решения о декомпозиции манифеста на блоки** (помечено как открытое в §7, DE-блоки):
  - Если в `config.py` (или отдельной структуре, см. ниже) задан маппинг `lesson_id → block_id`, сервер деривит `current_block.block_id` как `block_id` следующего непройденного урока (= `next_unpassed_lesson()` из api v1 §3.3, его `block_id`); `block_title` — из источника блоков; `lessons_in_block` / `lessons_passed_in_block` — счётчики по тому же маппингу.
  - Если маппинга нет (текущее состояние config.py — `FIRST_LESSON_ID`/`TOTAL_LESSONS`/`COURSE_MANIFEST`-на-приёмке, без блоков) — под-блок `current_block` ОТСУТСТВУЕТ в payload. Клиент рендерит только `lessons_passed_total/lessons_total` без блочной декомпозиции. Это не блокер — `course_progress` остаётся информативным («12 из 27»), просто без блоков.

> **ПРАВКА КОНТРАКТА ДАННЫХ НА ПРИЁМКУ (CLAUDE.md §3, DE-блоки в §7):** для блочной декомпозиции нужно расширение `config.py` или соседней структуры — например, `COURSE_BLOCKS: tuple[Block, ...]` где `Block` = `{block_id, block_title, lesson_ids: tuple[str, ...]}`. Это **добавление константы конфигурации**, как `COURSE_MANIFEST` (api v1 §3.4 вариант А). Помечено как правка контракта данных на приёмку фаундера и Brain-дельту; до приёмки — `current_block` ОТСУТСТВУЕТ, клиент рендерит без блочной разбивки. Конкретные `block_title` и группировка `lesson_id`-ов — методическая зона (продюсер контента/фаундер), не выдумывается архитектором.

### 4.4 `next_lesson_preview.*`

Источники: `COURSE_MANIFEST` + `Progress` + `LESSON_TITLES` (§4.4-bis) + `COURSE_BLOCKS` (§4.3).

**Деривация — поведение на 3 view (R1-Б1, R1-Б4, R1-Б5):**

- **view=`day_done`:** по дефолту блок `next_lesson_preview` **ОТСУТСТВУЕТ** в payload (fail-safe в сторону A6 §3.2 «без догоняющих»). Включается, ТОЛЬКО ЕСЛИ DE-5 закрыта фаундером как «да, отдавать»; в этом случае:
  - `lesson_id` = `next_unpassed_lesson(progress_by_lesson)` (api v1 §3.3); если вернулся `None` — это рассинхрон манифеста (§5.4), сервер выставляет `system_paused=true` и `next_lesson_preview` НЕ отдаёт.
  - `retry = false`, `not_pushy_tone = true`.
- **view=`day_blocked`:** ПРИСУТСТВУЕТ всегда (R1-Б1: на этом view превью методически уместно — «завтра вернёмся к ЭТОМУ уроку», это не «догоняющее предложение нового», а тёплое утешение):
  - `lesson_id` = `lesson_id` того урока, который в этом дне получил `status=failed_today` (он же будет «следующим» завтра после scheduler-перехода `failed_today → not_started`, v4 §2б `daily_blocked --evt_next_day--> registered`).
  - `retry = true`, `not_pushy_tone = true`.
- **view=`course_complete`:** блок ОТСУТСТВУЕТ (= JSON-`null` / отсутствие поля; курс пройден, следующего урока нет). Клиент в payload `course_complete` рендерит `course_completion`, не `next_lesson_preview`.

**Поля под-блока (когда блок присутствует):**

- `lesson_id` — см. выше.
- `title` — см. §4.4-bis (опционально внутри под-блока).
- `block_id` = блок next-урока (если декомпозиция задана, §4.3); иначе ОТСУТСТВУЕТ.
- `retry` — см. выше.
- `not_pushy_tone` — всегда `true`; см. §3.3 инвариант.

### 4.4-bis Источник `title` — `LESSON_TITLES` (R1-Б4: переклассифицировано в ОБЯЗАТЕЛЬНОЕ ПРЕДУСЛОВИЕ)

В CSV-контракте v4 §3 («19 колонок») заголовка урока НЕТ — есть `lesson_id`, `message_id`, `stage`, `text`. Архитектор предлагает **вариант (а): отдельная константа `LESSON_TITLES: Final[dict[str, str]]`** в `config.py` (или соседний JSON), карта `lesson_id → human-readable title`, рядом с `COURSE_MANIFEST` / `COURSE_BLOCKS`. НЕ меняет CSV-контракт (19 колонок) и keeper.py-валидатор контента — добавляет соседнюю мета-таблицу. Отвергнутый вариант (б) с 20-й колонкой в CSV см. в §7 (DE-4).

**(R1-Б4) Это ОБЯЗАТЕЛЬНОЕ ПРЕДУСЛОВИЕ для реализации фичи `next_lesson_preview` на любом view, не «опциональная правка».** Без приёмки `LESSON_TITLES` фаундером:
- `title` внутри `next_lesson_preview` ОТСУТСТВУЕТ; клиент рендерит превью без заголовка — текст A8 формата «завтра возьмём следующий урок» (БЕЗ имени урока). Это серверный fallback, не клиентская TODO-заглушка в коде.
- Сервер **НЕ возвращает** TODO-строки «Урок {lesson_id}» (нарушение CLAUDE.md §4 «пользовательские тексты не хардкодить»). Только отсутствие поля.
- Ответственность keeper.py при включении `LESSON_TITLES`: проверять, что для каждого `lesson_id` в `COURSE_MANIFEST` есть запись в `LESSON_TITLES` (валидация консистентности — см. §8.2).

### 4.5 `streak_today.*`

Источники: `Streak` (v4 §1) + `DailySession`.

- `current_streak_days` = `Streak.current_streak` ПОСЛЕ применения сегодняшнего `streak_update`. На view'ах `day_done`/`day_blocked`/`course_complete` это значение УЖЕ обновлено (либо через `daily_done → registered` цепочку с `evt_session_end → registered → evt_day_end → streak_update`, либо через `daily_blocked + evt_open_app` уже произошедший до этого момента scheduler-шаг). При повторном заходе того же дня — идемпотентно (v4 EC-06: `streak_update` проверяет `last_active_date == today`).

  > **Дисциплина деривации:** при формировании render'а на E4 сервер берёт ТЕКУЩЕЕ значение `Streak.current_streak` из БД — не пересчитывает streak здесь. Streak-update — зона `streak_service` (v4 §7 раскладка), вызываемая scheduler'ом (`evt_day_end`) либо lazy при `evt_open_app` с `missed_day_end=true` (api v1 §6 ремарка о двойном внутреннем переходе E5). Этот аддендум только ЧИТАЕТ streak, не пишет.

- `freeze_applied_today` = **`(ReminderState.freeze_applied_date == today)`** — единый источник истины (R1-Б2). Семантика — «передышка была применена ИМЕННО СЕГОДНЯ» (датный флаг сегодняшнего применения). НЕ путать с `Streak.freeze_used_this_week` — это **другое** поле в v4 §1 (булев недельный лимит): оно становится `true` при применении передышки и остаётся `true` всю неделю до scheduler-сброса в понедельник; использовать его для деривации `freeze_applied_today` НЕЛЬЗЯ — получим «`true` всю неделю» вместо «`true` ровно в день применения», что введёт ученика в заблуждение. **`today` — в локальном TZ ученика (§4.1).**
- `longest_streak_days` = `Streak.longest_streak`, **но отдаётся в payload ТОЛЬКО ЕСЛИ DE-6 закрыта фаундером как «выводить»** (R1-Б3). По дефолту — поле отсутствует в схеме (fail-safe в сторону Methodology §1.3, симметрично api v1 R2-№5 для `streak_days`). Сервер ВПРАВЕ читать `Streak.longest_streak` (право `streak_own/read=true` по v4 §3) — но право чтения ≠ обязанность отдавать в payload.

### 4.6 `block_completed_today` (опциональное)

Источник: те же что в `course_progress.current_block`.

Деривация: сервер проверяет, является ли `lesson_id` последнего сегодня пройденного урока (= max(Progress.completed_at)::date == today AND status=passed) ПОСЛЕДНИМ уроком своего блока по `COURSE_BLOCKS`. Если да — выставить `block_completed_today = {block_id, block_title}`. Если COURSE_BLOCKS не задан (DE-блоки не закрыта) — поле ОТСУТСТВУЕТ всегда.

> Зачем флаг отдельно от `course_progress`: это **событие «прямо сегодня»**, а не агрегат курса. UI может отметить его (микро-поздравление, см. DE-1) без анализа `lessons_passed_in_block == lessons_in_block` на стороне клиента.

### 4.7 `course_completion` (только view=`course_complete`)

- `completed_at` = `max(Progress.completed_at WHERE user_id = current_user AND status = passed)` — timestamp последнего пройденного урока (он же завершил курс). При повторных заходах в `course_complete` (EC-DE-09) значение НЕ обновляется (всегда указывает на момент фактического завершения, не на «сейчас»). **(R2-К5) Формат — UTC-instant (ISO-8601 с суффиксом `Z`)**, как любая event-datetime-метка из БД (`Progress.completed_at` хранится в UTC согласно общему контракту ORM-моделей). Локализацию в TZ ученика выполняет КЛИЕНТ при рендере (например, через `Intl.DateTimeFormat`). Это согласуется с §4.1 «локальный TZ» — то правило касается date-полей вроде `today` для счётчиков (`lessons_completed_today`, `freeze_applied_today`), а UTC-datetime событий сохраняется как есть.
- `oge_score_estimate` = `null` ДО решения DE-2 (§7). После решения — целое 3..5 по согласованной с фаундером методике (источник — методика, не код; данные — `Progress`/`DailySession`-агрегаты, доступны). **ВНИМАНИЕ (R1-З8, 152-ФЗ):** методика, агрегирующая поведение несовершеннолетнего в персональный психометрический срез (балл-прогноз), требует ПД-классификации ДО включения в render — это юридическое решение, не код и не архитектура. До закрытия — `null`; не подразумевать «как только методика будет — сразу включаем».

### 4.8 `system_paused` (диагностический флаг, R1-Б5)

**Условие включения:** `system_paused = true` ⇔ сервер при формировании render'а E4 детектирует:
```
(view == "day_done")  AND
(next_unpassed_lesson(progress_by_lesson) == None)  AND
(lessons_passed_total < lessons_total)
```
То есть «следующего непройденного урока нет, но и курс не завершён» — вырожденная аномалия рассинхрона `COURSE_MANIFEST` ↔ `Progress` ↔ контент (api v1 §3.4-bis открытый блокер). FSM в этой ситуации честно держит ученика в `daily_done` (потому что `evt_all_lessons_done` требует строго `passed=27`, а у нас < 27), и без диагностического флага клиент бы рендерил обычный «на сегодня всё» — что в EC-DE-04 превращается в бесконечную ежедневную петлю «на сегодня всё», пока админ не починит контракт. Флаг убирает эту петлю.

**Серверные действия при детекте:**
1. Выставить `day_summary.system_paused = true` в render.
2. **НЕ отдавать** `next_lesson_preview` и `block_completed_today` (избегаем ложного контекста).
3. Записать в лог `logger.error("course manifest desync: next=None, passed_total=%d/%d, user=%d", n, total, user_id)`.
4. Поднять алерт фаундеру по уровню **F-12 «course manifest desync»** (R2-К3, новый failure-режим в дополнение к v4 §6 F-01..F-11): рассинхрон контракта данных `COURSE_MANIFEST`/`Progress`/контент. По тяжести аналогичен F-06 (битый return_X в keeper) — продуктовый блокер на стороне контракта/контента, требует ручного вмешательства; обратимо (после фикса контракта). Канал доставки алерта — тот же, что для F-01..F-11 (по контракту infra/мониторинга; конкретика — sentry/email/метрика — задаётся в инфра-спеке, не здесь). До приёмки F-12 в v4 §6 — кодер использует ближайший существующий канал F-уровня (например, тот же что для F-06).
5. Остальные поля `day_summary` (`day_recap`, `course_progress`, `streak_today`) — отдаются как есть (они информативны и не вводят в заблуждение).

**Клиент при `system_paused=true`:** рендерит экран «временно недоступно, мы уже разбираемся» (текст A8) вместо `EmptyState`-«на сегодня всё». Это не FSM-переход, не новый view-дискриминатор — это инвариант рендера внутри уже существующего `view: "day_done"`.

**Дисциплина:** `system_paused` — это не failure-режим v4 §6, а **транспортное правило для уже существующей вырожденной ситуации** в принятом FSM. Аддендум не вводит новых FSM-состояний/событий, не меняет v4 §6 — только говорит, как сервер render'ит уже существующий `daily_done` при контрактной аномалии. Условие детекта (`next=None AND passed<total`) — детерминированное и cheap (O(1) проверка по уже посчитанным значениям §4.3).

---

## 5. Edge cases

### 5.1 EC-DE-01: первый день (день 1, прошёл первый урок)

Условие: ученик зарегистрировался сегодня, прошёл урок 1.1 (или несколько), цикл R1/R2 завершён (`day_done` или `day_blocked`).
Поведение:
- `day_number = 1`.
- `day_recap.lessons_completed_today` ∈ {0, 1, ...} (обычно 1 — после `evt_lesson_complete` и завершённого R2 наступает `review_queue_scheduled → registered → ... → daily_done`; если ученик закрыл уже несколько уроков подряд — больше, но FSM v4 даёт «один новый урок в день» через `daily_done` после первого, так что в норме 1).
- `course_progress.lessons_passed_total ∈ {0, 1}`; `lessons_total = 27`.
- `next_lesson_preview.lesson_id` = следующий по манифесту (обычно `1_2`).
- `streak_today.current_streak_days = 1`, `freeze_applied_today = false`.
- `push_cta` присутствует с `reason: "after_first_lesson"` (DE-3 в §7 — закрытие политики; дефолт-fail-safe: предлагать ровно один раз после первого пройденного урока, если `pwa_push_token = NULL`).

Особенностей нет; стандартный путь, проверяет, что нулевые / минимальные значения корректно вычисляются (например, `current_block.lessons_passed_in_block = 1`, не падает на делении/индексе).

### 5.2 EC-DE-02: конец блока

Условие: сегодняшний последний пройденный урок — последний в своём блоке (например, `1_9` — последний в блоке «Числа»).
Поведение (если `COURSE_BLOCKS` задан, §4.3 / DE-блоки):
- `block_completed_today = {block_id: "1", block_title: "Числа и вычисления"}`.
- `current_block` в `course_progress` УЖЕ показывает следующий блок (потому что `next_unpassed_lesson()` указывает на первый урок блока 2 → `current_block.block_id = "2"`).
- `next_lesson_preview.lesson_id = "2_1"` (первый урок блока 2), `block_id = "2"`.

Если `COURSE_BLOCKS` НЕ задан — `block_completed_today` всегда `null`/отсутствует; ученик не получает блочного поздравления. Дефолт безопасен (тихо), но менее тёплый — поэтому DE-1 (нужно ли отмечать конец блока) и DE-блоки (нужна ли декомпозиция вообще) отдельно вынесены в §7.

### 5.3 EC-DE-03: конец курса (course_complete достигнут сегодня)

Условие: пройден 27-й урок; FSM `lesson_final --evt_lesson_complete--> course_complete` (api v1 §1.3, branch `all_lessons_passed`).
Поведение:
- `view = "course_complete"`.
- `course_progress.lessons_passed_total = 27`, `lessons_total = 27`.
- `current_block` (если задан) — последний блок курса.
- `next_lesson_preview` ОТСУТСТВУЕТ (нет следующего урока).
- `course_completion = {completed_at: ..., oge_score_estimate: null|<int>}`.
- `block_completed_today` (если задан) — **НЕ отдаётся серверным инвариантом** (R1-З6), даже если последний пройденный урок технически закрыл блок: на view=`course_complete` курс-finish доминирует над block-finish, чтобы не было двойного поздравления. Серверный инвариант — не клиентское решение.
- `push_cta` обычно ОТСУТСТВУЕТ (курс пройден, ежедневные напоминания не нужны; если ученик уже подписан — push отключается через отдельный flow, не в render). Это DE-3 в §7 — поведение push_cta на course_complete; дефолт-fail-safe: не предлагать.

> **EC-11 (v4):** «`evt_all_lessons_done → course_complete`; показывается финальный экран с прогнозом балла ОГЭ». Прогноз = `oge_score_estimate`; методика — DE-2 в §7. До закрытия фаундером — `null`, клиент рендерит экран без прогноза (только факт завершения курса).

### 5.4 EC-DE-04: рассинхрон манифеста (`next_unpassed_lesson` = None, но `lessons_passed_total < lessons_total`) — диагностический режим `system_paused` (R1-Б5)

**Проблема в исходной v1:** Архитектор написал «корректно: ученик «застрял», но видит спокойный экран; админ получает алерт и чинит контракт». Это создавало скрытый продуктовый тупик: на следующий день при `evt_next_day → registered → daily_start → lesson_select → evt_no_lesson_today → daily_done` снова срабатывает тот же `next=None AND passed<total`, и ученик попадает в БЕСКОНЕЧНУЮ ежедневную UX-петлю «на сегодня всё» без какого-либо сигнала, что нужно ждать админа (алерт идёт фаундеру, не ученику). Это не пройдёт рубрику «В. Достижимость и тупики».

**Решение R1 (диагностический флаг + честный экран):** см. §4.8 — сервер при детекте этой аномалии выставляет `day_summary.system_paused = true` и НЕ отдаёт `next_lesson_preview` / `block_completed_today`. Клиент рендерит **«временно недоступно, мы уже разбираемся»** (текст A8 — без обвинения ученика, без «продукт сломался»; информирование, не молчание).

**Поведение:**
- FSM не меняется: ученик остаётся в `daily_done` (`evt_no_lesson_today reason=нет новых` — guard ловит этот случай корректно; FSM не ломается). Это НЕ переход в `course_complete` (`evt_all_lessons_done` требует `passed=lessons_total`, чего нет).
- Render: `view: "day_done"`, `day_summary.system_paused = true`, обычные `day_recap`/`course_progress`/`streak_today` отдаются как есть.
- Сервер: лог-алерт фаундеру (§4.8); до фикса контракта (api v1 §3.4-bis) — повторные заходы возвращают тот же диагностический экран. Этот цикл КОНЕЧЕН во времени: либо фаундер фиксит контракт (норма), либо ученик возвращается к нормальному `day_done` после фикса.
- Тон A8: «Сейчас следующий урок временно недоступен. Мы уже разбираемся — заходи через день» (плейсхолдер, финальная формулировка — A8).

> **Дисциплина:** EC-DE-04 — это **UX-страховка от контрактной аномалии**, не FSM-failure. Аномалия более вероятна, чем кажется, потому что api v1 §3.4-bis помечен как открытый КОНТЕНТНЫЙ блокер (текущий контент = 9 файлов вместо 27, `lesson_id="1"` на весь блок). До закрытия api v1 §3.4-bis вероятность срабатывания EC-DE-04 в проде/staging НЕ ничтожна. Поэтому защитить честным экраном — не «защита от паранойи», а закрытие предусмотренного сценария.

### 5.5 EC-DE-05: идемпотентность повторного входа в `day_done` тем же днём

Условие: ученик закрыл день (`day_done` рендерится), закрыл PWA, открыл снова через час — снова попал на `day_done`.
Поведение:
- `day_summary` рендерится повторно, значения идентичны (тот же `day_number`, тот же `day_recap`).
- `streak_today.current_streak_days` НЕ инкрементится повторно (v4 EC-06: идемпотентность `streak_update` через `last_active_date == today`).
- **При выключенной DE-5** (дефолт): `next_lesson_preview` отсутствует и при первом, и при повторном заходе — экран идентичен.
- **При включённой DE-5** (если фаундер закрыл «да отдавать»): `next_lesson_preview` отдаётся на обоих заходах с тем же `lesson_id` (next-непройденный по манифесту не меняется внутри дня — нет новых passed-записей между заходами в `day_done`), **`retry=false` остаётся как был** (не «retry», ученик не провалил — это всё ещё спокойное «завтра возьмём X»). `not_pushy_tone=true` на повторных заходах тоже не сбрасывается (R2-К2 уточнение). Никаких новых интерпретаций при повторе.
- `push_cta` поведение зависит от DE-3: безопасный дефолт — не предлагать повторно в тот же день, если уже предлагали и ученик не подписался (см. §6.1).

### 5.6 EC-DE-06: повторный вход в `daily_blocked` тем же днём (v4 EC-22)

Условие: ученик провалил урок сегодня (→ `daily_blocked`), закрыл PWA, открыл снова. FSM v4: `daily_blocked --evt_open_app--> daily_blocked` (самопетля; v4 §2б).
Поведение:
- `view = "day_blocked"` тот же.
- `day_summary` тот же (`lessons_failed_today = 1`, `next_lesson_preview.lesson_id` = провалённый урок, `retry = true`).
- Это согласуется с api v1 §6.1 «`daily_blocked` исключён из session_end-нормализуемых», R2-№3: ученик НЕ переводится в `registered` lazy — он остаётся в `daily_blocked` до scheduler `evt_next_day`.

### 5.7 EC-DE-07: ученик закрыл день, но завтра scheduler уже сменил день (открытие PWA после полуночи)

Условие: вчера `day_done`; ученик не закрывал приложение всю ночь; в 23:59 scheduler `evt_day_end` (если в `registered` — streak_update; если в `daily_done` — scheduler ничего не делает по v4 §2 «evt_day_end из daily_done — идемпотентно по `last_active_date`»). После полуночи `evt_next_day` ведёт `daily_done --evt_next_day--> registered`.
Поведение:
- Утром при `evt_open_app` (E5) ученик видит `view = "day_hub"` (НОВЫЙ день, `day_number` уже инкрементирован — будет учтён при первой `DailySession` сегодня; впрочем, до её создания значение может быть равно вчерашнему — это не блокер render'а).
- `day_summary` НЕ присутствует (на `day_hub` его нет — §2).
- Если у ученика остались due-повторения (review_queue) — обычный цикл разминки/уроков; конец нового дня снова рендерится через этот же контракт.

### 5.8 EC-DE-08: ученик в `lesson_failed` закрыл PWA до подтверждения, открыл вечером (R1-З2, биндинг v4 EC-17)

Условие: ученик дошёл до `lesson_failed` (исчерпаны попытки главного вопроса, `Progress.main_question_attempts == 2`), НЕ нажал «Понятно» и закрыл PWA. Через несколько часов открывает снова. По v4 EC-17: `fsm_service` при открытии PWA читает `StudentProfile.fsm_state` из БД; видит `lesson_failed` + `Progress.status=in_progress` + `attempts==2` → **автоматически генерирует `evt_lesson_fail_confirmed`** без участия пользователя → переход в `daily_blocked`.

Поведение этой спеки:
- На этот заход E4 возвращает `view = "day_blocked"` с полным `day_summary` (как обычный `day_blocked`).
- `day_recap.lessons_completed_today` считает passed-уроки сегодня корректно по инварианту R1-З9 (например, если утром ученик прошёл урок 1.5 как passed, потом стартовал 1.6 и провалил — значение = 1, не 0).
- `day_recap.lessons_failed_today = 1`.
- `next_lesson_preview = {lesson_id: <провалённый>, retry: true, not_pushy_tone: true}`.
- `streak_today.current_streak_days` — корректное значение по `Streak.current_streak` на момент рендера (если scheduler `evt_day_end` уже отработал в `registered` пути — учтён; если ещё нет — будет учтён ночью).
- Никаких особых полей render не нужно — EC-17 — это уже принятое поведение v4, аддендум только биндит его на render. Тон A8 на `day_blocked` (`DeferCard`) корректно покрывает кейс «провал был зафиксирован автоматически» без отдельного сценария — ученику показывается то же утешительное сообщение, что и при явном подтверждении.

### 5.9 EC-DE-09: возврат в `course_complete` через неделю после завершения курса (R1-З7)

Условие: ученик прошёл курс N дней назад (например, неделю), затем закрыл PWA. Открывает снова — заходит «посмотреть карту знаний» или из любопытства. По v4 §2б: `course_complete --evt_open_app--> registered` (для доступа к настройкам), затем при выборе чего-либо снова `daily_start → lesson_select → evt_all_lessons_done → course_complete`. То есть ученик снова попадает на `view: "course_complete"` с тем же `day_summary`.

Поведение:
- `view = "course_complete"`, `day_summary` рендерится повторно.
- `course_completion.completed_at` = **ТА ЖЕ датa**, что и при первом завершении (не «сейчас»; `max(Progress.completed_at)` по passed-урокам не меняется при возврате — никаких новых passed-записей не появляется после `course_complete`). Серверный инвариант §3.3.
- `day_number` = текущий (число активных дней суммарно за всё время, включая сегодняшний возврат); может быть «25», когда курс был пройден на «18-й день». Это согласовано: `day_number` — про активность ученика, `course_completion.completed_at` — про момент окончания курса.
- `day_recap.lessons_completed_today = 0`, `lessons_failed_today = 0` (за сегодня — никаких уроков, ученик уже всё прошёл; warmup тоже невозможен, потому что `review_queue` исчерпана — все интервальные повторения за неделю выгорели; впрочем, технически если в queue остались — `reviews_completed_today` отразит).
- `course_progress.lessons_passed_total = 27` (как и в день завершения).
- Тон A8 на повторном `course_complete`: формулировка должна работать для обоих случаев (первое завершение + возврат). Не «поздравляем сегодня!», а «курс пройден» — нейтрально-торжественно (плейсхолдер; финальная — A8).
- Удаление аккаунта прямо отсюда: `course_complete --evt_delete_account--> unregistered` (v4 §2б) — `day_summary` (включая `course_completion`) не мешает FSM-переходу; `next_actions` (api v1 §4.1 общий блок) включает `["delete_account"]` для этого view.

---

## 6. CTA «Включить напоминание» — границы решения

### 6.1 Что в этой спеке

Этот аддендум определяет:
- **Поле `push_cta` в render-payload `day_summary`** (§3.2): когда сервер деривит «предложить push» — это значение возвращается; когда не предлагать — поле ОТСУТСТВУЕТ.
- **Серверная политика деривации `push_cta` (дефолт fail-safe; уточняется DE-3 фаундером):**
  - Предлагать (`push_cta = {show: true, reason: "after_first_lesson"}`) при ПЕРВОМ заходе на `view=day_done`, если у ученика `User.pwa_push_token IS NULL` (ещё не подписан) И `ReminderState.last_notified_at IS NULL` (никогда не уведомляли) И сегодня пройден хотя бы один урок (`lessons_completed_today ≥ 1`). Это согласовано с A6 §5 «дефолт: предлагаем push после первого успешного урока, спокойно».
  - НЕ предлагать на view=`course_complete` (курс пройден, ежедневные напоминания не критичны; DE-3 для уточнения).
  - НЕ предлагать на view=`day_blocked` ПЕРВОГО дня (тон «извини, завтра попробуем» + CTA «подключи напоминания» = смешанный сигнал). На повторных `daily_blocked` после уже прошедшего отказа от push — можно предложить с `reason: "after_streak_at_risk"` (DE-3 для уточнения).
  - НЕ предлагать чаще, чем раз в N дней после отказа (`ReminderState.skip_days_count`, существующее поле v4 §1; параметр N — DE-3).
- **Микрокопия CTA — зона A8** (по `reason`-enum'у: `after_first_lesson` / `after_streak_at_risk` / `default_re_offer`); в этой спеке тексты не пишутся.

> **Дисциплина монтажа CTA на экране (R1-З3, встречное требование к A6/A8):** push-CTA визуально и тонально отделён от блока итогов дня (`day_recap` / `streak_today` / `block_completed_today`). Требования к UI:
>   - **Визуально:** CTA НЕ должен быть на одной панели/кнопке с поздравлением урока или серии («ты молодец → включи push» = манипулятивная связка успех→согласие); CTA — отдельный блок ниже, тон спокойный, кнопка вторичная (`secondary`, не `primary`).
>   - **Тон A8:** фразировка CTA НЕ использует достижение урока как обоснование push'а («ты прошёл первый урок, чтобы не потерять серию — включи напоминания» — анти-паттерн). Тон: «можно подключить напоминания, чтобы не упустить повторения — это спокойные ежедневные подсказки» (плейсхолдер; финал — A8). Если ученик отказывается принципиально — не давить, повторно предложить не раньше чем через N дней (DE-3).
>   - Это **встречное требование** к A6/A8 (не правит существующие компоненты A6, но добавляет требование к их использованию на трёх экранах). Помечено как зависимость на сверку с A6/A8 — серверный контракт `push_cta` (поле, `reason`, политика деривации) НЕ меняется.

### 6.2 Что НЕ в этой спеке (отдельная спека)

Контракт **самой push-подписки** — отдельный аддендум `push_subscription_api_v1` (роутер `push.py` в раскладке v4 §7, эндпоинт ещё не описан). Он покрывает:
- HTTP-эндпоинт `POST /api/push/subscribe` — приём `pwa_push_token` от service worker'а после `Notification.requestPermission()`.
- HTTP-эндпоинт `DELETE /api/push/unsubscribe` — отзыв подписки (`push_token_own/delete`, v4 §3).
- Связь с `ReminderState` (записать `last_notified_at`, сброс `skip_days_count` при подписке).
- Серверная сторона отправки push (FCM/APNS, EC-07 / F-04).
- 152-ФЗ: согласие на push не = согласие на ПД (ПД-согласие даётся отдельно при регистрации, reg_v2); push — отдельная opt-in операция.

> **Граница:** этот аддендум (day_end_screen_v1) — ТОЛЬКО render-флаг «предлагать или нет». Контракт самого предложения (HTTP, токены, разрешения браузера) — задача спеки `push_subscription_api_v1` (помечена в §8 как зависимость).

### 6.3 Что клиент делает при `push_cta.show = true`

Клиент рендерит CTA-кнопку «включить напоминания» (A6 — отдельный компонент или вариант существующего; A8 — текст по `reason`). При нажатии — вызывает Web Notification API (`Notification.requestPermission()`) → service worker регистрирует подписку → клиент шлёт токен на эндпоинт `POST /api/push/subscribe` (контракт — отдельная спека). При отказе ученика (кнопка «не сейчас» / отказ в браузер-диалоге) — сервер должен инкрементить `ReminderState.skip_days_count`, чтобы CTA не предлагался каждый день (см. дефолт §6.1). Способ передачи «отказа» — отдельный эндпоинт `POST /api/push/decline` (часть `push_subscription_api_v1`) ИЛИ имплицитно при следующем заходе (если `pwa_push_token` всё ещё NULL и прошло меньше N дней — не предлагать); конкретный механизм — в push-спеке.

---

## 7. Открытые развилки (решает фаундер; дизайном НЕ закрыты)

| # | Развилка | Что за ней | Дефолт fail-safe ДО решения |
|---|----------|-----------|------------------------------|
| **DE-1** | Особое поздравление при завершении блока — да/нет, насколько заметно? | Влияет на наличие `block_completed_today` в payload и на UI-рендер (микро-баннер vs модал vs тихий ярлык). Methodology §1.3 запрещает «давящие счётчики» — поздравления тоже могут быть «давящими» (праздновать конец блока 1 = «осталось 5 блоков!»). | Render отдаёт `block_completed_today` ЕСЛИ `COURSE_BLOCKS` задан и сегодня закрыт блок; клиент рендерит **тихий ярлык**, не модал. Заметность и формулировка — за фаундером (тон A8). |
| **DE-блоки** | Нужна ли декомпозиция курса на блоки в config (`COURSE_BLOCKS`)? Если да — какие блоки и какие `lesson_id` в каждом? | Это правка контракта данных (CLAUDE.md §3), как `COURSE_MANIFEST` (api v1 §3.4). Без неё `current_block` и `block_completed_today` всегда отсутствуют; ученик видит только «12 из 27». | Render: `current_block` и `block_completed_today` ОТСУТСТВУЮТ; `course_progress` без блочной разбивки. Это валидный режим — не блокер. Заведение `COURSE_BLOCKS` — отдельная задача (методика блоков уже есть в контенте, нужно поднять в код). |
| **DE-2** | Прогноз балла ОГЭ (`oge_score_estimate`) на `course_complete` — какая методика, какие данные, какой текст? | EC-11 v4 «финальный экран с прогнозом балла». Методика расчёта (среднее `passed_on_attempt`, число `failed_today`, темп прохождения, ...) — методическая, не код. Текст — A8. **ВНИМАНИЕ 152-ФЗ (R1-З8):** любая методика, агрегирующая поведение несовершеннолетнего в персональный психометрический срез (балл-прогноз), требует **ПД-классификации ДО включения** — это юридическое решение, не «когда методика готова — сразу включаем». | `oge_score_estimate = null` всегда; клиент рендерит `course_complete` без прогноза (только факт завершения). Поле НЕ убирается из схемы — добавится при закрытии DE-2 **И** прохождении ПД-классификации (юрист/фаундер). |
| **DE-3** | Политика частоты push-CTA: когда предлагать, сколько раз после отказа, на каких view? | Влияет на серверную деривацию `push_cta` (§6.1). Антипаттерн «спамить разрешением» — реальный риск; антипаттерн «не предлагать вообще» — тоже (ученик не получит R1/R2-push). | §6.1 дефолт-fail-safe: первый раз после первого урока на `day_done`; не предлагать на `course_complete`; на `day_blocked` — не предлагать на первом отказе, потом по необходимости. Параметр N (дней между предложениями) — конфиг, дефолт N=3 (значение помечено к подтверждению). |
| **DE-4 (R1: ОБЯЗАТЕЛЬНОЕ ПРЕДУСЛОВИЕ)** | Источник `LESSON_TITLES` (заголовки уроков) — отдельная константа в config.py / JSON-каталог / 20-я колонка CSV? | §4.4 вариант (а) vs (б). Влияет на keeper.py-валидацию и на CSV-контракт. Архитектор предложил (а) — отдельная константа, без правки 19-колоночного контракта; (б) требует пересмотра CSV-контракта v4 §3. **R1-Б4: переклассифицировано из «опциональной правки» в ОБЯЗАТЕЛЬНОЕ ПРЕДУСЛОВИЕ для реализации `next_lesson_preview`.** | Дефолт — (а): `LESSON_TITLES` отдельной структурой рядом с `COURSE_MANIFEST` в config.py. **БЕЗ приёмки** `LESSON_TITLES`: `next_lesson_preview.title` ОТСУТСТВУЕТ внутри под-блока, клиент рендерит превью без имени урока (текст A8, НЕ TODO-заглушка в коде); сервер НЕ возвращает строки «Урок {lesson_id}» (нарушение CLAUDE.md §4). **(R2-К4) Этот degraded-режим (без `title`) допустим ВРЕМЕННО — на staging или в первой итерации MVP под пилот, — но НЕ как продакшен-цель.** Полноценное превью с именем урока — обязательная цель к запуску с реальными учениками: после приёмки фаундера + контентного наполнения карты заголовков (зона keeper.py/контент-продюсера). Кодер не должен трактовать «degraded допустим» как «можно жить навсегда без `title`». |
| **DE-5 (R1-Б1, НОВАЯ)** | Нужно ли превью завтрашнего урока (`next_lesson_preview`) на view=`day_done`? | A6 §3.2 описывает `daily_done` как «`EmptyState`: «на сегодня всё, отдыхай. **Спокойно, без догоняющих предложений «ещё урок»**»». Превью завтрашнего урока — потенциально «догоняющее», даже с `not_pushy_tone`. Архитектор сделал поле опциональным; решение оставлено фаундеру: убрать совсем (тон A6 уважается) или включить с дисциплиной тона (тёплое «завтра возьмём X», не «вперёд к следующему уроку»). | По дефолту `next_lesson_preview` НЕ отдаётся на `day_done` (fail-safe в сторону A6 §3.2). При включении фаундером — серверный флаг `not_pushy_tone=true` обязывает A8 к тёплой формулировке. **Встречная правка A6 §3.2** при включении (см. §8.1 R1) — `EmptyState` для `daily_done` обогащается опциональным превью; формулировки `EmptyState` пересматриваются под расширенный сценарий. |
| **DE-6 (R1-Б3, НОВАЯ)** | Выводить ли `longest_streak_days` («лучшая серия») в payload поверх `current_streak_days`? Расширение F-1. | F-1 в A6 — открытая развилка про заметность даже текущего `current_streak`. `longest_streak` поверх неё — это дополнительный «давящий счётчик» («ты был на 12 днях, не подведи себя») по дисциплине Methodology §1.3. По дисциплине api v1 R2-№5 (fail-safe — отсутствие = не показывать) сервер не отдаёт пока фаундер явно не разрешил. | По дефолту `longest_streak_days` НЕ отдаётся в `streak_today` (fail-safe в сторону Methodology §1.3). Сервер ВПРАВЕ читать значение, НО не обязан отдавать. Включение — после явного решения фаундера: «нужна ли «лучшая серия» в продукте под Methodology §1.3 — да или нет». Это решение требует продуктового чутья + пилота на 5+ учениках, не архитектурное. |

> **Зачем перечислены дефолты:** чтобы кодер не остановился на каждом из этих пунктов, а имел безопасный путь по умолчанию. ВСЕ дефолты — fail-safe в сторону Methodology §1.3 (без давления, без шума, тихо). Открытые развилки — это улучшения, не блокеры — **за единственным исключением: DE-4 (LESSON_TITLES) после R1 — обязательное предусловие, без неё фича `next_lesson_preview` не имплементится в полном виде** (только без `title`-поля).

---

## 8. Стыковка с принятыми артефактами и зависимости

### 8.1 Стыковка

- **`student_lesson_fsm_v4` §2б:** FSM не меняется; используем существующие переходы `lesson_select --evt_no_lesson_today--> daily_done`/`daily_blocked`, `lesson_select --evt_all_lessons_done--> course_complete`, `daily_done --evt_session_end--> registered`, `daily_blocked --evt_next_day--> registered`, `course_complete --evt_open_app--> registered`/`--evt_delete_account--> unregistered`.
- **`student_lesson_fsm_v4` §3:** матрица прав не меняется; все читаемые ресурсы (`progress_own/read`, `streak_own/read`, `daily_session_own/read`, `review_queue_own/read`, `reminder_state_own/read`, `lesson_content/read`) — уже `allow: true` для аутентифицированного владельца.
- **`student_lesson_api_v1` §4.1:** общий `render`-блок расширяется опциональным полем `day_summary`; обратно-совместимо.
- **`student_lesson_api_v1` §6.1:** lazy-нормализация `evt_session_end` на E4 (`review_queue_scheduled → daily_done`) остаётся как есть; этот аддендум рендерит уже нормализованный `daily_done`.
- **`A6_UI_дизайн-система_ученик_v1` §3.2:** см. ниже — **СУЩЕСТВЕННАЯ встречная правка A6** (R1-Б1).

> **ВСТРЕЧНАЯ ПРАВКА A6 §3.2 НА ПРИЁМКУ (СУЩЕСТВЕННО, R1-Б1, по ревью Критика):** A6 §3.2 описывает `daily_done` как `EmptyState`: «на сегодня всё, отдыхай. **Спокойно, без догоняющих предложений «ещё урок»**». Этот аддендум при включении DE-5 фаундером (опционально) добавляет на `daily_done` блок `next_lesson_preview` — это **прямое расширение** принятого описания A6 (даже с серверным флагом `not_pushy_tone=true` поведение экрана меняется относительно «без догоняющих»). Нельзя оставлять два принятых артефакта противоречащими (CLAUDE.md §3 — рассинхрон принятых артефактов закрывается осознанно, а не молча). **Встречная правка A6 §3.2** (симметрично api v1 R3 для `LessonProgress`-ремапа):
>   - `EmptyState` для `daily_done` обогащается ОПЦИОНАЛЬНЫМ блоком превью завтрашнего урока (при включении DE-5);
>   - формулировка «спокойно, без догоняющих предложений «ещё урок»» **пересматривается**: правильнее — «без давящих/торопящих формулировок; превью завтра, если показывается, тёплое и без срочности» (финал формулировки — A8);
>   - **A6 в этом аддендуме НЕ редактируется** — только помечается встречная правка; финальное приведение A6 §3.2 к расширенному сценарию — на приёмке фаундера/в зоне A6.
> Дополнительная сверка с A6 §3.2: компоненты `EmptyState`/`DeferCard`/`course_complete`-экрана получают расширенный набор данных (`day_summary.*`) и должны быть обогащены при реализации UI. Это пометка на доработку компонентов, не правка A6 §1/§2 (токены и инвентарь не меняются).
> Дополнительная сверка с A6 F-1 (заметность счётчика дней): эта спека ДЕ-ФАКТО расширяет F-1 двумя сущностями — `current_streak_days` (обязательное в `streak_today` payload) и `longest_streak_days` (опциональное, по дефолту не отдаётся — DE-6). Сервер по-прежнему лишь отдаёт значения, UX-политику показа (заметность/скрытость) решает фаундер на стороне A6. Это согласовано с api v1 R2-№5.

### 8.2 Зависимости (другие спеки)

| Зависимость | Статус | Нужна для |
|-------------|--------|-----------|
| `student_lesson_api_v1` (E4 `GET /api/day`) | CURRENT | сервер рендерит `day_summary` в ответе E4 на view=`day_done`/`day_blocked`/`course_complete` |
| `COURSE_MANIFEST` в config.py | НА ПРИЁМКЕ ФАУНДЕРА (api v1 §3.4) | `course_progress.lessons_passed_total`, `next_lesson_preview.lesson_id` (через `next_unpassed_lesson`) |
| Единое пространство `lesson_id` | НА ПРИЁМКЕ ФАУНДЕРА (api v1 §3.4-bis) | согласование `Progress.lesson_id` ↔ `COURSE_MANIFEST` ↔ ключ контента |
| `LESSON_TITLES` (DE-4 в §7) | **R1: ОБЯЗАТЕЛЬНОЕ ПРЕДУСЛОВИЕ** на приёмке фаундера для полноценного `next_lesson_preview` с именем урока; без приёмки — `title` отсутствует, превью рендерится без имени (сервер НЕ возвращает TODO-строки) | `next_lesson_preview.title` |
| `COURSE_BLOCKS` (DE-блоки в §7) | НОВАЯ ОПЦИОНАЛЬНАЯ ПРАВКА НА ПРИЁМКЕ ФАУНДЕРА | `course_progress.current_block`, `block_completed_today`, `next_lesson_preview.block_id` |
| `StudentProfile.tz` (R1-З1, §4.1) | НОВАЯ ПРАВКА КОНТРАКТА ДАННЫХ (v4 §1 модель `StudentProfile`) на приёмку | корректная деривация «сегодня» в локальном TZ ученика; до приёмки — fail-safe дефолт `Europe/Moscow` |
| `push_subscription_api_v1` (§6.2) | НЕ НАПИСАНА — отдельная задача А3 | приём `pwa_push_token`, отзыв подписки, обработка отказа; этот аддендум только флагует «предложить» |

> **Контентный блокер (api v1 §3.4-bis):** доведение `Progress.lesson_id` / контент-ключей до единого пространства + содержание манифеста и блоков (27 `lesson_id`, заголовки, разбивка) — зона keeper.py / контент-продюсера + приёмка фаундера. Без этого `course_progress.lessons_passed_total` и `next_lesson_preview.lesson_id` могут возвращать корректные, но методически нерелевантные значения (например, при `lesson_id="1"` на весь блок 1 — `lessons_passed_total` не различает уроки внутри блока). Кодер этой спеки полагается на УЖЕ согласованное пространство (api v1 §3.4-bis); если на момент кодирования пространство не согласовано — поднять фаундеру, не импровизировать.

### 8.3 Требования к `keeper.py` (валидация консистентности констант — R1-З4)

При приёмке новых констант `LESSON_TITLES` / `COURSE_BLOCKS` фаундером, `keeper.py` (хранитель контента) должен расширить свои проверки следующими сверками (это требование к keeper, не реализация — конкретная имплементация — отдельная задача после приёмки):

1. **`COURSE_MANIFEST` ⊆ `LESSON_TITLES.keys()`** — для каждого `lesson_id` в манифесте курса должна быть запись в `LESSON_TITLES`; отсутствие — блокировать как ошибку контента (keeper аналогично сейчас блокирует CSV с битым return_X — EC-08 / F-06 v4). Это закрывает риск «сервер на каждом рендере молча отдаёт превью без `title` из-за пропущенной записи».
2. **`COURSE_MANIFEST` ⊆ `union(COURSE_BLOCKS[*].lesson_ids)`** (если `COURSE_BLOCKS` задан) — каждый `lesson_id` манифеста должен быть в одном из блоков; ни один не висит в воздухе. Это закрывает риск «`next_lesson_preview.block_id` отсутствует для конкретных уроков из-за пропуска в `COURSE_BLOCKS`».
3. **Пересечения блоков:** `COURSE_BLOCKS[i].lesson_ids ∩ COURSE_BLOCKS[j].lesson_ids == ∅` для `i ≠ j` — один `lesson_id` принадлежит ровно одному блоку; иначе деривация `current_block` неопределённа.
4. **Порядок:** `COURSE_BLOCKS` сохраняет порядок `COURSE_MANIFEST` — конкатенация `lesson_ids` по блокам в порядке блоков должна соответствовать `COURSE_MANIFEST`. Это закрывает риск рассинхрона позиции «следующего непройденного» внутри блока vs его глобальной позиции.

> Этот раздел — спецификация требований к keeper.py, не сама имплементация. Применяется только после приёмки фаундером `LESSON_TITLES` / `COURSE_BLOCKS`. До приёмки — keeper не трогается.

### 8.4 Фронт-схема: open/extensible (R1-З5)

Добавление `day_summary` к `render`-блоку (api v1 §4.1) безопасно ТОЛЬКО при условии, что фронт-схема парсера render-payload в проекте — **open/extensible** (игнорирует неизвестные поля, не падает на лишних). Это инвариант, унаследованный от api v1 (там опциональные поля верхнего уровня — `day?`, `feedback?`, `lesson_progress?` — добавлены аналогично; парсер уже должен быть open).

**Что нужно явно зафиксировать в коде (зона кодера фронта при реализации):**
- Используется схема, толерантная к неизвестным полям: для TypeScript — `interface` без `strict mode` на extra fields, либо Zod с `.passthrough()`, либо плоское чтение полей без полной валидации схемы.
- Сервер при отправке `day_summary` НЕ ломает существующих клиентов; старый клиент игнорирует поле и рендерит как раньше (текущий `EmptyState` «на сегодня всё»).
- Новый клиент при отсутствии `day_summary` (на не-конец-дня view'ах) — НЕ падает; парсер допускает отсутствие.

Это не блокер аддендума, но явная инструкция кодеру — иначе риск «парсер строгий → новый payload отвергается → ученик видит пустоту/ошибку» проявится на staging.

---

## 9. Самопроверка перед выдачей

- [x] FSM v4 §2б/§3б НЕ переоткрыты; новых состояний/событий/переходов/permissions нет. Новый FSM-YAML и permissions-YAML НЕ дублированы (намеренно, §0); validator.py по этому документу неприменим — ожидаемо, как api v1 §0. **R1: ни одна из 5 правок по блокерам и 8 правок по замечаниям не тронула несущие контракты v4 §2б/§3б и api v1 §4.1 (общий render-блок, view-дискриминаторы); `lesson_engine.py` также не тронут.**
- [x] **(1)** Подтверждено: FSM не меняется. Три существующих терминала дня (`daily_done`, `daily_blocked`, `course_complete`) согласованы с гипотезой фаундера. Обоснование, почему слияние в один `day_end` ломает v4 §2б и матрицу прав — §1.1.
- [x] **(2)** Состав `day_summary` определён (§3): `day_number`, `day_recap`, `course_progress`, `next_lesson_preview?` (R1-Б1: опц), `streak_today` (R1-Б3: `longest_streak_days?` опц), `push_cta?`, `block_completed_today?` (R1-З6: только на `day_done`), `course_completion?` (R1-З7: `completed_at` не обновляется при возврате), `system_paused?` (R1-Б5: новое поле для диагностики). Все поля выводятся из существующих источников v4 §1 + `COURSE_MANIFEST`; новой ORM-таблицы не требуется. **R1-З1:** все «сегодня» — в локальном TZ ученика (`StudentProfile.tz`, новая правка контракта v4 §1). **R1-Б2:** `freeze_applied_today` унифицировано на `ReminderState.freeze_applied_date == today` (НЕ `Streak.freeze_used_this_week`). **R1-З10:** `day_summary` НЕ влияет на `seq`-сверку api v1 §5.2.
- [x] **(3)** Edge cases покрыты (§5): EC-DE-01 (первый день), EC-DE-02 (конец блока), EC-DE-03 (конец курса), EC-DE-04 (рассинхрон манифеста — **R1-Б5: переписан с диагностическим режимом `system_paused`, устранена бесконечная UX-петля**), EC-DE-05/06 (идемпотентность повторного входа), EC-DE-07 (смена дня по полуночи), **R1-З2: EC-DE-08 (EC-17 lesson_failed → авто-`evt_lesson_fail_confirmed` → day_blocked render)**, **R1-З7: EC-DE-09 (возврат в course_complete через неделю — `completed_at` не обновляется, удаление аккаунта работает)**.
- [x] **(4)** Push CTA: в этой спеке только флаг `push_cta` (§6.1) + дефолтная политика деривации (DE-3 для уточнения); контракт самой подписки/токена — отдельная спека `push_subscription_api_v1` (§6.2). **R1-З3:** добавлено встречное требование к A6/A8 — CTA визуально и тонально отделён от блока итогов; A8 НЕ использует достижение урока как обоснование push'а.
- [x] **Обратная совместимость render-блока (api v1 §4.1):** `day_summary` — опциональное поле верхнего уровня; все существующие поля и view-дискриминаторы НЕ тронуты; старый клиент продолжает рендерить пустой `EmptyState`, новый рендерит «День N завершён». Никаких новых view-дискриминаторов (всё через `day_summary` под существующими `view: "day_done"`/`"day_blocked"`/`"course_complete"`). **R1-З5:** инвариант open/extensible фронт-схемы зафиксирован явно (§8.4).
- [x] **Граница «конец дня» vs «pending в течение дня» (§2):** `day_summary` присутствует ТОЛЬКО на трёх view; `repeat_*_pending`/`repeat_*_active`/`warmup`/`lesson_*`/`day_hub` — без `day_summary` (инвариант). Снимает риск, что кодер вернёт «превью завтра» на pending-экране в середине дня.
- [x] **Открытые развилки фаундеру вынесены (§7):** DE-1 (поздравление при конце блока), DE-блоки (декомпозиция курса на блоки), DE-2 (прогноз ОГЭ + R1-З8 пометка ПД-классификации), DE-3 (политика push-CTA), **DE-4 (R1-Б4: переклассифицирована в ОБЯЗАТЕЛЬНОЕ ПРЕДУСЛОВИЕ для непустого `title` превью; без неё title отсутствует, превью рендерится без имени — без TODO-строк в коде)**, **R1-Б1: DE-5 (новая — нужно ли превью на `day_done`)**, **R1-Б3: DE-6 (новая — выводить ли `longest_streak_days`)**. Все имеют fail-safe-дефолты (тихо, без шума, без давления — Methodology §1.3); ни один не блокирует MVP-реализацию частично (без `title` и без блоков — превью работает, но беднее).
- [x] **Правки контракта данных на приёмку фаундеру/Brain-дельту:** (1) `LESSON_TITLES` (DE-4 / §4.4-bis) — **R1-Б4: ОБЯЗАТЕЛЬНОЕ ПРЕДУСЛОВИЕ** для полноценного `title` превью (не «опциональная правка»); (2) `COURSE_BLOCKS` (DE-блоки / §4.3) — опциональна для `current_block`/`block_completed_today`; (3) **R1-З1: `StudentProfile.tz`** (новая) — правка модели v4 §1 для корректного локального TZ; до приёмки — fail-safe `Europe/Moscow`. Все три — добавления конфиг-констант / простой колонки модели, не изменения CSV-контракта v4 §3. Зависимости от открытых правок api v1 (§3.4 `COURSE_MANIFEST`, §3.4-bis единое пространство `lesson_id`) — пересекаются; их закрытие нужно ДО реализации этого аддендума.
- [x] **R1-З4: требования к keeper.py-валидации констант** (§8.3): `COURSE_MANIFEST ⊆ LESSON_TITLES.keys()`, `COURSE_MANIFEST ⊆ union(COURSE_BLOCKS[*].lesson_ids)`, непересекающиеся блоки, согласованный порядок. Применяется после приёмки констант; до приёмки — keeper не трогается.
- [x] **R1-Б1: СУЩЕСТВЕННАЯ встречная правка A6 §3.2 (§8.1):** при включении DE-5 фаундером `EmptyState` для `daily_done` обогащается опциональным превью; формулировка A6 «без догоняющих предложений «ещё урок»» пересматривается (зона A8). A6 в этом аддендуме НЕ редактируется — только встречная пометка (симметрично api v1 R3 для `LessonProgress`). Плюс сверка с A6 F-1 (current_streak обязательный, longest_streak опц — DE-6).
- [x] **152-ФЗ:** ничего нового по ПД не вводится для штатного режима — все читаемые поля уже `read: true` по матрице v4 §3. **R1-З8:** при закрытии DE-2 (`oge_score_estimate`) — обязательная ПД-классификация ДО включения (методика, агрегирующая поведение несовершеннолетнего в психометрический срез, может стать новым ПД-обязательством). Push-CTA не запрашивает разрешения сама по себе — это решает клиент через Web Notification API; согласие на push отдельно от согласия на ПД (см. §6.2).
- [x] **Тон и Методология §1.3:** дефолты всех опциональных полей (`push_cta` отсутствует ⇒ не предлагать; `block_completed_today` отсутствует или тихий ярлык; `oge_score_estimate = null` ⇒ без прогноза; **R1-Б1: `next_lesson_preview` на `day_done` отсутствует по дефолту до DE-5**; **R1-Б3: `longest_streak_days` отсутствует по дефолту до DE-6**) — fail-safe в сторону «без давления, без сгорания, без сравнения». Никаких счётчиков «осталось N дней!», «лучше других на X%», «не пропусти!» в render-контракте нет.
- [x] **R1-Б5: устранена бесконечная UX-петля «на сегодня всё»** при рассинхроне манифеста (EC-DE-04). Диагностический флаг `system_paused` + честный экран «временно недоступно» вместо тихого `EmptyState`. FSM v4 НЕ тронут — это транспортное правило рендера в уже существующей вырожденной ситуации.
- [x] **R2 (косметика, по второму проходу А4):** 5 точечных доводок без переоткрытия R1: (Р2-К1) `block_completed_today` явно ОТСУТСТВУЕТ на `day_blocked` серверным инвариантом (§3.3); (Р2-К2) EC-DE-05 уточнён для DE-5-включённого режима — повторные заходы в `day_done` отдают тот же `next_lesson_preview` с `retry=false` (§5.5); (Р2-К3) `system_paused`-алерт привязан к новому F-12 «course manifest desync» (по тяжести как F-06) в §4.8; (Р2-К4) `LESSON_TITLES` — degraded-режим без `title` допустим временно, НЕ как продакшен-цель (§7 DE-4); (Р2-К5) `course_completion.completed_at` явно помечен как UTC-instant с клиентской локализацией (§3.2 + §4.7), согласовано с инвариантом §4.1 «локальный TZ для date-полей». Несущие контракты R1 НЕ тронуты.

---

*Аддендум v1 (с ревизиями R1 + R2, 2026-06-30) — поведенческо-транспортное расширение render-payload `view ∈ {day_done, day_blocked, course_complete}` поверх принятых `student_lesson_fsm_v4` (validator PASS, А4 GO) и `student_lesson_api_v1` (R1+R2+R3, А4 GO). Заменяет пустой экран «Всё на сегодня закончено» на содержательный «День N завершён» с прогрессом курса, агрегатом дня, опциональным превью следующего урока, streak-фидбэком и опциональным push-CTA. РЕВИЗИЯ R1 закрывает 5 блокеров и 8 замечаний А4: (Б-1) `next_lesson_preview` на `day_done` сделан опциональным с дисциплиной тона + DE-5 + СУЩЕСТВЕННАЯ встречная правка A6 §3.2; (Б-2) `freeze_applied_today` унифицирован на `ReminderState.freeze_applied_date`; (Б-3) `longest_streak_days` опциональный, дефолт «не отдавать» + DE-6; (Б-4) `LESSON_TITLES` переклассифицирована в ОБЯЗАТЕЛЬНОЕ ПРЕДУСЛОВИЕ, TODO-заглушки в коде запрещены; (Б-5) диагностический флаг `system_paused` для рассинхрона манифеста — устраняет бесконечную UX-петлю; замечания З-1 (локальный TZ + `StudentProfile.tz` на приёмку), З-2 (EC-DE-08 для EC-17), З-4 (keeper-валидация консистентности констант), З-5 (фронт-схема open/extensible), З-6 (`block_completed_today` инвариант), З-7 (EC-DE-09 возврат в course_complete), З-8 (ПД-классификация oge_score_estimate), З-9 (`lessons_completed_today` всегда по passed), З-10 (`seq` независим). FSM v4 НЕ тронут (3 существующих терминала дня семантически достаточны). Матрица прав v4 §3 НЕ тронута (все читаемые поля уже allow). Контракт api v1 §4.1 расширен обратно-совместимо ОДНИМ опциональным полем `day_summary`. Контракт `push_subscription_api_v1` — отдельная задача А3 (роутер push.py, v4 §7). Правки контракта данных на приёмку: `LESSON_TITLES` (обязательна), `COURSE_BLOCKS` (опц), `StudentProfile.tz` (правка модели v4 §1) — добавления конфиг-констант/простой колонки, не CSV/ORM-миграции. Открытые продуктовые развилки: DE-1, DE-2 + ПД-классификация, DE-3, DE-5, DE-6, DE-блоки. Встречная правка A6 §3.2 — на приёмку. Проверяют: А4 (второй раунд) + validator.py (неприменим, §0).*
