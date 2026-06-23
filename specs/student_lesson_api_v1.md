# Аддендум: HTTP-API-контракт дневного потока и прохождения урока ученика (R1/R2 включены)

**Версия:** v1
**Дата:** 2026-06-22
**Автор:** Агент 3 (Архитектор системы)
**Тип документа:** ТРАНСПОРТНЫЙ аддендум поверх принятой FSM-спеки. НЕ переоткрывает FSM, матрицу прав, межролевые сценарии, edge cases, режимы отказа `student_lesson_fsm_v4`. Добавляет к ним HTTP-биндинг: набор эндпоинтов дневного потока/урока (с R1/R2), серверное судейство ответа (анти-подмена), схемы request/response (включая render-payload для A6/A8), контракт секвенирования внутри урока + манифеста курса между уроками, дедупликацию переходов и конвенцию статус-кодов, границу HTTP vs scheduler.
**Источники (строгий приоритет):** Methodology v2.1 > Project Brain v3.2 > `specs/student_lesson_fsm_v4.md` > CLAUDE.md (§1 спека-до-кода, §3 контракты данных, §6 безопасность/152-ФЗ, §7 границы).
**Образец стиля/дисциплины:** `specs/student_registration_api_v1.md` (§0 о неприменимости FSM-YAML, конвенция статус-кодов, идемпотентность, ссылочная карта вместо дублирования FSM).
**Потребители render-payload:** A6 §3.2 (`LessonProgress` 1–6, `MessageCard`/`QuestionBlock`, `AnswerFeedback`, `ConnectionStub`), A8 §2 (микрокопи фидбэка/стадий). Они читают `render`-блок §4, но не задают его — контракт здесь.
**Область:** HTTP-транспорт под FSM v4 §2 от `registered --evt_open_app--> daily_start` до прохождения урока (`lesson_hook … lesson_final/lesson_failed`), повторений R1/R2 (`repeat_1h_*`, `repeat_evening_*`, `review_queue_scheduled`) и тупиковых исходов дня (`daily_done`, `daily_blocked`, `course_complete`). Регистрация/онбординг — в `student_registration_api_v1.md` (стыкуется через `next: daily_start`). Роли родитель/учитель/репетитор, мессенджер-поверхности — вне охвата.
**Стыковка:** ВХОД — `student_registration_api_v1.md` E3 отдаёт `fsm_state: registered` + `next: daily_start` + непустой `current_lesson_id`. Этот аддендум начинается с `evt_open_app`. Все события `evt_*`, guards, side-effects, deny-by-default матрицы прав v4 — НЕ ломаются.
**Проверяют:** Агент 4 (Критик системы) + validator.py.

> **РЕВИЗИЯ R1 (2026-06-22, по ревью А4 «GO WITH REVISIONS», блокеров нет):** внесены 7 правок без переоткрытия несущих контрактов v4 §2б/§3б и движка. (№1) `evt_session_end` классифицирован в §6/§8 — устранён формальный тупик HTTP-возврата `review_queue_scheduled`/`daily_done → registered`. (№2) R3-разминка (`morning_warmup`/стадия `repeat_morning`) доопределена в §2.3/§2.5: warmup-answer не диспатчит FSM-событие, серверный счётчик «3 вопроса» деривит `evt_warmup_complete`. (№3) Зафиксирован порядок «гард до инкремента»: `main_question_attempts` инкрементится САЙД-ЭФФЕКТОМ движка, в `ctx` подаётся значение ДО инкремента; убраны вводящие в заблуждение «(станет 2)/(станет 1)». (№4) Доопределено sequence-эхо для E9 `advance` (§5.2): сверка по позиционному курсору `(stage, индекс сообщения в стадии)`, не по `message_id`. (№5) Карта §8 дополнена `evt_session_end`; подтверждено различение `evt_open_pwa`/`evt_open_app`. (№6) `view` для «wrong с возвратом» сведён к единому контракту (§4.5/§4.9). (№7) `streak_days` помечен как ОПЦИОНАЛЬНЫЙ тихий показ (F-1). Несущие контракты v4 (события/гарды/side-effects/матрица прав) и `lesson_engine.py` — НЕ тронуты.

> **РЕВИЗИЯ R2 (2026-06-22, второй проход А4 «GO WITH REVISIONS», блокеров нет):** 5 правок — №1 единое пространство `lesson_id` (контракт данных на приёмку, §3.4); №2 skip-внутри-разминки не помечает R3 done (§2.5); №3 `daily_blocked` вне session_end-нормализации (§6.1); №4 `seq++` на каждом command включая return_X (§5.2); №5 дефолт `streak` — тихий показ (§4.1). Транспортный характер сохранён: новых FSM-YAML нет; несущие контракты v4 §2б/§3б и `lesson_engine.py` НЕ тронуты ни одной из 5 правок.

> **К-1 (2026-06-22, третий проход А4 «GO», косметика):** в строке E6 (§1.2) добавлена перекрёст-ссылка — «пропустить» разминку, нажатое уже ВНУТРИ `morning_warmup`, деривит `evt_warmup_complete`, а НЕ `evt_warmup_skip` (в движке нет перехода `MORNING_WARMUP --WARMUP_SKIP-->`, §2.5 п.5). Снимает риск, что кодер, прочитав только §1.2, пошлёт `evt_warmup_skip` из `morning_warmup` → `UnknownTransitionError`. К-2 (абзац-определение `view`) по решению фаундера НЕ вносится — сводная таблица §4.9 достаточна. Вердикт А4 — чистый GO.

---

## 0. Замечание о применимости FSM-YAML и форме проверки

Этот аддендум **чисто транспортный**: он не вводит новых состояний, событий, переходов или ролей сверх `student_lesson_fsm_v4` §2б. FSM ученика уже принят и прошёл validator.py (MEMORY: validator PASS, А4 GO). **Новый FSM-YAML здесь НЕ вводится** — он был бы дубликатом принятого и создавал бы риск рассинхрона двух источников по одному автомату (та же дисциплина, что reg api §0).

Соответственно:
- **FSM-составляющая** даётся только как ССЫЛОЧНАЯ карта «HTTP-действие ↔ событие(я) v4» (§1.3, §9), без переопределения states/events/transitions. Источник истины автомата — v4 §2б и `backend/engine/lesson_engine.py`.
- **Матрица прав** v4 §3 НЕ переписывается. §2 этого аддендума лишь УТОЧНЯЕТ место исполнения судейства ответа (`progress_own/write` «только через FSM-эндпоинты» — v4 §3) и не меняет ни одного `allow`-значения. YAML-блок прав НЕ дублируется (источник — v4 §3б).
- **Edge cases / failure modes** v4 §5/§6 НЕ переоткрываются. §6 даёт лишь HTTP-биндинг для EC-01/EC-02/EC-03/EC-09/F-07/F-10 (статус-коды, дедуп).
- **Проверяемые А4 артефакты** этого документа — таблицы: эндпоинтов (§1), маппинга действие→событие (§1.3, §9), серверного судейства (§2), схем/render-payload (§4), секвенирования+манифеста (§3), конкурентности+статус-кодов (§5), границы scheduler (§7). Самодостаточны для ревью без FSM-YAML.

> Если validator.py настроен искать YAML-блоки `role/states/...` или `permissions:` — в этом аддендуме их нет НАМЕРЕННО. Канонические YAML — в v4 §2б/§3б, единственный источник для прогона. validator.py по ЭТОМУ документу останется НЕПРИМЕНИМ — это ожидаемо и не дефект аддендума.

### 0.1 Что этот аддендум РЕШАЕТ и что НЕ решает (мандат фаундера)

| # пункта мандата | Решено здесь | Раздел |
|---|---|---|
| 1. Набор endpoints + маппинг «HTTP→evt FSM», единая кнопка «Дальше» → разные evt по stage | да | §1, §1.3, §9 |
| 2. Серверное судейство ответа (анти-подмена): клиент шлёт букву, сервер деривит correct/wrong/feedback/return/evt | да | §2 |
| 3. Схемы request/response + render-payload (resume/correct/wrong/fail/final) | да | §4 |
| 4. Контракт секвенирования внутри урока + манифест курса (27 lesson_id) | да — **манифест включён в этот аддендум** (минимальный интерфейс) + помечена правка контракта данных на приёмку | §3 |
| 5. Конкурентность (EC-01/EC-03/F-07) + статус-коды; дедуп без version-колонки у Progress | да — **sequence-эхо без новой колонки** (основной механизм) + опциональная version-колонка помечена как правка модели на приёмку | §5 |
| 6. Граница HTTP vs scheduler (evt_1h_elapsed/evt_evening_time/evt_day_end/evt_next_day/evt_session_end) | да — все системные/временные события классифицированы (включая `evt_session_end`, R1-№1) | §6 |

**Продуктовых развилок аддендум не создаёт.** Все трактовки v4 (D-2..D-5) уже приняты v4; здесь не переоткрываются. Открытые архитектурные правки на приёмку (контракт данных) — §3.4 (источник манифеста + **единое пространство `lesson_id`, R2-№1**) и §5.4 (version-колонка Progress, опциональна). Они НЕ продуктовые — это правки §3-контрактов данных (CLAUDE.md §3), помечены явно на Brain-дельту.

---

## 1. Эндпоинты дневного потока и урока

Базовый префикс: `/api`. Все ответы — `application/json` (кроме 204). Аутентификация — httpOnly-cookie `oge_session` (`backend/auth/deps.py`, `current_user_or_none`); анонимный доступ к любому из E4–E10 → 401/403 (§5). Контекст текущего состояния FSM сервер ВСЕГДА берёт из `StudentProfile.fsm_state` (v4 §8 «не доверяет клиентскому параметру»), а не из тела/URL — клиент не выбирает состояние.

### 1.1 Принцип одного «FSM-action»-эндпоинта + чтение состояния

Транспорт дневного потока строится на **двух осях**:
- **read-ось** (`GET`) — «что рендерить сейчас»: render-payload текущего состояния/сообщения (E4 day-view, E7 lesson-view).
- **command-ось** (`POST`) — «продвинуть FSM»: клиент шлёт *намерение* (advance / answer / cancel / confirm / acknowledge), сервер по текущему `fsm_state` + stage деривит конкретное `evt_*`, диспатчит через `lesson_engine.dispatch`, исполняет side-effects транзакционно (v4 §8 контракт `routers → fsm_service`), возвращает новый render-payload.

**Клиент НЕ называет событие FSM в запросе.** Он называет тип действия (`advance`/`answer`/...). Сервер — единственный, кто превращает действие+stage в `evt_*`. Это закрывает «фронтенд судит сам себя» (матрица прав v4 §3 `progress_own/write` = «только через FSM-эндпоинты; прямой PUT/PATCH запрещён»).

### 1.2 Таблица эндпоинтов

| # | Метод | Путь | Назначение | Аутентификация | FSM-привязка (источник — v4 §2б) |
|---|-------|------|-----------|----------------|----------------------------------|
| E4 | `GET` | `/api/day` | Render-payload текущего состояния ДНЯ (хаб): что показать на `daily_start`/`morning_warmup`/`lesson_select`/`daily_done`/`daily_blocked`/`course_complete`/`repeat_*_pending`/`review_queue_scheduled`. Читает `fsm_state`, `streak`, наличие due-повторений, наличие следующего урока. На входе из `review_queue_scheduled`/`daily_done` деривит `evt_session_end → registered` (R1-№1, §6). НЕ мутирует FSM напрямую (см. §6 о session_end). | cookie | состояние читается; `evt_session_end` деривится сервером (§6) |
| E5 | `POST` | `/api/day/open` | Вход в день: `registered --evt_open_app--> daily_start` (или `--> streak_update` при `missed_day_end`, §7). Идемпотентен в пределах дня. | cookie | `evt_open_app` |
| E6 | `POST` | `/api/day/warmup` | Действия утренней разминки (R3, 3 interleaved-вопроса, A6 `WarmupRunner`): `start` (`evt_warmup_available`), `skip` (`evt_warmup_skip` — ТОЛЬКО из `daily_start`; «пропустить», нажатое уже ВНУТРИ `morning_warmup`, деривит `evt_warmup_complete`, НЕ `evt_warmup_skip`, т.к. в движке нет перехода `MORNING_WARMUP --WARMUP_SKIP-->`, единственный выход — `evt_warmup_complete` — §2.5 п.5, К-1), `answer` (ответ на R3-вопрос разминки, стадия `repeat_morning`, судится сервером как §2 — только feedback-render, FSM-событие НЕ диспатчится, §2.5). `complete` НЕ присылается клиентом — `evt_warmup_complete` деривит СЕРВЕР по исчерпании серверного счётчика 3 вопросов (§2.5). | cookie | `evt_warmup_available` / `evt_warmup_skip` (skip ТОЛЬКО из `daily_start`; нажатие «пропустить» ВНУТРИ `morning_warmup` → `evt_warmup_complete`, не `evt_warmup_skip` — К-1, §2.5 п.5); `answer` → judge-only (нет evt); `evt_warmup_complete` — сервер деривит (§2.5) |
| E7 | `GET` | `/api/lesson/current` | Render-payload ТЕКУЩЕГО сообщения урока (resume-точка, EC-02): stage, HTML text, опции A–D, `LessonProgress` (этап 1–6), цель возврата при незавершённом возврате. Не мутирует FSM. | cookie | состояние/`current_message_id` читается |
| E8 | `POST` | `/api/lesson/start` | `lesson_select --evt_start_lesson--> lesson_hook` для следующего незавершённого урока (или тупик: `evt_no_lesson_today` / `evt_all_lessons_done` — сервер деривит по манифесту §3). Создаёт/находит Progress (`progress_own/create`, v4 §3 «при старте урока через FSM»). | cookie | `evt_start_lesson` / `evt_no_lesson_today` / `evt_all_lessons_done` |
| E9 | `POST` | `/api/lesson/advance` | **Единая кнопка «Дальше»** на нон-вопросных стадиях: сервер по текущему stage деривит `evt_hook_read` / `evt_theory_read` / `evt_example_read` / `evt_theory_reviewed` / `evt_lesson_complete` / `evt_lesson_fail_confirmed` (§1.3). Тело несёт лишь `action: "advance"` + `seq` (§5; сверка `seq` по позиционному курсору, §5.2). | cookie | см. §1.3 |
| E10 | `POST` | `/api/lesson/answer` | **Ответ на вопрос** (training / main_question / main_question_backup). Тело: выбранная буква A–D + `message_id` + `seq`. **Сервер судит** (§2): сверяет с `correct_answer` из CSV, деривит correct/wrong, feedback_X, return_X, целевое `evt_*`. Клиент НЕ шлёт семантику «верно/неверно». | cookie | `evt_answer_correct` / `evt_answer_wrong` / `evt_training_max_errors` / `evt_main_correct_attempt1` / `evt_main_wrong_attempt1` / `evt_main_correct_attempt2` / `evt_main_wrong_attempt2` |
| E11 | `POST` | `/api/lesson/cancel` | «Выйти из урока» из любого `lesson_*`: `evt_cancel_lesson --> registered`, прогресс сохранён (`PERSIST_RESUMABLE_PROGRESS`, S-10, EC-02). | cookie | `evt_cancel_lesson` |
| E12 | `POST` | `/api/repeat/answer` | Ответ в R1/R2: `repeat_1h_active` (`evt_repeat_1h_answered`), `repeat_evening_active` (`evt_repeat_evening_answered`). Сервер судит ответ как §2 (это вопрос-стадия `repeat_1h`/`repeat_evening`); судейство НЕ влияет на переход (R1/R2 засчитываются по факту ответа, откат интервала — §3.3/EC-05), но даёт feedback-render. | cookie | `evt_repeat_1h_answered` / `evt_repeat_evening_answered` |

> **Самопетли R1/R2/blocked** (`repeat_1h_pending + evt_open_app` → countdown; `repeat_evening_active + evt_open_app` → prompt; `daily_blocked + evt_open_app`) — это `GET /api/day` (E4): чтение состояния возвращает соответствующий render (`SHOW_R1_COUNTDOWN` / `SHOW_EVENING_PROMPT` / `SHOW_BLOCKED_MESSAGE`). Самопетля НЕ требует отдельного command-эндпоинта — она не меняет состояние (dest == src), а только показывает сообщение. Если же ученик в `repeat_evening_active` нажимает «начать вечернее повторение» и отвечает — это E12.
> **Удаление аккаунта** (`evt_delete_account`) и **logout** — уже зона `account_service` / auth (v4 §8, reg api). В охват дневного потока не входят; здесь не дублируются.

### 1.3 Маппинг единой кнопки «Дальше» (E9 `advance`) на разные evt по stage

E9 принимает один `action: "advance"`; конкретное событие — функция текущего `fsm_state` (= stage урока). Сервер читает `fsm_state` из БД (НЕ из запроса) и выбирает:

| Текущий `fsm_state` (stage) | Деривированное `evt_*` (E9) | dest | Источник (v4 §2б) |
|------------------------------|------------------------------|------|--------------------|
| `lesson_hook` | `evt_hook_read` | `lesson_theory` | v4 transition |
| `lesson_theory` | `evt_theory_read` | `lesson_example` | v4 transition |
| `lesson_example` | `evt_example_read` | `lesson_training` | v4 transition |
| `lesson_theory_review` | `evt_theory_reviewed` | `lesson_main_question_backup` | v4 transition |
| `lesson_final` | `evt_lesson_complete` | `repeat_1h_pending` ИЛИ `course_complete` (guard `all_lessons_passed`, §3) | v4 transition |
| `lesson_failed` | `evt_lesson_fail_confirmed` | `daily_blocked` | v4 transition |

> **`lesson_theory`/`lesson_example` — многоэкранные внутри одного FSM-состояния** (§3.1): на не-последнем экране стадии E9 НЕ диспатчит FSM-событие, а двигает `current_message_id` к следующему сообщению той же стадии (внутри-стадийный шаг). FSM-событие (`evt_theory_read`/`evt_example_read`) диспатчится только когда показан ПОСЛЕДНИЙ экран стадии и ученик жмёт «Дальше». Сервер определяет «последний ли это экран стадии» по правилу §3.1 — клиент этого не знает и не присылает. Дедуп таких внутри-стадийных шагов E9 — по позиционному курсору, НЕ по `message_id`-сверке (§5.2, R1-№4).
> **`lesson_training`/`lesson_main_question`/`lesson_main_question_backup`/`repeat_*` — НЕ через E9**: на вопрос-стадиях кнопки «Дальше» нет, есть выбор A–D → E10/E12. Вызов E9 в вопрос-стадии → 409 `wrong_action_for_stage` (§5): действие не соответствует стадии (сервер знает stage, клиент не навязывает событие).
> **Почему сервер, а не клиент, выбирает evt:** клиент мог бы прислать `evt_lesson_complete` из `lesson_theory` и «проскочить» урок. Единая `advance` + серверная деривация по `fsm_state` это исключают (анти-подмена прогресса, CLAUDE.md §6; v4 §3 `progress_own/write` через FSM).

---

## 2. Серверное судейство ответа (анти-подмена, CLAUDE.md §6)

### 2.1 Принцип

**Клиент НЕ шлёт семантические события** `evt_answer_correct` / `evt_answer_wrong` / `evt_main_correct_attempt1` / ... — это был бы «фронтенд судит сам себя» (запрещено матрицей прав v4 §3: `progress_own/write` «только через FSM-эндпоинты»). Запрос E10/E12 несёт ТОЛЬКО:
- `message_id` — какое сообщение-вопрос судится (сервер сверяет, что оно = `current_message_id` Progress; иначе 409 `stale_message`, §5);
- `selected` — выбранная буква `A|B|C|D`;
- `seq` — sequence-эхо для дедупликации (§5).

Сервер делает ВСЁ остальное.

### 2.2 Алгоритм судейства (E10; E12/E6-warmup аналогично для repeat-/warmup-стадий)

1. Прочитать `fsm_state` и `Progress` из БД (источник истины, не клиент). Проверить, что `fsm_state` — вопрос-стадия (`lesson_training`/`lesson_main_question`/`lesson_main_question_backup`); иначе 409 `wrong_action_for_stage`.
2. Проверить `message_id == Progress.current_message_id` (анти-stale/анти-двойная-вкладка). Несовпадение → 409 `stale_message` (EC-03).
3. Загрузить `LessonMessage` по `(lesson_id, message_id)` через `csv_loader` (плоский список, §3.1). Проверить `selected` ∈ непустых `options` (иначе 422 `invalid_option`).
4. **`is_correct = (selected == message.correct_answer)`** — сервер сверяет с CSV. `correct_answer` гарантированно A/B/C/D (keeper.py). Клиент к этому сравнению не причастен.
5. Деривировать **render**: `feedback_X = message.feedbacks[selected]`; при wrong — `return_target = message.returns[selected]` (полный `message_id`, §3.1; если в CSV пусто — fallback §3.5).
6. Деривировать **целевое `evt_*`** по таблице §2.3 (зависит от stage, is_correct и счётчиков `main_question_attempts` / `training_errors[message_id]`). **Счётчик в `ctx` подаётся в значении ДО инкремента** (R1-№3): сервер читает текущее значение из Progress, кладёт в `FSMContext`, НЕ инкрементит сам перед dispatch. Инкремент (`INCREMENT_MAIN_ATTEMPT` / `RECORD_TRAINING_ERROR`) — это **side-effect движка**, исполняемый fsm_service ПОСЛЕ выбора перехода (см. §2.2-bis).
7. Диспатчить событие через `lesson_engine.dispatch(fsm_state, evt, ctx)` с серверно-собранным `FSMContext` (`training_remaining`, `main_question_attempts`, `all_lessons_passed` — §3, значения ДО инкремента); `dispatch` вернёт `(new_state, effects)`; затем fsm_service **исполняет side-effects транзакционно** (в т.ч. инкремент счётчиков); атомарно обновить `StudentProfile.fsm_state` + `Progress` (v4 §1 «fsm_state обновляется атомарно с Progress»).
8. Вернуть render-payload нового состояния (§4): correct → следующее сообщение/стадия; wrong → feedback + цель return_X + перерисованная стадия; max-errors/fail → fail-render; correct-final → final-render.

### 2.2-bis Порядок «гард ДО инкремента» (сверено с `lesson_engine.py`, R1-№3)

Зафиксировано явно во избежание ложного 409/`GuardError` в коде. В `lesson_engine.py`:
- гард `MAIN_WRONG_ATTEMPT1` = `c.main_question_attempts == 0` (вход в первую попытку), side-effect `INCREMENT_MAIN_ATTEMPT` доводит до 1 ПОСЛЕ выбора перехода;
- гард `MAIN_CORRECT_ATTEMPT2` / `MAIN_WRONG_ATTEMPT2` = `c.main_question_attempts == 1` (вход в резерв = вторая попытка), `INCREMENT_MAIN_ATTEMPT` доводит до 2 ПОСЛЕ;
- docstring `lesson_engine.py` (строки 12–17): «гард `wrong_attempt2` проверяет вход в резерв (`attempts==1`), а не пост-инкремент; "==2" в тексте v4 §2б — это значение ПОСЛЕ инкремента».

**Транспортное правило (несущее для кодера):** сервер собирает `ctx.main_question_attempts` из ТЕКУЩЕГО `Progress.main_question_attempts` (значение ДО обработки этого ответа) и НЕ инкрементит счётчик до `dispatch`. Если сервер ошибочно инкрементит ДО dispatch, гард `==0`/`==1` не пройдёт → `GuardError` → ложный 409 `guard_failed`. Инкремент — исключительно через side-effect движка (`INCREMENT_MAIN_ATTEMPT`, `RECORD_TRAINING_ERROR`), исполняемый fsm_service после выбора перехода и атомарно с `fsm_state`. То же для `training_errors[message_id]`: в `ctx` сервер кладёт значение, нужное для выбора между `evt_answer_wrong` (ещё < порога) и `evt_training_max_errors` (см. §2.3), а фактический инкремент-запись в JSON делает side-effect `RECORD_TRAINING_ERROR`.

### 2.3 Таблица деривации события из (stage, is_correct, счётчики)

Сервер выбирает `evt_*`. Счётчики — серверные (Progress), не из клиента; в `ctx` — значение ДО инкремента (§2.2-bis). Пороги — `config.MAX_TRAINING_ERRORS=3`, `config.MAX_MAIN_QUESTION_ATTEMPTS` (счётчик 0..3; провал главного вопроса при 2 неверных, см. lesson_engine docstring строки 12–17).

| stage (= `fsm_state`) | is_correct | Условие счётчика (серверное, значение ДО инкремента) | Деривированное `evt_*` | dest |
|------------------------|-----------|-------------------------------|--------------------------|------|
| `lesson_training` | true | `training_remaining` (есть ещё training-вопрос, §3.1) | `evt_answer_correct` | `lesson_training` |
| `lesson_training` | true | НЕ `training_remaining` (Q-последний пройден) | `evt_answer_correct` | `lesson_main_question` (автопереход — §3.2) |
| `lesson_training` | false | `training_errors[message_id]` ДО инкремента < 2 (этот wrong — не 3-й; side-effect доведёт счётчик до < 3) | `evt_answer_wrong` (side-effect `RECORD_TRAINING_ERROR`) | `lesson_training` (возврат по return_X, §3.1) |
| `lesson_training` | false | `training_errors[message_id]` ДО инкремента == 2 (этот wrong — 3-й подряд) | `evt_training_max_errors` | `lesson_failed` |
| `lesson_main_question` | true | `main_question_attempts == 0` (вход в 1-ю попытку) | `evt_main_correct_attempt1` | `lesson_final` |
| `lesson_main_question` | false | `main_question_attempts == 0` (вход в 1-ю попытку; side-effect `INCREMENT_MAIN_ATTEMPT` доведёт до 1) | `evt_main_wrong_attempt1` | `lesson_theory_review` |
| `lesson_main_question_backup` | true | `main_question_attempts == 1` (вход в резерв = 2-я попытка) | `evt_main_correct_attempt2` (`ENQUEUE_PASSED_ATTEMPT_2_REVIEW`) | `lesson_final` |
| `lesson_main_question_backup` | false | `main_question_attempts == 1` (вход в резерв; side-effect `INCREMENT_MAIN_ATTEMPT` доведёт до 2 → провал) | `evt_main_wrong_attempt2` | `lesson_failed` |
| `morning_warmup` (E6 `answer`, стадия `repeat_morning`) | true/false | — (warmup-ответ не диспатчит FSM-событие; только feedback-render; серверный счётчик «3 вопроса», §2.5) | — (нет evt; по исчерпании счётчика сервер деривит `evt_warmup_complete`) | `morning_warmup` (пока вопросы есть) → `lesson_select` (по `evt_warmup_complete`) |
| `repeat_1h_active` (E12) | true/false | — (ответ засчитывается по факту; судейство только для feedback-render) | `evt_repeat_1h_answered` | `repeat_evening_pending` |
| `repeat_evening_active` (E12) | true/false | — | `evt_repeat_evening_answered` | `review_queue_scheduled` |

> **«3 ошибки подряд на ОДНОМ вопросе» (D-2, трактовка v4):** счётчик — `Progress.training_errors[message_id]` (JSON, по `message_id`). Сервер инкрементит на каждый wrong по этому `message_id` через side-effect `RECORD_TRAINING_ERROR`; верный ответ на этот навык переводит к следующему вопросу (счётчик данного вопроса больше не растёт). 3-й wrong подряд (счётчик ДО инкремента == 2) → `evt_training_max_errors`. Это ровно D-2-трактовка v4 «3 ошибки на один тренировочный вопрос подряд», уже принятая; аддендум её НЕ переоткрывает, лишь биндит на E10.
> **R1/R2-судейство (E12):** на стадиях `repeat_1h`/`repeat_evening` сервер тоже судит ответ (это question-стадии, keeper.QUESTION_STAGES), НО переход (`evt_repeat_1h_answered`/`evt_repeat_evening_answered`) в v4 не имеет ветки по correctness — он происходит по факту ответа. Поэтому судейство E12 даёт ТОЛЬКО feedback-render; откат интервала при ошибке (EC-05 «интервал откатывается на шаг назад») — забота `review_service` на side-effect, не FSM-ветка. Эта семантика — из v4 EC-05 и §2б, не новая.

### 2.4 Что сервер деривит и клиент НЕ присылает (сводка анти-подмены)

| Поле | Кто источник | Почему не от клиента |
|------|--------------|----------------------|
| `is_correct` | сервер (сравнение `selected` с `correct_answer` CSV) | иначе фронтенд «проходит» любой вопрос |
| `feedback_X` | сервер (`message.feedbacks[selected]`) | контент только из CSV (v4 §3 `lesson_content/read` только сервер) |
| `return_target` | сервер (`message.returns[selected]`) | навигация возврата — из CSV, не из клиента |
| целевое `evt_*` | сервер (таблица §2.3) | `progress_own/write` только через FSM (v4 §3) |
| `main_question_attempts`, `training_errors`, **счётчик 3 warmup-вопросов** | сервер (Progress / warmup-сессия) | счётчики mastery и темпа — анти-обход (CLAUDE.md §6) |
| `evt_warmup_complete` (исчерпание разминки) | сервер (по серверному счётчику 3 вопросов, §2.5) | клиент не решает, что разминка пройдена (анти-подмена темпа) |
| `current_lesson_id`, следующий урок | сервер (манифест §3) | секвенирование курса — серверное |
| `LessonProgress` (этап 1–6) | сервер (по stage) | производное от `fsm_state` |

### 2.5 R3-разминка (`morning_warmup`): счётчик 3 вопросов и деривация `evt_warmup_complete` (R1-№2)

`morning_warmup` (A6 `WarmupRunner`, A6 §3.2: «3 коротких interleaved-вопроса») — отдельное FSM-состояние v4 с переходом `morning_warmup --evt_warmup_complete--> lesson_select`. R3-вопросы разминки — это question-стадия `repeat_morning` (render-payload §4.1, enum `stage`; keeper.QUESTION_STAGES), берутся из `review_queue` (due-повторения). Транспортно недоопределено в v1-исходнике — фиксируется здесь без изменения FSM:

1. **Ответ на R3-вопрос разминки — через E6 `answer`** (НЕ E10/E12: это не урок и не R1/R2, у разминки своя ручка `/api/day/warmup`). Сервер судит ответ ровно как §2.2 (сверка `selected` с `correct_answer`, feedback_X из CSV) — это нужно для feedback-render (A6 `AnswerFeedback`, A8 `lesson.feedback.correct`/`lesson.feedback.trap`).
2. **Warmup-answer НЕ диспатчит FSM-событие** (аналогично repeat-стадиям R1/R2, у которых переход по факту, а не по correctness; и аналогично внутри-стадийному шагу). Состояние остаётся `morning_warmup`, пока в текущей разминке есть невыданные вопросы. Correctness разминки на FSM-переход не влияет.
3. **Счётчик «3 вопроса разминки» — серверный** (анти-подмена темпа, как `training_remaining`/`main_question_attempts`; §2.4). Сервер ведёт его в серверной warmup-сессии (число выданных/отвеченных R3-вопросов текущей разминки; реализационно — поле сессии дня / транзиентное состояние, НЕ новая колонка Progress; модель НЕ меняется). Клиент НЕ присылает «разминка пройдена».
4. **`evt_warmup_complete` деривит СЕРВЕР** по исчерпанию счётчика: когда отвечен последний (3-й) R3-вопрос (или вопросов в `review_queue` оказалось меньше 3 и они исчерпаны) — сервер на том же ответе E6 `answer` диспатчит `evt_warmup_complete` → `lesson_select` и возвращает render целевого состояния (обычно сразу `lesson_hook` следующего урока, как `lesson_select` транзитно, §3 / A6 §3.2). Отдельный клиентский вызов `complete` НЕ требуется.
5. **`skip` (`evt_warmup_skip`)** остаётся клиентским действием E6 (явное «Пропустить разминку», v4 transition `daily_start --evt_warmup_skip--> lesson_select` при `user_skipped_warmup`, и выход из `morning_warmup` решается продуктом A6 — кнопка «Пропустить разминку» на экране разминки; транспортно: E6 `skip` в `morning_warmup` → сервер деривит `evt_warmup_complete` как «разминка завершена досрочно» → `lesson_select`, без штрафа). *Примечание: v4 НЕ имеет прямого `morning_warmup --evt_warmup_skip-->`; единственный выход из `morning_warmup` — `evt_warmup_complete`. Поэтому досрочный «пропустить» внутри разминки сервер биндит на `evt_warmup_complete` (разминка считается завершённой), НЕ вводя нового перехода. Это транспортная трактовка существующего перехода, не новое FSM-поведение; помечено для сверки А4.*

> **R2-№2 — skip-внутри-разминки НЕ помечает невыданные/неотвеченные R3-вопросы как `done`.** Когда `skip` внутри `morning_warmup` биндится на `evt_warmup_complete` (п.5), сервер НЕ имеет права засчитать (`done=true`) те R3-вопросы из `review_queue`, которые НЕ были выданы или были выданы, но не отвечены к моменту пропуска. Их `due_date` СОХРАНЯЕТСЯ как было — они снова всплывут в ближайшей доступной разминке/повторении. Засчитывается (отмечается отвеченным/обновляет интервал через `review_service`) ТОЛЬКО фактически отвеченный R3-вопрос. Это согласовано с EC-19 (v4: «skip → due_date остаются», пропуск разминки не сжигает запланированные повторения) — досрочный выход не должен «терять» интервальные карточки. Транспортный контракт E6 `skip`: сервер диспатчит `evt_warmup_complete`, но НЕ вызывает «mark all warmup items done» — только переход состояния; статус невыданных/неотвеченных R3-вопросов в `review_queue` остаётся due. **Помечено на сверку с `review_service`** (он владеет `due_date`/счётчиком интервала; аддендум фиксирует требование «skip не трогает due невыданных», не переопределяя логику интервалов EC-05/EC-19).

> **Что НЕ меняется:** `morning_warmup`, `evt_warmup_available`/`evt_warmup_skip`/`evt_warmup_complete`, переход `morning_warmup → lesson_select` — дословно v4 §2б. Аддендум лишь говорит: warmup-ответ судится для feedback, FSM-событие на ответ НЕ диспатчится, а `evt_warmup_complete` — серверная деривация по исчерпанию 3 вопросов (или skip). Источник «3» — методический (A6 §3.2 «3 interleaved-вопроса»); если в `review_queue` меньше 3 due — разминка короче, что не блокер.

---

## 3. Контракт секвенирования внутри урока + манифест курса

### 3.1 Внутри урока: правило «следующее сообщение в этапе» (CSV без указателя next)

**Проблема (зафиксирована честно):** FSM v4 считает `lesson_theory` ОДНИМ состоянием, но реально theory = 1–2 экрана, training = Q1/Q2/Q3 (A6 §3.2, S-02). В CSV (`csv_loader.LessonMessage`) есть `return_X`, но НЕТ колонки «следующее сообщение». `csv_loader.load_lesson` отдаёт **плоский список в порядке файла** (`rows[1:]`). Значит «следующее сообщение в этапе» нужно ЗАДАТЬ правилом — иначе кодер импровизирует.

**Правило (транспортно-движковое, архитектор фиксирует):**

1. **Порядок файла = порядок секвенирования.** В пределах одного `lesson_id` сообщения идут в порядке строк CSV (как отдаёт `csv_loader`). Это уже гарантировано keeper.py (структурный контракт) и порядком файла.
2. **Группировка по стадии.** Сообщения одной стадии (`stage`) образуют под-последовательность В ПОРЯДКЕ ФАЙЛА. «Следующее сообщение в стадии» = следующая строка с тем же `stage`, идущая после `current_message_id` в плоском списке, ДО первой строки иной стадии. Если такой строки нет — стадия исчерпана.
3. **Не-вопросные стадии (`hook`/`theory`/`example`/`final`/`lesson_failed`):** многоэкранны. E9 `advance` на не-последнем экране стадии двигает `current_message_id` к следующему сообщению той же стадии БЕЗ FSM-события. На последнем экране стадии E9 диспатчит соответствующее `evt_*_read` (§1.3) → переход к первой строке следующей стадии. **Дедуп внутри-стадийного шага — по позиционному курсору (§5.2), не по `message_id`-сверке (R1-№4).**
4. **Вопросные training-стадии (`training`):** каждая строка `stage=training` — отдельный вопрос (Q1, Q2, Q3 = 3 строки `training` подряд по порядку файла). `training_remaining` (= `FSMContext.training_remaining`) истинно, если ПОСЛЕ текущего training-`message_id` в плоском списке есть ещё хотя бы одна строка `stage=training` ДО первой не-training строки. Верный ответ на последний training-вопрос → `training_remaining=false` → автопереход в `lesson_main_question` (§3.2).
5. **`training_remaining` считается сервером** по плоскому списку, не клиентом (анти-подмена, §2.4).
6. **`main_question` / `main_question_backup`:** ровно одна «активная» строка стадии на попытку (main_question — первая строка стадии; backup — первая строка `main_question_backup`). Если стадия содержит >1 строки (несколько резервных формулировок) — берётся первая непройденная в порядке файла; выбор — детерминированный (порядок файла), без рандома в v1 (рандомизация — не решена, см. §3.6).

### 3.2 Момент автоперехода `lesson_training → lesson_main_question`

Согласовано с `lesson_engine.py` (transition `LESSON_TRAINING --ANSWER_CORRECT--> LESSON_MAIN_QUESTION [guard: not training_remaining]`) и v4 §8 (`fsm_service → lesson_engine`: «после evt_answer_correct движок проверяет, остались ли training-вопросы; если все Q1..Q3 пройдены — автоматически генерирует переход в lesson_main_question без дополнительного события от клиента»).

**Транспортный контракт:** при E10 с верным ответом на ПОСЛЕДНИЙ training-вопрос сервер диспатчит `evt_answer_correct` с `ctx.training_remaining=false` → `dispatch` сам выбирает переход в `lesson_main_question` (guard). Клиент получает в одном ответе E10 render-payload УЖЕ `lesson_main_question` (первого main-вопроса). Отдельного `evt_training_complete` НЕТ (упразднён в v4 §2б). Дополнительного round-trip клиента не требуется.

### 3.3 Между уроками: манифест курса (упорядоченный список 27 lesson_id) — ВКЛЮЧЁН В ЭТОТ АДДЕНДУМ

**Проблема (зафиксирована честно как блокер кодера):** guard `lesson_select --evt_start_lesson--> lesson_hook [следующий незавершённый урок существует]` и `--evt_all_lessons_done--> course_complete [все 27 passed]` (v4 §2б) требуют **упорядоченного списка 27 `lesson_id`**. Его НЕТ нигде: `config.py` имеет только `FIRST_LESSON_ID="1_1"` и `TOTAL_LESSONS=27`. Без манифеста кодер не сможет вычислить «следующий незавершённый урок» и «все ли 27 passed».

**Решение:** манифест курса задаётся как **минимальный серверный интерфейс**, на который опираются E8/E4 (а не разбросанная логика). Он НЕ требует новой ORM-таблицы (Lesson/LessonMessage в БД нет — v4 §1, models.py). Интерфейс:

```
COURSE_MANIFEST: tuple[str, ...]   # упорядоченный кортеж ровно 27 lesson_id, индекс = позиция в курсе
                                   # инвариант: len == config.TOTAL_LESSONS; COURSE_MANIFEST[0] == config.FIRST_LESSON_ID
```

Операции, на которые биндятся endpoints (чистые функции над манифестом + Progress ученика):

| Функция | Сигнатура (контракт) | Используется в |
|---------|----------------------|----------------|
| `next_unpassed_lesson(progress_by_lesson)` | → `str | None`: первый по порядку манифеста `lesson_id`, чей `Progress.status != passed` И `!= failed_today` (для сегодня) | E8 guard `has_next_lesson`; E4 «есть ли урок» |
| `all_lessons_passed(progress_by_lesson)` | → `bool`: все 27 манифеста имеют `Progress.status == passed` | E8 guard `all_lessons_passed`; E9 на `lesson_final` |
| `is_in_course(lesson_id)` | → `bool`: `lesson_id in COURSE_MANIFEST` | валидация E7/E8 (урок принадлежит курсу — v4 §3 `lesson_content/read`) |

> **`FSMContext` для E8:** `has_next_lesson = next_unpassed_lesson(...) is not None`; `next_lesson_failed_today = (Progress[next].status == failed_today)`; `all_lessons_passed = all_lessons_passed(...)`. Эти три поля — ровно входы гардов `lesson_engine.FSMContext` (уже существуют). Аддендум лишь говорит, КАК их вычислить (через манифест), не меняя FSMContext.

### 3.4 Источник данных манифеста — ПРАВКА КОНТРАКТА ДАННЫХ НА ПРИЁМКУ (CLAUDE.md §3)

Манифест нужен, но ОТКУДА берётся упорядоченный список 27 `lesson_id` — это правка §3-контракта данных. Архитектор предлагает вариант и помечает на приёмку фаундеру/Brain-дельту:

- **Предлагаемый вариант (А): явная константа в `config.py`** — `COURSE_MANIFEST: Final[tuple[str, ...]]` = упорядоченные 27 `lesson_id` (например `("1_1","1_2",...,"6_5")`), рядом с `FIRST_LESSON_ID`/`TOTAL_LESSONS`. Плюс: явный, детерминированный, проверяемый (`len==27`, `[0]==FIRST_LESSON_ID`); не зависит от имён файлов; ревьюится глазами. Минус: дублирует знание о порядке, которое есть и в CSV-каталоге.
- **Отвергнутый вариант (Б): выводить порядок из имён файлов каталога `content/`** (`load_lessons_dir` сортирует по имени файла). Минус: хрупко — `sorted(glob("*.csv"))` даёт ЛЕКСИКОГРАФИЧЕСКИЙ порядок (`Контент_урок_1_1`, `..._1_10`, `..._1_2` — `1_10` < `1_2`!), плюс системный контент (`lesson_id=0/system`) подмешивается; имя файла ≠ `lesson_id`. Не годится как источник порядка курса без отдельного маппинга.

**Решение архитектора:** взять вариант (А) — явная `COURSE_MANIFEST` в `config.py`. Это **добавление константы конфигурации** (не ORM-миграция, не изменение CSV-контракта), но оно касается §3-дисциплины «структура/контракт данных не меняется без обновления спеки». Поэтому:
- Помечено как **правка контракта данных на приёмку фаундером** и на Brain-дельту (`/обновить-brain`): «добавить `COURSE_MANIFEST` (27 упорядоченных lesson_id) в config.py — источник секвенирования курса для guard'ов lesson_select».
- Значения самих 27 `lesson_id` — **НЕ продуктовая развилка** (порядок программы методически детерминирован, как и `FIRST_LESSON_ID=1_1`), но конкретный список должен быть сверен с фактическим набором CSV в `content/` (зона keeper.py/контент-продюсера). Кодер НЕ выдумывает список — он берёт его как заданную константу; если на момент кодирования каталог содержит не 27 уроков, это блокер контента, не кода (поднять фаундеру).

#### 3.4-bis ЕДИНОЕ пространство `lesson_id` для манифеста, Progress и контента (R2-№1)

§3.4 закрывает ИСТОЧНИК порядка курса (`COURSE_MANIFEST`), но НЕ закрывает рассинхрон ПРОСТРАНСТВ идентификаторов, по которым три подсистемы ключуются. Фиксируется требование к схеме (без выдумывания конкретных 27 id):

**Требование (несущее для кодера):** должно существовать ЕДИНОЕ пространство `lesson_id`, по которому ключуются согласованно:
- (а) `COURSE_MANIFEST[i]` — позиция урока в курсе;
- (б) `Progress.lesson_id` — статус прохождения урока учеником (models.py, `uq_progress_user_lesson`);
- (в) ключ загруженного контента урока в `csv_loader` (по которому сервер берёт `LessonMessage` урока в E7/E8/E10).

Без согласования этих трёх пространств кодер не сможет связать «позиция в курсе ↔ прогресс ученика ↔ контент урока» и будет вынужден импровизировать маппинг.

**Проблема (зафиксирована честно):** сейчас эти три пространства РАЗНЫЕ.
- `csv_loader.load_lessons_dir` ключует возвращаемый словарь по **ИМЕНИ ФАЙЛА** (`csv_path.stem`), а НЕ по `lesson_id` (col3).
- Фактический `lesson_id` (col3) в текущем CSV блока 1 = `"1"` ОДИНАКОВО для всех уроков 1.1–1.9 — то есть `lesson_id` в контенте НЕ уникален по уроку (один и тот же `"1"` на весь блок).
- Итог: `Progress.lesson_id` ↔ `COURSE_MANIFEST[i]` ↔ ключ загруженного контента сейчас в ТРЁХ разных пространствах (имя файла ≠ col3-`lesson_id` ≠ предполагаемый `"1_1".."6_5"` из §3.4). Связать их без явного маппинга невозможно.

**Предлагаемый интерфейс (одно из двух, на выбор реализации — оба согласуют пространство):**
- **(I) `load_lessons_dir` ключует по `lesson_id` (col3)** вместо `csv_path.stem` — тогда ключ контента == `COURSE_MANIFEST[i]` == `Progress.lesson_id` напрямую. Требует, чтобы col3 был УНИКАЛЕН по уроку (см. контентный блокер ниже).
- **(II) ввести аккуратный аксессор `lesson_messages(lesson_id) -> list[LessonMessage]` поверх загрузчика** — функция, которая по `lesson_id` из единого пространства (манифест/Progress) отдаёт плоский список сообщений урока (§3.1), инкапсулируя текущий маппинг «как файлы разложены». Endpoints (E7/E8/E10) обращаются только к этому аксессору, не зная физической раскладки файлов.

**ЧЕСТНАЯ пометка — это КОНТЕНТНЫЙ блокер, НЕ код:** текущее состояние контента — `lesson_id="1"` на весь блок 1 и **9 файлов вместо ожидаемых 27 уроков** — означает, что единого уникального пространства `lesson_id` в данных СЕЙЧАС НЕТ. Привести col3-`lesson_id` к уникальному-по-уроку виду (и довести каталог до 27 уроков) — это **зона keeper.py / контент-продюсера + приёмка фаундера**, НЕ зона кодера. Спека фиксирует ТРЕБОВАНИЕ к схеме идентификаторов (единое пространство для (а)/(б)/(в) + один из интерфейсов I/II), **не выдумывая конкретные 27 id** и не предписывая, как переразметить CSV. Кодер реализует выбранный интерфейс поверх уже согласованного пространства; если на момент кодирования контент остаётся в старом пространстве (`"1"` на блок, 9 файлов) — это блокер контента, поднимается фаундеру, код по E7/E8/E10 не пишется до согласования пространства (CLAUDE.md §1 «нет однозначного контракта данных → стоп»).

**Помечено на приёмку фаундеру/Brain-дельту** (вместе с §3.4 `COURSE_MANIFEST`): «единое пространство `lesson_id` для COURSE_MANIFEST / Progress.lesson_id / ключа контента csv_loader; выбрать интерфейс (I) ключевание load_lessons_dir по col3 ИЛИ (II) аксессор lesson_messages(lesson_id); привести контент к уникальному-по-уроку lesson_id и к 27 урокам — зона keeper.py/контента». Это правка §3-контракта данных, не продуктовая развилка; конкретные значения id НЕ задаются спекой.

> Эта правка минимальна и НЕ ломает models.py (commit ae6e765): новой колонки/таблицы нет. Это конфиг-константа, симметрично уже принятым `FIRST_LESSON_ID`/`TOTAL_LESSONS`/`REVIEW_INTERVALS_DAYS`.

### 3.5 Fallback при битом секвенировании (привязка к EC-08)

Если `return_X` указывает на отсутствующий `message_id` или стадия не находит «следующее сообщение» (повреждённый CSV прорвался мимо keeper.py) — поведение УЖЕ задано v4 EC-08: «движок логирует ошибку, показывает ученику theory с начала урока (safe fallback), не ломает FSM». Транспортно: E9/E10 при недостижимой цели возвращают render первого `theory`-сообщения урока + лог; FSM-состояние не повреждается. Аддендум не вводит нового поведения — биндит EC-08 на endpoints.

### 3.6 НЕ решается здесь (не блокер для этого среза)

- **Рандомизация выбора резервной формулировки `main_question_backup`** при >1 строке стадии: v1 — детерминированно первая строка (§3.1 п.6). Если методически нужна вариативность — это отдельная задача (не блокирует endpoints). Не продуктовая развилка уровня СТОП: дефолт безопасен и не противоречит Методологии.
- **Расписание уроков по дням** (какой урок «сегодня»): v4 `lesson_select` берёт «следующий незавершённый» — один урок-в-день регулируется FSM (`daily_done` после прохождения), не календарём. Манифест даёт порядок, FSM — темп. Доп. контракта не нужно.

---

## 4. Схемы request/response (JSON) + render-payload

Типы: `string`, `integer`, `boolean`, `null`, `array`, `object`. `?` = поле опционально/nullable. Имена — snake_case (контракт с моделью). Render-payload — общий контракт для A6 (`LessonProgress`, `MessageCard`/`QuestionBlock`, `AnswerFeedback`, `ConnectionStub`) и A8 (микрокопи). Все пользовательские ТЕКСТЫ-обёртки (заголовки экранов, кнопки) — зона A8 (`[A8: …]`), НЕ в этом контракте; здесь — структура и контентные поля из CSV.

### 4.1 Общий `render`-блок (возвращается всеми E4/E7/E9/E10/E11/E12)

```json
{
  "fsm_state": "string",              // каноническое состояние (StudentProfile.fsm_state); клиент рендерит экран по нему
  "view": "string",                   // дискриминатор экрана: "day_hub"|"warmup"|"lesson_message"|"lesson_question"|"lesson_feedback"|"lesson_final"|"lesson_failed"|"day_done"|"day_blocked"|"course_complete"|"repeat_pending"|"repeat_question"|"connection_stub"
  "message": {                        // ? присутствует, когда показывается сообщение/вопрос урока (из CSV); null на чисто-хабовых view
    "message_id": "string",
    "stage": "string",                // hook|theory|example|training|main_question|main_question_backup|final|lesson_failed|repeat_1h|repeat_evening|repeat_morning
    "text_html": "string",            // message.text (HTML; рендерится MessageCard — A6)
    "options": [                      // ? непустые варианты (LessonMessage.options); присутствует только на question-стадиях
      { "letter": "A", "text_html": "string" }
    ]
  },
  "lesson_progress": {                // ? присутствует в lesson_* view; индикатор A6 §3.2 «этап 1–6»
    "step": 3,                        // 1..6: 1=hook,2=theory,3=example,4=training,5=main_question,6=final (§4.5)
    "total": 6
  },
  "feedback": {                       // ? присутствует ТОЛЬКО в ответе E10/E12/E6-warmup после судейства (§2)
    "is_correct": true,
    "feedback_html": "string",        // message.feedbacks[selected]; A6 AnswerFeedback (correct/«типичная ловушка»)
    "return_target": "string"         // ? при wrong: message_id, к которому возвращаемся (return_X); null при correct
  },
  "seq": 7,                           // sequence-номер ПОСЛЕ этого перехода (клиент эхо-ит в следующем command-запросе, §5)
  "day": {                            // ? присутствует в day_hub view (E4): тихий контекст дня
    "streak_days": 5,                 // Streak.current_streak (A6 DayCounterBadge, A8 day.counter.badge). ОПЦИОНАЛЬНЫЙ тихий показ — см. ремарку ниже (F-1, R1-№7; дефолт показа R2-№5)
    "warmup_available": false,        // есть due-повторения → разминка доступна
    "has_lesson_today": true          // next_unpassed_lesson существует и не failed_today
  },
  "next_actions": ["advance"]         // подсказка клиенту, какие command'ы валидны сейчас: подмн. ["advance","answer","cancel","start","warmup_start","warmup_skip","warmup_answer"]
}
```

> `next_actions` — НЕ авторитет (сервер всё равно проверяет stage и вернёт 409 на неуместное действие, §1.3/§5), а UX-подсказка для рендера кнопок. Источник истины валидности — серверная проверка `fsm_state`.
> **`streak_days` — для ОПЦИОНАЛЬНОГО тихого показа (F-1, R1-№7).** Сервер отдаёт значение, потому что право `streak_own/read=true` (v4 §3) соблюдено, НО сервер НЕ предписывает его заметность и не требует показа. Методология §1.3 (без давящих счётчиков) + A8 §2 (`day.counter.badge`: «тихо, вторично — заметность за фаундером, F-1») оставляют решение показывать/скрывать/насколько заметно — на стороне клиента и фаундера (A6 `DayCounterBadge`, F-1 не закрыта). Контракт лишь делает поле доступным; UX-политика показа здесь НЕ задаётся и НЕ навязывается (анти-тёмный-паттерн, Methodology §1.3).
> **R2-№5 — дефолт клиента ДО решения фаундера по F-1: ТИХИЙ/СКРЫТЫЙ показ.** Пока F-1 (заметность счётчика дней) не закрыта фаундером, дефолтное поведение клиента — **fail-safe в сторону Methodology §1.3 «без сгорания/давления»**: `streak_days` показывается тихо/скрыто (минимальная заметность или скрыт вовсе), НЕ заметным счётчиком и НЕ с акцентом на «не потеряй серию». Это безопасный дефолт (нельзя случайно ввести давящий streak-паттерн до явного продуктового решения), а не финальная политика — финальную заметность решает фаундер (F-1). Сервер по-прежнему лишь отдаёт значение; направление дефолта (тихо, а не громко) фиксируется здесь как fail-safe, чтобы клиент при отсутствии решения не дефолтил в сторону давления.

### 4.2 E5 `POST /api/day/open` — вход в день

**Request body:** `{}` (или пустое). Контекст — из cookie + БД.
**Response 200:** `render`-блок с `view: "day_hub"` (или `view` целевого состояния после `evt_open_app`; при `missed_day_end` сервер сначала отрабатывает отложенный `streak_update`, §7, и затем отдаёт day_hub).

### 4.3 E8 `POST /api/lesson/start` — старт следующего урока

**Request body:** `{ "seq": <int> }` (эхо последнего seq; §5).
**Response 200 (урок есть):** `render` с `view: "lesson_message"`, `message` = первое `hook`-сообщение, `lesson_progress.step=1`, `fsm_state: "lesson_hook"`.
**Response 200 (тупик):** сервер по манифесту (§3) деривит исход — `view: "day_done"` (`evt_no_lesson_today`, нет новых) / `view: "day_blocked"` (`evt_no_lesson_today`, failed_today) / `view: "course_complete"` (`evt_all_lessons_done`, все 27 passed).

### 4.4 E9 `POST /api/lesson/advance` — «Дальше»

**Request body:**
```json
{ "action": "advance", "seq": 7 }
```
**Response 200:** `render` нового состояния (следующий экран стадии ИЛИ первая строка следующей стадии после FSM-перехода, §3.1). На `lesson_final` + `advance` → `view: "repeat_pending"` (R1) или `course_complete`. На `lesson_failed` + `advance` → `view: "day_blocked"`.
**409 `wrong_action_for_stage`** — `advance` прислан в question-стадии (там нужен E10), §5.
**Дедуп E9:** сверка `seq` — по позиционному курсору `(stage, индекс сообщения в стадии)`, НЕ по `message_id` (E9 в теле `message_id` не несёт). См. §5.2.

### 4.5 E10 `POST /api/lesson/answer` — ответ (серверное судейство, §2)

**Request body:**
```json
{ "message_id": "string", "selected": "A", "seq": 7 }
```
**Response 200 (correct):** `render` с `feedback.is_correct=true`, `feedback.feedback_html`, `feedback.return_target=null`; `message`/`fsm_state` = СЛЕДУЮЩЕЕ состояние (следующий training-вопрос / `lesson_main_question` при автопереходе / `lesson_final`). `lesson_progress.step` обновлён.
**Response 200 (wrong с возвратом, не фатально) — ЕДИНЫЙ контракт (R1-№6):** `view: "lesson_feedback"` (один дискриминатор для обоих под-случаев wrong-с-возвратом). Блок `feedback` несёт `is_correct=false`, `feedback_html` (= feedback_X выбранной буквы) И `return_target` (= return_X). Блок `message` несёт сообщение возврата (theory-кусок по return_target) — то есть payload «wrong с возвратом» содержит И feedback, И message возврата ОДНОВРЕМЕННО. A6 рендерит `AnswerFeedback` (тон «типичная ловушка», `--trap`) + следом `MessageCard`/`QuestionBlock` возврата из того же ответа, без второго round-trip. Два под-случая под одним `view: "lesson_feedback"`:
  - **training-wrong (<3):** `fsm_state` остаётся `lesson_training`; `message` = вопрос для повторной попытки по `return_target` (возврат к нужному куску/вопросу, §3.1).
  - **main-wrong#1:** `fsm_state: "lesson_theory_review"`; `message` = theory-кусок повтора (A8 `lesson.theory_review`); далее ученик жмёт «Дальше» (E9 → `evt_theory_reviewed` → `lesson_main_question_backup`).

  > Дискриминатор для A6 однозначен: `view: "lesson_feedback"` всегда = «есть feedback + есть message возврата в ОДНОМ payload»; различие training-wrong / main-wrong#1 клиент берёт из `fsm_state`, не из `view`. `view: "lesson_message"` остаётся для случаев БЕЗ feedback (resume, чистый theory-экран по advance). Это снимает прежнюю двойственность (§4.9-исходник давал `lesson_message` и `lesson_feedback` на один исход).
**Response 200 (wrong → fail):** при 3-й training-ошибке или main-wrong#2 → `view: "lesson_failed"`, `feedback.is_correct=false`, `message` = `lesson_failed`-сообщение из CSV (DeferCard, A6).
**Response 200 (correct → final):** main-correct#1/#2 → `view: "lesson_final"`, `message` = `final`-сообщение, `lesson_progress.step=6`.
**422 `invalid_option`** — `selected` ∉ непустых опций сообщения. **409 `stale_message`** — `message_id != Progress.current_message_id` (EC-03). **409 `wrong_action_for_stage`** — текущая стадия не вопросная.

### 4.6 E7 `GET /api/lesson/current` — resume (EC-02)

**Request:** без тела (cookie).
**Response 200:** `render` ТЕКУЩЕГО сохранённого сообщения (`Progress.current_message_id`), `fsm_state` из профиля, `view: "lesson_message"`/`lesson_question` (БЕЗ блока `feedback` — resume не несёт результата ответа). Если `fsm_state` не в уроке (`registered` с in_progress-прогрессом, после S-10 cancel) — `view: "lesson_message"` с resume-точкой + флаг возобновления; клиент показывает «Продолжить урок». Если контент не подгрузился офлайн (D-5) — клиент сам рендерит `connection_stub` (это клиентский fallback, не отдельный код сервера); сервер при наличии контента всегда отдаёт сообщение.

### 4.7 E11 `POST /api/lesson/cancel` — выход из урока

**Request body:** `{ "seq": <int> }`.
**Response 200:** `render` с `fsm_state: "registered"`, `view: "day_hub"`; `Progress.status=in_progress`, `current_message_id` сохранён (S-10). Урок возобновляем через E7.

### 4.8 E12 `POST /api/repeat/answer` — ответ R1/R2

**Request body:** `{ "message_id": "string", "selected": "A", "seq": <int> }`.
**Response 200:** `render` с `feedback` (судейство §2.3 — только для показа), `fsm_state` = следующее (`repeat_evening_pending` после R1; `review_queue_scheduled` после R2). Откат интервала при ошибке — side-effect `review_service` (EC-05), не отражается отдельным кодом.

### 4.9 Что отдаётся в ключевых случаях (сводка для A6/A8)

| Случай | `view` | `feedback` | `message` |
|--------|--------|-----------|-----------|
| resume (EC-02) | `lesson_message`/`lesson_question` | нет | текущее сохранённое |
| correct (training, ещё есть) | `lesson_question` | is_correct=true | следующий training-вопрос |
| correct (последний training) | `lesson_question` | is_correct=true | первый main-вопрос (автопереход §3.2) |
| **wrong с возвратом — training (<3)** | **`lesson_feedback`** (R1-№6) | is_correct=false, return_target | feedback + вопрос/кусок возврата по return_X (в одном payload); `fsm_state=lesson_training` |
| **wrong с возвратом — main-wrong#1** | **`lesson_feedback`** (R1-№6) | is_correct=false, return_target | feedback + theory-кусок повтора (в одном payload); `fsm_state=lesson_theory_review` |
| wrong → max_errors / main-wrong#2 | `lesson_failed` | is_correct=false | lesson_failed-сообщение |
| correct → final | `lesson_final` | is_correct=true | final-сообщение |
| warmup-ответ (R3, §2.5) | `warmup` | is_correct (только показ) | следующий R3-вопрос ИЛИ (по исчерпании) render `lesson_select`/`lesson_hook` после `evt_warmup_complete` |

> **Единый дискриминатор «wrong с возвратом» (R1-№6):** оба под-случая отдают `view: "lesson_feedback"` и несут feedback+message в одном payload; различие (вопрос-возврат vs theory-review) клиент читает из `fsm_state`. `view: "lesson_message"` зарезервирован за payload'ами БЕЗ feedback (resume, advance-шаг theory/example). Прежней двойственности (`lesson_message` vs `lesson_feedback` на один исход) больше нет.

---

## 5. Конкурентность и статус-коды

### 5.1 Конвенция кодов (транспортное решение архитектора, фиксируется явно — как reg api §5)

- **200** — успешный command/read (включая идемпотентный повтор перехода, §5.2).
- **400** — некорректный запрос на транспортном уровне (нет обязательного тела/поля `seq`/`selected`, синтаксис).
- **401** — нет/невалидная сессия (cookie) при доступе к E4–E12 (анонимный к защищённому ресурсу урока). *Отличие от reg api:* там анонимный доступ к онбордингу — норма; здесь дневной поток требует сессии. 401 = «не аутентифицирован».
- **403** — аутентифицирован, но deny-by-default по матрице прав v4 §3: попытка читать/писать ЧУЖОЙ ресурс (`progress_other`/`lesson` не своего ученика) — F-10; либо EC-09 (`lesson_content` урока в статусе failed_today — «доступен завтра»). 403 ТОЛЬКО за deny-by-default доступом, НЕ за validation.
- **404** — `lesson_id`/`message_id` вне курса/урока (`is_in_course=false`, §3.3) — ресурс не существует.
- **409** — конкурентный/состоянийный конфликт: дубль перехода после сделанного (EC-01), две вкладки (EC-03, `stale_message`), действие не соответствует стадии (`wrong_action_for_stage`), optimistic-конфликт записи Progress (F-07). См. §5.2–5.4.
- **422** — семантически невалидное значение тела: `selected` ∉ опций (`invalid_option`), невалидный формат `seq`.

Тело ошибки (как reg api): `{ "error": "<code>", "field": "<поле|null>" }`.

### 5.2 Дедупликация перехода БЕЗ version-колонки у Progress: sequence-эхо (основной механизм)

**Проблема:** `Progress` (models.py, commit ae6e765) НЕ имеет `version`/`lock`-колонки. EC-01 (дабл-клик), EC-03 (две вкладки → 409), F-07 (optimistic lock → 409) требуют механизма, чтобы повторный/гоночный command не задвоил переход.

**Решение (основное, без правки модели): монотонный `seq` + сверка позиционного курсора.**

Позиционный курсор прохождения определяется как **пара `(fsm_state/stage, индекс сообщения в стадии)`** — где «индекс сообщения в стадии» = позиция `current_message_id` в под-последовательности своей стадии по порядку файла (§3.1). `seq` выводится детерминированно из этой позиции (+ счётчик попыток для вопрос-стадий), НЕ требует новой колонки — это производное от уже сохраняемого `Progress.current_message_id` + `fsm_state` + счётчиков.

> **R2-№4 — семантика инкремента `seq`: `seq++` на КАЖДОМ ПРИНЯТОМ command.** Уточнение во избежание неоднозначности дедупа после возврата по `return_X`. `seq` инкрементится на каждом принятом (фактически выполненном) command — **включая** (а) wrong-возврат по `return_X` (E10 training-wrong: `fsm_state` остался `lesson_training`, но позиционный курсор откатился назад к `return_target`) и (б) внутри-стадийный advance-шаг (E9 двигает `current_message_id` без FSM-события). `seq` растёт монотонно ВСЕГДА при принятом command, **даже если позиционный курсор `(stage, индекс)` откатывается НАЗАД** по `message_id` (как при возврате). То есть `seq` — это счётчик ПРИНЯТЫХ команд прохождения, монотонный, а не функция от одной лишь позиции: позиция может вернуться к ранее посещённому `message_id`, но `seq` уже больше. Это снимает неоднозначность: легитимный повтор того же вопроса ПОСЛЕ возврата по `return_X` (ученик снова на том же `message_id`, что был до ошибки) имеет НОВЫЙ, больший `seq`, и сервер не спутает его с устаревшим дублем старого ответа на тот же `message_id` (у старого дубля `seq` меньше → §5.2 ветвь «seq отстал»). Идемпотентность/409 определяются сверкой как ниже; `seq++ на каждый принятый command` — инвариант, на который эта сверка опирается.

1. Каждый успешный command возвращает в `render.seq` номер, монотонно растущий в пределах прохождения урока (на каждый принятый command, R2-№4).
2. Клиент ЭХО-ит последний полученный `seq` в следующем command (`E6/E8/E9/E10/E11/E12`).
3. **Сверка на сервере — две ветви по типу действия:**

   **(а) E10/E12/E6-answer (ответ на вопрос; тело несёт `message_id`):** сервер сравнивает (`message_id` запроса == `Progress.current_message_id`) И (`seq` соответствует текущей позиции).
   - **Совпало, переход возможен** → выполнить, вернуть новый `seq`.
   - **`message_id` устарел** (ответ на уже пройденное сообщение — дабл-клик/вторая вкладка, EC-01/EC-03) → **409 `stale_message`**. Клиент перечитывает E7 и продолжает с актуальной точки. Повторного перехода не происходит.
   - **`seq` отстал, но `message_id` совпадает** (легитимный повтор того же шага после таймаута/дабл-клика до ответа) → **идемпотентно: 200 с ТЕКУЩИМ render** (переход уже сделан ровно один раз; не диспатчить второй раз). Дружелюбный путь для EC-01 (ученик не видит ошибку из-за дабл-клика — A6/A8 тон «не наказываем»). *После легитимного возврата по `return_X` ученик снова на том же `message_id`, но с БОльшим `seq` (R2-№4): это уже НЕ «отставший seq», а новый принятый шаг — сервер судит его как свежий ответ, не как дубль.*

   **(б) E9 `advance` (тело несёт ТОЛЬКО `action`+`seq`, БЕЗ `message_id`) — R1-№4:** для нон-вопросных стадий, включая внутри-стадийный шаг theory/example (двигает `current_message_id` без FSM-события), сверка по `message_id` НЕприменима. Сервер сверяет присланный `seq` против СЕРВЕРНОГО позиционного курсора `(stage, индекс сообщения в стадии)`:
   - **`seq` совпадает с текущей позицией** (позиция не двигалась с момента выдачи этого `seq`) → выполнить шаг (внутри-стадийный сдвиг ИЛИ FSM-переход по §1.3), вернуть новый `seq`.
   - **`seq` отстал, но позиция ТА ЖЕ** (`(stage, индекс)` не изменились — легитимный повтор `advance` после таймаута/дабл-клика, шаг уже выполнен ровно один раз) → **200 идемпотентно** с ТЕКУЩИМ render; второй раз шаг НЕ выполняется (ни внутри-стадийный сдвиг, ни dispatch).
   - **`seq` отстал и позиция УШЛА ВПЕРЁД** (`(stage, индекс)` уже другие — поздний дубль на устаревшем экране, EC-01/EC-03 для нон-вопросной стадии) → **409 `stale_message`**; клиент перечитывает E7 (`GET current`) и продолжает с актуальной позиции. Повторного сдвига/перехода нет.

> **Граница «409 stale» vs «200 идемпотентно»** (единая для (а) и (б)): если позиция уже УШЛА ВПЕРЁД относительно того, что прислал клиент — поздний дубль на устаревшем шаге → **409**, перечитать E7. Если позиция ТА ЖЕ и команда идентична — идемпотентный повтор → **200** без второго шага. Различение: для (а) — по `message_id` запроса vs `Progress.current_message_id` (с учётом R2-№4: монотонный `seq` отличает свежий пост-возвратный ответ от устаревшего дубля); для (б) — по `seq` vs серверный курсор `(stage, индекс сообщения в стадии)`.

### 5.3 EC-01 / EC-03 / F-07 на HTTP-слое (биндинг, без переоткрытия)

| v4 id | Что | HTTP-поведение |
|-------|-----|----------------|
| EC-01 | дабл-клик «Далее»/ответ | клиент блокирует кнопку после 1-го нажатия (A6 §3.1); если 2-й запрос ушёл с тем же `seq` и шаг уже сделан → **200 идемпотентный** (тот же render), второй раз FSM/сдвиг не выполняется (§5.2 (а) по `message_id`, (б) по позиции); если позиция ушла → 409 stale → клиент перечитывает E7 |
| EC-02 | закрытие браузера в середине урока | `Progress.current_message_id` + `fsm_state` сохранены при каждом переходе (атомарно, v4 §1); resume через E7 (`GET current`) |
| EC-03 | две вкладки, ответ на один вопрос в обеих | первый command фиксирует переход (`current_message_id`/позиция сдвигается); второй приходит с устаревшим `message_id` (E10) или устаревшим `seq`+ушедшей позицией (E9) → **409 `stale_message`**; состояние не задваивается |
| F-07 | гонка двойной записи Progress | сверка `current_message_id`/позиции + транзакция: проигравший видит уже сдвинутую позицию → **409**; клиент перезагружает (E7) и продолжает |
| EC-09 | прямой URL урока минуя FSM (failed_today) | сервер проверяет `Progress.status`: failed_today → **403** «доступен завтра» (deny-by-default; не validation) |
| F-10 | утечка чужого progress (auth bug) | каждый E4–E12 проверяет `user_id == authenticated` (deps.py + матрица прав v4 §3 deny-by-default); чужой ресурс → **403** |

### 5.4 Опциональная version-колонка Progress — ПРАВКА МОДЕЛИ НА ПРИЁМКУ (не обязательна, по умолчанию НЕ применяется)

Sequence-эхо (§5.2) достаточно для EC-01/EC-03/F-07 БЕЗ изменения модели — это **основной и принятый для среза механизм**. Однако F-07 в v4 §6 буквально называет «optimistic lock на Progress». Архитектор фиксирует развилку реализации честно, **не обещая `row_version` как обязательную**:

- **Принятый для этого среза вариант (по умолчанию):** **без новой колонки** — дедуп через сверку `current_message_id`/позиционного курсора + транзакцию (SQLAlchemy session + БД-транзакция дают атомарность; UniqueConstraint `uq_progress_user_lesson` уже есть). Этого достаточно: переход меняет позицию, гонка проигравшего ловится сверкой (§5.2). **Кодер реализует ИМЕННО ЭТОТ вариант; `row_version` НЕ добавляется без отдельного принятого решения.**
- **Опциональная правка модели (только если фаундер/А4 явно потребуют строгий optimistic lock на уровне БД):** добавить `Progress.row_version: int` (`Integer, nullable=False, default=0`; SQLAlchemy `version_id_col`). Тогда конкурентная запись с устаревшим `row_version` → `StaleDataError` → 409. Это **изменение models.py (commit ae6e765) + Alembic-миграция** → проходит CLAUDE.md §3 (А3-спека → А4 → код).

**Помечено на приёмку:** для текущего среза модель НЕ меняется (правки нет; §5.2 не зависит от `row_version` и полностью самодостаточен). `row_version` — отдельная необязательная правка модели на Brain-дельту, применяется ТОЛЬКО при явном решении; иначе — §5.2 без колонки.

### 5.5 Маппинг исключений движка (`lesson_engine`) на HTTP

`lesson_engine.dispatch` поднимает типизированные ошибки (как auth.py мапит `RegistrationError`): сервис ловит и мапит в код. Маппинг:

| Исключение движка | Семантика | HTTP | `error` |
|-------------------|-----------|------|---------|
| `UnknownTransitionError` | для (`fsm_state`, derived evt) нет перехода — действие недопустимо в этом состоянии (например `advance` в `daily_blocked`) | **409** | `wrong_action_for_stage` |
| `GuardError` | переходы есть, но ни один guard не прошёл (например `evt_start_lesson` при `has_next_lesson=false` — но это сервер деривит в `evt_no_lesson_today`, см. §1.3; реальный GuardError = рассинхрон контекста, в т.ч. инкремент счётчика ДО dispatch — §2.2-bis, R1-№3) | **409** | `guard_failed` |
| `AmbiguousTransitionError` | несколько переходов подошло — ДЕФЕКТ таблицы (гарды пересеклись) | **500** | `fsm_internal_error` (лог + алерт фаундеру; F-уровень) |
| `InvalidCSVError` (csv_loader) | контент урока не загрузился (EC-08/F-03) | **503** | `lesson_content_unavailable` (safe fallback theory, §3.5) |

> `AmbiguousTransitionError` — единственный 500: это внутренний дефект, не ошибка клиента. `UnknownTransitionError`/`GuardError` от КЛИЕНТСКОГО действия не в той стадии — 409 (конфликт состояния), а не 422 (тело валидно, конфликтует состояние). Это симметрично reg api §5 «409 — конкурентный/состоянийный конфликт».
> **Анти-паттерн для кодера (R1-№3):** `guard_failed` от `main_question_attempts` чаще всего означает, что сервис инкрементил счётчик ДО `dispatch` (нарушение §2.2-bis). Гард ждёт значение ДО инкремента; инкремент — side-effect движка ПОСЛЕ. Не «чинить» это сдвигом гарда — чинить порядком вызова.

---

## 6. Граница HTTP vs scheduler (какие события endpoints выставляют, какие серверно-внутренние)

Источник: v4 §8 контракт `scheduler → fsm_service` — scheduler вызывает fsm_service «через внутренний API, не через HTTP». Аддендум очерчивает разделение для этого среза.

| Событие v4 | Кто выставляет | Транспорт | Endpoint (если HTTP) |
|------------|----------------|-----------|----------------------|
| `evt_open_app` | КЛИЕНТ | HTTP | E5 `POST /api/day/open` |
| `evt_warmup_available`/`evt_warmup_skip` | КЛИЕНТ | HTTP | E6 `POST /api/day/warmup` (`start`/`skip`) |
| `evt_warmup_complete` | **СЕРВЕР деривит** (исчерпание 3 R3-вопросов разминки ИЛИ skip внутри разминки, §2.5) | HTTP-ответ E6 (на последнем `answer`/на `skip`) | E6 (сервер диспатчит в обработке E6, клиент `complete` не шлёт) |
| `evt_start_lesson`/`evt_no_lesson_today`/`evt_all_lessons_done` | КЛИЕНТ (триггер) → сервер деривит исход по манифесту | HTTP | E8 `POST /api/lesson/start` |
| `evt_hook_read`/`evt_theory_read`/`evt_example_read`/`evt_theory_reviewed`/`evt_lesson_complete`/`evt_lesson_fail_confirmed` | КЛИЕНТ (action=advance) → сервер деривит evt по stage | HTTP | E9 `POST /api/lesson/advance` |
| `evt_answer_correct`/`evt_answer_wrong`/`evt_training_max_errors`/`evt_main_*` | КЛИЕНТ (буква) → **сервер судит и деривит evt** (§2) | HTTP | E10 `POST /api/lesson/answer` |
| `evt_cancel_lesson` | КЛИЕНТ | HTTP | E11 `POST /api/lesson/cancel` |
| `evt_repeat_1h_answered`/`evt_repeat_evening_answered` | КЛИЕНТ (буква) → сервер судит для feedback, диспатчит по факту | HTTP | E12 `POST /api/repeat/answer` |
| `evt_session_end` (**R1-№1**) | **СЕРВЕР деривит** при следующем заходе из `review_queue_scheduled`/`daily_done` (E4 `GET /api/day`) | HTTP-чтение E4 (lazy, при заходе) — НЕ клиентское событие | E4 `GET /api/day` (см. ниже) |
| `evt_1h_elapsed` | **SCHEDULER** | внутренний API (не HTTP) | — (scheduler.py → fsm_service; v4 §8) |
| `evt_evening_time` | **SCHEDULER** | внутренний API | — |
| `evt_day_end` | **SCHEDULER** (23:59 job) | внутренний API | — |
| `evt_next_day` | **SCHEDULER** | внутренний API | — |
| `evt_streak_updated` | **СЕРВЕР внутренне** (синхронно в `streak_update`; пользователь не взаимодействует, v4 §2б) | внутренний | — |

**Принцип границы:** endpoints выставляют ТОЛЬКО события, инициируемые ДЕЙСТВИЕМ ученика (advance/answer/cancel/open/warmup). Все ВРЕМЕННЫЕ/системные события (`evt_1h_elapsed`, `evt_evening_time`, `evt_day_end`, `evt_next_day`) и синхронный `evt_streak_updated` — серверно-внутренние (scheduler/fsm_service), HTTP их НЕ принимает. Клиент не может прислать `evt_day_end` или «промотать время» — это анти-подмена темпа (CLAUDE.md §6; Methodology §1.3 — нет искусственного удержания, но и нет обхода интервалов).

### 6.1 `evt_session_end` — деривируется сервером при заходе из тупиков дня (R1-№1)

В v4 §2б два перехода ведут обратно в `registered` по `evt_session_end`:
- `review_queue_scheduled --evt_session_end--> registered` (после R2/планирования интервальных повторений);
- `daily_done --evt_session_end--> registered` (день закрыт, новых уроков нет).

В исходнике v1 это событие не было классифицировано (ни scheduler, ни HTTP, ни «сервер внутренне») — формальный тупик HTTP-слоя: ученик в `review_queue_scheduled`/`daily_done` не имел транспорта возврата в `registered`. Классификация (без изменения FSM):

- **`evt_session_end` — НЕ клиентское и НЕ временно-scheduler-событие.** Оно семантически означает «эта дневная сессия завершена; при следующем обращении ученик стартует с чистого `registered`». Это **ленивая серверная деривация при ближайшем чтении состояния дня (E4 `GET /api/day`)**: сервер, увидев `fsm_state ∈ {review_queue_scheduled, daily_done}` на входе в E4, синхронно диспатчит `evt_session_end → registered` (нормализация состояния), затем отрабатывает `evt_open_app`-эквивалент чтения дня и отдаёт day_hub текущего дня. Для клиента это один ответ E4 (day_hub) — двойной внутренний переход скрыт, симметрично отложенному `streak_update` в E5 (§7, «двойной внутренний переход — серверный»).
- **Почему именно так, а не scheduler:** `evt_session_end` не привязано ко времени (в отличие от `evt_next_day`/`evt_day_end`, которые сбрасывают день в полночь и делает scheduler). Оно — про «сессию закрыли», и естественный момент его применения — следующий заход ученика. Если же день уже сменился раньше захода, scheduler-овский `evt_next_day` (`daily_done --evt_next_day--> registered`) уведёт из `daily_done` независимо; для `review_queue_scheduled` ветки `evt_next_day` в v4 нет, поэтому именно lazy-`evt_session_end` на E4 — единственный корректный транспорт возврата из `review_queue_scheduled` в `registered`. Это закрывает тупик (R1-№1) ровно одним механизмом.
- **Альтернатива, помеченная для А4:** если архитектурно предпочтительнее, `evt_session_end` может выставляться тем же scheduler-job, что и `evt_day_end` (ночная нормализация всех «висящих» дневных состояний в `registered`). Тогда E4 при заходе уже видит `registered`. Оба варианта НЕ меняют FSM v4; выбор реализации (lazy-on-E4 vs nightly-job) — транспортный, не продуктовый; дефолт спеки — **lazy-on-E4** (немедленно разблокирует возврат, не ждёт полуночи). Помечено как транспортная развилка реализации, не блокер.
  > **R2-№3 — `daily_blocked` ИСКЛЮЧЁН из множества session_end-нормализуемых состояний.** В альтернативе nightly-job (как и в lazy-on-E4) множество нормализуемых по `evt_session_end` состояний — РОВНО `{review_queue_scheduled, daily_done}` и НИЧЕГО больше. `daily_blocked` **НЕ нормализуется** через `evt_session_end` ни на E4, ни в nightly-job: в v4 §2б у `daily_blocked` НЕТ перехода по `evt_session_end`. Его единственный выход — `daily_blocked --evt_next_day--> registered` (scheduler, смена дня) плюс самопетля `daily_blocked --evt_open_app-->` (E4-read, показывает `SHOW_BLOCKED_MESSAGE`, dest==src). То есть ученик, проваливший урок сегодня (`daily_blocked`), остаётся заблокированным ДО смены дня по scheduler — это намеренно (v4: «провал → доступно завтра»), и ни E4-нормализация, ни nightly-session_end-job не имеют права вывести его из `daily_blocked` раньше `evt_next_day`. Кодер, реализуя нормализацию (lazy или nightly), берёт целевое множество = `{review_queue_scheduled, daily_done}`; попытка диспатчить `evt_session_end` из `daily_blocked` → `UnknownTransitionError` (нет перехода) → это БАГ нормализации, не валидный путь. FSM не допускает session_end из `daily_blocked`.

**Самопетли при входе в pending-состояния** (`repeat_1h_pending`/`repeat_evening_active`/`daily_blocked` + `evt_open_app`) — это `GET /api/day` (E4, read), показывающий countdown/prompt/blocked-сообщение; FSM не двигается (dest==src), реальный сдвиг (`evt_1h_elapsed`/`evt_evening_time`) делает scheduler. Клиент НЕ может «активировать» R1 раньше времени через HTTP. *Отличие от `review_queue_scheduled`/`daily_done`:* там E4 НЕ самопетля (нет `*_pending + evt_open_app` самопетли в v4), а нормализующий `evt_session_end → registered` (выше). *`daily_blocked` — именно самопетля (read-only), НЕ нормализуемое состояние (R2-№3): выход только по `evt_next_day` (scheduler).*

> **Отложенный streak (`missed_day_end`, v4 §2):** E5 (`evt_open_app`) при `DailySession.missed_day_end=true` ведёт `registered --> streak_update` (не сразу в daily_start). Сервер синхронно отрабатывает `evt_streak_updated` (внутренне) → `registered`, затем повторно применяет `evt_open_app --> daily_start` и отдаёт day_hub. Клиент видит один ответ E5 (day_hub); двойной внутренний переход — серверный, по v4 §2 «при следующем evt_open_app из registered fsm_service немедленно генерирует evt_day_end перед переходом в daily_start». Аддендум это лишь биндит на E5, не меняет.

---

## 7. Стыковка с registration_api и v4 (границы охвата)

- **ВХОД:** `student_registration_api_v1.md` E3 → `next: daily_start`, `fsm_state: registered`, непустой `current_lesson_id`. Этот аддендум начинается с E5 (`evt_open_app`). Никакого дублирования регистрации.
- **`current_lesson_id`** на входе = `COURSE_MANIFEST[0]` (= `config.FIRST_LESSON_ID="1_1"`) для нового ученика; далее сдвигается по `next_unpassed_lesson` (§3.3) после каждого `record_lesson_passed`.
- **Удаление аккаунта / logout** (`evt_delete_account`, `session_own/delete`) — v4 §8 + reg api, вне дневного потока; здесь не дублируются.
- **`evt_open_pwa` vs `evt_open_app` (различены, R1-№5):** `evt_open_pwa` (`unregistered --evt_open_pwa--> onboarding`, lesson_engine `OPEN_PWA`) — вход НЕзарегистрированного в онбординг; он зона `student_registration_api_v1.md`, в дневном потоке НЕ выставляется (из `registered` он недостижим — нет перехода `registered --evt_open_pwa-->`). `evt_open_app` (`registered --evt_open_app--> daily_start`, lesson_engine `OPEN_APP`) — вход ЗАрегистрированного в день, это E5. Два разных события, два разных эндпоинта (reg vs day); путаницы нет — сервер выбирает по `fsm_state` (unregistered → reg-флоу; registered → E5).
- **Привязки взрослых, push-токен** — отдельные эндпоинты (`push.py`, links), вне этого среза.

---

## 8. Ссылочная карта «HTTP-действие ↔ событие/состояние v4» (не переопределяет FSM)

Карта для ревью А4 — показывает, что транспорт не вводит новых переходов, а биндится на v4 §2б / `lesson_engine.py`. **Покрывает ВСЕ `evt_*` v4 ученика** (либо HTTP, либо scheduler, либо «сервер внутренне», либо «вне охвата с причиной»).

| Endpoint + action | Деривированное `evt_*` (сервер) | Переход (v4 §2б) | Источник истины |
|-------------------|----------------------------------|-------------------|------------------|
| E5 `/day/open` | `evt_open_app` | `registered → daily_start` (или `→ streak_update` при missed_day_end) | v4 §2б |
| E6 `/day/warmup` start/skip | `evt_warmup_available`/`evt_warmup_skip` | `daily_start → morning_warmup`/`→ lesson_select` | v4 §2б |
| E6 `/day/warmup` answer (R3) | — (judge-only, нет evt; §2.5) | dest==src `morning_warmup`, пока есть R3-вопросы | §2.5 |
| E6 `/day/warmup` (исчерпание/skip) | `evt_warmup_complete` (**сервер деривит**, §2.5) | `morning_warmup → lesson_select` | v4 §2б; §2.5 |
| E8 `/lesson/start` | `evt_start_lesson` / `evt_no_lesson_today` / `evt_all_lessons_done` (по манифесту) | `lesson_select → lesson_hook`/`daily_done`/`daily_blocked`/`course_complete` | v4 §2б |
| E9 `/lesson/advance` (по stage) | `evt_hook_read`/`evt_theory_read`/`evt_example_read`/`evt_theory_reviewed`/`evt_lesson_complete`/`evt_lesson_fail_confirmed` | соответствующие lesson-переходы | v4 §2б; §1.3 |
| E10 `/lesson/answer` (судейство) | `evt_answer_correct`/`evt_answer_wrong`/`evt_training_max_errors`/`evt_main_correct_attempt1`/`evt_main_wrong_attempt1`/`evt_main_correct_attempt2`/`evt_main_wrong_attempt2` | training/main-переходы | v4 §2б; §2.3 |
| E11 `/lesson/cancel` | `evt_cancel_lesson` | `lesson_* → registered` (прогресс сохранён) | v4 §2б |
| E12 `/repeat/answer` | `evt_repeat_1h_answered`/`evt_repeat_evening_answered` | `repeat_1h_active → repeat_evening_pending`; `repeat_evening_active → review_queue_scheduled` | v4 §2б |
| E4 `/day` (read) | — (самопетли показывают `SHOW_R1_COUNTDOWN`/`SHOW_EVENING_PROMPT`/`SHOW_BLOCKED_MESSAGE`) | dest==src; не двигает FSM | v4 §2б |
| E4 `/day` (нормализация тупика дня, **R1-№1/№5; R2-№3**) | `evt_session_end` (**сервер деривит lazy при заходе из `review_queue_scheduled`/`daily_done`**; `daily_blocked` ИСКЛЮЧЁН — §6.1) | `review_queue_scheduled → registered`; `daily_done → registered` | v4 §2б; §6.1 |
| (scheduler, не HTTP) | `evt_1h_elapsed`/`evt_evening_time`/`evt_day_end`/`evt_next_day` (в т.ч. `daily_blocked --evt_next_day--> registered` — единственный выход из blocked, R2-№3) | временные переходы | v4 §8; §7 |
| (сервер внутренне) | `evt_streak_updated` | `streak_update → registered` | v4 §2б; §6 |
| (вне охвата — регистрация, `evt_open_pwa` различён с `evt_open_app`, R1-№5) | `evt_open_pwa`/`evt_submit_registration`/`evt_cancel_registration` | `unregistered → onboarding → registered` | `student_registration_api_v1.md`; v4 §2б |
| (вне охвата — auth/account_service) | `evt_delete_account` | `* → unregistered` (каскадное удаление ПД) | v4 §8; reg api |

> Все события `evt_*` и их guards — дословно как в v4 §2б / `lesson_engine.py`. Аддендум их не меняет; он лишь говорит, КАКОЙ HTTP-вызов их инициирует и КАК сервер деривит событие из действия+stage (анти-подмена). После R1 карта покрывает ВСЕ `evt_*` ученика: HTTP (E5–E12), сервер-деривит (`evt_warmup_complete`, `evt_session_end`), scheduler (4 временных), сервер-внутренне (`evt_streak_updated`), вне охвата (регистрация/auth — с явной причиной). Тупиков HTTP-возврата нет.

---

## 9. Самопроверка перед выдачей

- [x] Не переоткрыты FSM/матрица прав/сценарии/edge/failure v4 — только HTTP-биндинг. FSM-YAML и permissions-YAML НЕ дублированы (намеренно, §0); validator.py по этому документу неприменим — ожидаемо, не дефект. **R1: несущие контракты v4 §2б/§3б и `lesson_engine.py` (события/гарды/side-effects/матрица прав/инвариант атомарности) НЕ тронуты ни одной из 7 правок. R2: пять правок R2 (№1–№5) — тоже чисто транспортные/контракт-данных-на-приёмку; FSM-YAML не введён, несущие контракты v4 НЕ тронуты.**
- [x] **(п.1)** Набор endpoints E4–E12 под дневной поток + урок + R1/R2; ссылочный маппинг «HTTP→evt» (§1.3, §8). Единая кнопка «Дальше» (E9) → разные evt по stage — сервер деривит по `fsm_state`, клиент шлёт только `action:advance` (§1.3).
- [x] **(п.2)** Серверное судейство (§2): клиент шлёт букву A–D + message_id; сервер сверяет с `correct_answer` CSV, деривит is_correct/feedback_X/return_X/целевое evt (§2.2, §2.3); семантические evt от клиента НЕ принимаются (§2.4). Соответствует v4 §3 `progress_own/write` «только через FSM». **R1-№3:** порядок «гард ДО инкремента» зафиксирован (§2.2-bis): счётчик в `ctx` — ДО инкремента, инкремент — side-effect движка; убраны «(станет 2)/(станет 1)».
- [x] **(п.3)** Схемы request/response + общий render-payload (§4). **R1-№6:** «wrong с возвратом» сведён к единому `view: "lesson_feedback"` (feedback+message в одном payload; различие training/main-wrong#1 — по `fsm_state`); §4.5/§4.9 согласованы. **R1-№7:** `streak_days` помечен как ОПЦИОНАЛЬНЫЙ тихий показ (F-1, A8 `day.counter.badge`); сервер не предписывает заметность. **R2-№5:** зафиксирован дефолт клиента ДО решения по F-1 — тихий/скрытый показ (fail-safe в сторону Methodology §1.3 «без давления»), а не заметный счётчик (§4.1, ремарка про `streak_days`).
- [x] **(п.4а)** Секвенирование внутри урока (§3.1); `training_remaining` и автопереход `training→main_question` (§3.2). **(п.4б)** Манифест курса (§3.3); `COURSE_MANIFEST` в config.py — правка контракта данных на приёмку (§3.4); отвергнут вывод из имён файлов. Не ORM-миграция. **R2-№1:** §3.4-bis — требование ЕДИНОГО пространства `lesson_id` для COURSE_MANIFEST / Progress.lesson_id / ключа контента csv_loader; зафиксирован рассинхрон (csv_loader ключует по имени файла; col3 `lesson_id="1"` на весь блок; 9 файлов вместо 27); предложен интерфейс (I) ключевание load_lessons_dir по col3 ИЛИ (II) `lesson_messages(lesson_id)`; помечено ЧЕСТНО как КОНТЕНТНЫЙ блокер (keeper.py/контент-продюсер + приёмка фаундера), НЕ код; конкретные 27 id НЕ выдуманы.
- [x] **(п.2 / R3-разминка, R1-№2)** `morning_warmup` доопределена (§2.5): R3-ответ через E6 `answer` судится для feedback, FSM-событие НЕ диспатчит; серверный счётчик 3 вопросов; `evt_warmup_complete` — серверная деривация по исчерпании/skip. Стадия `repeat_morning`. Без изменения FSM. **R2-№2:** skip-внутри-разминки НЕ помечает невыданные/неотвеченные R3-вопросы как `done` — их `due_date` сохраняется (всплывут снова); засчитывается только фактически отвеченный R3-вопрос; согласовано с EC-19; помечено на сверку с `review_service` (§2.5).
- [x] **(п.5)** Конкурентность: дедуп через sequence-эхо + сверку позиции БЕЗ новой колонки (§5.2) — основной механизм. **R1-№4:** E9 `advance` (без `message_id`) сверяется по позиционному курсору `(stage, индекс сообщения в стадии)` — добавлена ветвь (б) §5.2; идемпотентность/409 для нон-вопросных шагов определены. **R2-№4:** уточнена семантика `seq` — `seq++` на КАЖДОМ принятом command (включая wrong-возврат по `return_X` и внутри-стадийный advance-шаг), даже если позиционный курсор откатывается назад по `message_id`; это снимает неоднозначность дедупа после `return_X` (легитимный пост-возвратный повтор имеет больший `seq` и не путается с устаревшим дублем) (§5.2). EC-01/EC-03/F-07 (§5.3). `Progress.row_version` — **опциональная правка модели**, по умолчанию НЕ применяется (§5.4). Конвенция кодов (§5.1); маппинг исключений (§5.5).
- [x] **(п.6)** Граница HTTP vs scheduler (§6): endpoints выставляют только действия ученика; временные события — scheduler; `evt_streak_updated` — сервер внутренне. **R1-№1:** `evt_session_end` классифицирован (§6.1) — серверная lazy-деривация на E4 при заходе из `review_queue_scheduled`/`daily_done`; тупик HTTP-возврата устранён. **R2-№3:** `daily_blocked` ЯВНО ИСКЛЮЧЁН из множества session_end-нормализуемых состояний (§6.1) — нормализуются только `review_queue_scheduled`/`daily_done`; `daily_blocked` выходит ИСКЛЮЧИТЕЛЬНО по `evt_next_day` (scheduler) + самопетля; FSM не допускает session_end из него (попытка → `UnknownTransitionError` = баг нормализации). **R1-№5:** карта §8 дополнена `evt_session_end` + `evt_warmup_complete`; `evt_open_pwa` vs `evt_open_app` различены (§7); карта покрывает ВСЕ `evt_*` v4.
- [x] Стыковка с reg api (`next:daily_start`, current_lesson_id=FIRST_LESSON_ID) и v4 (§7). Удаление/logout/привязки — вне охвата, не дублированы.
- [x] **Правки на приёмку фаундеру/Brain-дельту:** (1) `COURSE_MANIFEST` в config.py — добавление конфиг-константы (§3.4); (1-bis, R2-№1) единое пространство `lesson_id` для COURSE_MANIFEST/Progress/контента + выбор интерфейса (I/II) — правка §3-контракта данных; приведение контента к уникальному `lesson_id` и к 27 урокам — зона keeper.py/контента, КОНТЕНТНЫЙ блокер (§3.4-bis); (2) опционально `Progress.row_version` — только если приёмка требует строгий optimistic lock (§5.4, по умолчанию не применяется). §3-контракт данных, помечены явно; models.py commit ae6e765 в базовом варианте НЕ меняется.
- [x] Нерешённых ПРОДУКТОВЫХ развилок аддендум не создаёт; §3.6 (рандомизация backup-формулировки, календарное расписание), §6.1-альтернатива (lazy-on-E4 vs nightly-job для `evt_session_end`; `daily_blocked` исключён в обоих, R2-№3), §2.5-skip-трактовка — НЕ блокеры, дефолты безопасны и не противоречат Методологии; помечены для сверки А4. F-1 (заметность streak) — продуктовая развилка фаундера; аддендум лишь даёт fail-safe-дефолт «тихо» (R2-№5), не закрывает её.

---

*Аддендум v1 (ревизии R1 + R2, 2026-06-22) — транспортный HTTP-биндинг дневного потока и прохождения урока (R1/R2 включены) поверх принятой `specs/student_lesson_fsm_v4.md` (validator PASS, А4 GO) и `lesson_engine.py`. Стыкуется с `specs/student_registration_api_v1.md` через `next:daily_start`. Не меняет события evt_*, guards, side-effects, deny-by-default матрицы прав v4, инвариант «fsm_state — канонический источник, обновляется атомарно с Progress». Серверное судейство ответа (анти-подмена, §2), порядок «гард до инкремента» (§2.2-bis), R3-разминка + skip-не-сжигает-due (§2.5), секвенирование внутри урока (§3.1), момент автоперехода (§3.2), манифест курса (§3.3) + единое пространство lesson_id (§3.4-bis), дедуп переходов через sequence-эхо без новой колонки — включая ветвь E9 по позиционному курсору и `seq++` на каждый command (§5.2), конвенция кодов и маппинг исключений движка (§5), граница scheduler + `evt_session_end` (`daily_blocked` исключён, §6/§6.1) — транспортно-архитектурные решения, обоснованы. ПРАВКИ КОНТРАКТА ДАННЫХ НА ПРИЁМКУ: COURSE_MANIFEST в config.py (§3.4, обязательна для guard'ов lesson_select) + единое пространство lesson_id / интерфейс csv_loader (§3.4-bis, R2-№1, включает КОНТЕНТНЫЙ блокер на стороне keeper.py/контента); Progress.row_version (§5.4, опциональна, по умолчанию НЕ применяется). Проверяют: А4 + validator.py.*
