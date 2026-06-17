# Спека: Регистрация ученика в PWA (фаза onboarding)

**Версия:** v2
**Дата:** 2026-06-17
**Автор:** Агент 3 (Архитектор системы)
**Источники:** Methodology v2.1 (§1.4) > Project Brain v3.2 (Журнал решений 2026-06-17) > specs/student_lesson_fsm_v4.md
**Область:** регистрация ученика end-to-end — детализация фазы `onboarding` между `unregistered` и `registered` (со стыковкой в первый урок). Прохождение урока, повторения, mastery — вне охвата (см. v4).
**Стыковка:** этот документ ДЕТАЛИЗИРУЕТ переход `unregistered → onboarding → registered` из v4 (§2). Контракт v4 не ломается: имена сущностей (User, StudentProfile, Session, Consent-атрибуты), событие `evt_submit_registration` и конвенция `evt_*` сохранены. Внутри `onboarding` вводятся под-состояния, невидимые для FSM верхнего уровня v4: для v4 вся регистрация остаётся одним переходом `onboarding → registered`.
**Проверяют:** Агент 4 (Критик системы) + validator.py

**Исправлено по ревью А4 v1:** №1 (консистентность имён ресурсов с v4 + маппинг), №2 (идемпотентность submit = idempotency-key по сессии онбординга, убрана опора на `unique(name, created_at)`), №3 (самооценка grade=9 — UI-информер вне FSM, инвариант приведён в соответствие, вариант (а)), №4 (Z-1 — механизм аудита когорты grade=9 + обратимость), №6 (policy_version_shown перечитывается при повторном входе в consent_gate), №7 (ремарка: `ogeprep_answer` = null by design для grade=9). №5 (gate_grade8) — правка не требуется, оставлено как есть.

---

## 0. Открытые развилки и зависимости (решает фаундер / юрист)

| # | Развилка / зависимость | Статус | Почему важно |
|---|------------------------|--------|--------------|
| D-6 | grade=8 → возраст <14 → согласие на ПД даёт законный представитель (152-ФЗ ст.9 ч.1). | **Закрыта продуктово в этой задаче через жёсткий гейт.** В production guard регистрации = `grade IN (9,10,11)`. grade=8 в production вообще не создаёт активный аккаунт ученика курса (жёсткий гейт, экран «возвращайся в сентябре»). Полная поддержка grade=8 с согласием представителя — НЕ в этой спеке. | Закрывает D-6 на уровне продукта: курс не работает с заведомо <14-летними. |
| Z-1 | **Форма согласия законного представителя для лиц <14 лет — ОТЛОЖЕНА (юр-проверка).** | **Незакрытая зависимость, НЕ блокирует эту спеку, но требует механизма обратимости (см. §6 RF-08).** Опора: grade=8 закрыт жёстким гейтом; grade≥9 ≈ 14–15 лет, где согласие даёт сам субъект. Если юрист установит, что часть grade=9 моложе 14 — потребуется отдельная ветка согласия представителя; в текущей FSM её нет. Чтобы негативное юр-заключение НЕ оказалось необратимым задним числом, спека вводит механизм идентификации когорты (см. §1, RF-08). | До юр-заключения нельзя гарантировать, что 100% grade=9 ≥14 лет. Риск приниматься фаундером осознанно, но обратимо. |
| Z-2 | Версия и текст Политики обработки ПД (`pd_consent_version`). | Незакрыта (контент/юр). НЕ блокирует FSM: спека фиксирует МЕХАНИЗМ (ссылка + обязательный чекбокс + запись `pd_consent_at`/`pd_consent_version`), не текст. | Текст политики — зона юриста/А8, не архитектора. |
| D-1 | Смена имени/класса после регистрации (наследие v4). | Остаётся открытой; в этой спеке регистрация только СОЗДАЁТ профиль. `write` по профилю — deny (как в v4). | Не относится к onboarding напрямую. |

> Продуктовые решения по полям, порядку, ветке-по-классу, экрану «курс не подходит» и согласию ПД — **утверждены фаундером (разбор А9, 2026-06-17)** и здесь НЕ переоткрываются.

---

## 1. Словарь сущностей

Сущности консистентны с v4. Новые/уточнённые атрибуты для onboarding помечены **(new)**.

### Маппинг имён ресурсов на v4 (правка №1)

Чтобы матрица прав §3 не расходилась с принятой спекой v4, ресурсы этой спеки приведены к именам v4 там, где это тот же объект. Соответствие:

| Ресурс в этой спеке | Соответствие в v4 | Примечание |
|---------------------|-------------------|------------|
| `user_account_own` | `user_account_own` (v4) — операции delete; `user_profile_own` (v4) — операция read | `user_account` v1 переименован в `user_account_own`: это тот же объект — собственный аккаунт/профиль ученика. Создаётся регистрацией. read маппится на v4 `user_profile_own/read`, delete — на v4 `user_account_own/delete`, write — на v4 `user_profile_own/write` (deny, D-1). |
| `user_profile_other` | `user_profile_other` (v4) | Чужой аккаунт ученика (с точки зрения parent/teacher/tutor). В фазе регистрации — всё deny (привязки — отдельная задача). |
| `registration_draft` | **новый, нет в v4** | Существует только до `evt_submit_registration`. Не ПД в БД. Уничтожается на cancel/гейте/submit. |
| `pd_policy` | как в v4 (публичная политика ПД) | без изменений. |
| `session` | `session` (v4) | без изменений. |
| `lesson_content` | `lesson_content` (v4) | без изменений. |

### Таблица сущностей

| Сущность | Описание | Ключевые атрибуты | Связи |
|----------|----------|-------------------|-------|
| **User** | Аккаунт пользователя любой роли. Для онбординга — создаётся ТОЛЬКО при успешной регистрации (grade=9 или grade=10+ с подтверждением ОГЭ). | `id`, `role` (=student), `name` (никнейм/отображаемое имя; настоящее ФИО НЕ собирается), `grade` (9/10/11), `created_at`, `pwa_push_token` (null при регистрации), `pd_consent_at` (datetime — момент принятия политики ПД, обязателен), `pd_consent_version` (строка версии политики, обязательна), `consent_cohort_flag` **(new)**: bool/строка — помечает аккаунты grade=9, созданные ДО получения юр-заключения по Z-1; позволяет точечно идентифицировать когорту для запроса согласия представителя или удаления (см. RF-08) | 1:1 → StudentProfile |
| **StudentProfile** | Профиль ученика. На выходе регистрации `fsm_state=registered`, `current_lesson_id` = первый урок курса. | `user_id`, `current_lesson_id`, `course_started_at` (=now при регистрации), `last_active_at` (=now), `fsm_state` (=`registered`), `enrollment_reason` **(new)**: `grade9_direct` / `grade10plus_retake` — причина зачисления, для аналитики доходимости (не ПД) | 1:1 → User |
| **RegistrationDraft** **(new)** | Временное, НЕ персистентное состояние формы регистрации до отправки. Живёт только в памяти клиента + сессии онбординга на бэкенде; НЕ сохраняется как ПД в БД до `evt_submit_registration`. Несёт `onboarding_session_id` — основу идемпотентности submit (правка №2). | `onboarding_session_id` **(new)** (уникальный id сессии онбординга; служит idempotency-key для submit), `name_input`, `grade_input`, `ogeprep_answer` (для grade 10+: yes/no; для grade=9 — `null` by design, см. ремарку), `pd_consent_checked` (bool), `policy_version_shown` | — (не сохраняется при отмене/гейте; 152-ФЗ минимизация) |
| **Consent (атрибуты User)** | Не отдельная таблица — атрибуты `pd_consent_at` + `pd_consent_version` (+ `consent_cohort_flag`) на User (как в v4). Фиксируют согласие на обработку ПД. | см. User | embedded в User |
| **Session** | Сессионный токен аутентификации. Создаётся ТОЛЬКО при успешной регистрации. | `token` (httpOnly cookie, 256-bit random), `user_id`, `created_at`, `expires_at` (=created_at + 30 дней), `revoked` (bool) | N:1 → User |
| **Lesson** | Метаданные первого урока (читается из CSV). Только `read` для определения `current_lesson_id`. | `lesson_id` (без точек), `block_id`, `title` | — (см. v4) |

### Инварианты регистрации

- Регистрация собирает РОВНО: **никнейм (name)** + **класс (grade)** + **согласие на политику ПД**. Ничего больше (152-ФЗ минимизация). Никакого телефона/email/ФИО/даты рождения. Контакты и привязки взрослых — отдельная задача «после первого урока», НЕ здесь.
- `name` — отображаемое имя/ник, не верифицируется как настоящее ФИО и не должно им быть.
- **Без согласия на ПД (`pd_consent_checked=false`) регистрация не завершается** — `evt_submit_registration` отклоняется guard-ом; User не создаётся.
- `User`, `StudentProfile`, `Session` создаются АТОМАРНО в одной транзакции только в исходе `grade9_direct` или `grade10plus_retake`. До этого момента ПД в БД не пишутся.
- **Идемпотентность `evt_submit_registration` (правка №2):** единственный механизм — **idempotency-key = `onboarding_session_id`** из RegistrationDraft (сессия онбординга). Повторный submit с тем же `onboarding_session_id` возвращает уже созданный аккаунт (или 409 при гонке), новый User НЕ создаётся. **Опора на `unique(name, created_at)` УБРАНА** — `name` неуникальный ник, два «Ивана» в одну секунду давали бы ложную коллизию. Уникальный constraint — на `onboarding_session_id`, не на (name, created_at).
- **grade=8 (production): User НЕ создаётся.** Жёсткий гейт. Состояние `gate_grade8` — терминальный экран без активного аккаунта курса. RegistrationDraft уничтожается.
- **Экран «курс не подходит» (Methodology §1.4): информирующий, БЕЗ блокировки.** Достижим в FSM как состояние `course_mismatch` ТОЛЬКО из `ogeprep_check` (grade 10+, ответ «не готовлюсь к ОГЭ»). **Самооценка для grade=9** («целюсь на 4–5» / «за 2 недели» / «не освоил арифметику») — **чистый UI-информер без состояния FSM (правка №3, вариант (а))**: это опциональный экран/баннер, который не блокирует и не создаёт перехода. Решение «без блокировки» (§1.4) этим соблюдено: для grade=9 нет FSM-перехода в `course_mismatch`, что и заложено в FSM §2. Самооценка grade=9 НЕ является поведением FSM и более не упоминается в инварианте как FSM-достижимое состояние `course_mismatch`.
- **Ремарка по `ogeprep_answer` (правка №7):** атрибут релевантен ТОЛЬКО для `grade IN (10,11)` (заполняется в `ogeprep_check`). Для `grade=9` он остаётся `null` **by design** — ученик 9-го класса проходит прямой вход (`grade9_direct`) без уточнения про ОГЭ. Это ожидаемое значение, не пропуск данных.
- `policy_version_shown` записывается в `pd_consent_version` при отправке — фиксируем, какую именно версию политики ученик принял. **(правка №6)** При повторном входе в `consent_gate` (через `evt_back` и возврат) `policy_version_shown` **перечитывается заново** — фиксируется актуальная на момент повторного показа версия политики, а не закэшированная с первого входа. Это гарантирует, что `pd_consent_version` соответствует версии, которую ученик реально видел перед финальным submit.
- `enrollment_reason` — НЕ ПД (не идентифицирует личность); используется для метрик доходимости.
- `consent_cohort_flag` — НЕ ПД сам по себе; технический флаг для аудита когорты Z-1 (см. §6 RF-08).

---

## 2. Конечный автомат (FSM) — роль «ученик-регистрация»

Под-FSM фазы `onboarding`. `unregistered` — единственный start (стыковка с v4). Терминалы: `registered` (стык в v4 → первый урок), `unregistered` (отмена/гейт-выход), `gate_grade8` (жёсткий гейт, аккаунт курса не создан).

> Замечание о стыковке с v4: в v4 переход верхнего уровня `unregistered --evt_open_pwa--> onboarding --evt_submit_registration--> registered`. Здесь `onboarding` развёрнут. Финальный `evt_submit_registration` из под-состояния `consent_gate` соответствует ровно одному переходу v4 `onboarding → registered`. Прочие под-события (`evt_*`) — внутренние для onboarding и v4 не видны.

> **Правка №3 (вариант (а)):** `course_mismatch` достижим ТОЛЬКО из `ogeprep_check` (grade 10+). Самооценка grade=9 вынесена за пределы FSM как UI-информер без состояния — для неё НЕТ перехода и НЕТ состояния. FSM ниже отражает это: grade=9 → `consent_gate` напрямую.

### 2а. Mermaid-диаграмма

```mermaid
stateDiagram-v2
    [*] --> unregistered

    unregistered --> name_entry : evt_open_pwa

    name_entry --> grade_entry : evt_name_submitted [name непустое после trim]
    name_entry --> unregistered : evt_cancel_registration

    grade_entry --> gate_grade8 : evt_grade_selected [grade==8 AND env==production — жёсткий гейт]
    grade_entry --> consent_gate : evt_grade_selected [grade==9 — прямой вход, ogeprep_answer=null by design]
    grade_entry --> ogeprep_check : evt_grade_selected [grade IN (10,11)]
    grade_entry --> name_entry : evt_back
    grade_entry --> unregistered : evt_cancel_registration

    ogeprep_check --> consent_gate : evt_ogeprep_yes [готовится/пересдаёт ОГЭ]
    ogeprep_check --> course_mismatch : evt_ogeprep_no [курс не подходит — без блокировки]
    ogeprep_check --> grade_entry : evt_back
    ogeprep_check --> unregistered : evt_cancel_registration

    course_mismatch --> consent_gate : evt_mismatch_continue [ученик решил всё равно начать]
    course_mismatch --> unregistered : evt_mismatch_leave
    course_mismatch --> unregistered : evt_cancel_registration

    consent_gate --> registered : evt_submit_registration [name непустое AND grade IN (9,10,11) AND pd_consent_checked==true; idempotency по onboarding_session_id]
    consent_gate --> grade_entry : evt_back
    consent_gate --> unregistered : evt_cancel_registration

    gate_grade8 --> unregistered : evt_gate_dismiss [аккаунт курса не создан; draft уничтожен]

    registered --> [*]
    unregistered --> [*]
    gate_grade8 --> [*]

    %% evt_submit_registration возможно ТОЛЬКО из consent_gate (guard на pd_consent). В прочих состояниях — невозможно: согласие не подтверждено.
    %% course_mismatch достижим ТОЛЬКО из ogeprep_check (grade 10+). Самооценка grade=9 — UI-информер вне FSM (правка №3, вариант а), перехода в course_mismatch для grade=9 НЕТ.
    %% При повторном входе в consent_gate (через evt_back и возврат) policy_version_shown перечитывается заново (правка №6).
```

### 2б. YAML-блок для validator.py

```yaml
role: student_registration
states:
  - id: unregistered
    type: start
  - id: name_entry
    type: normal
  - id: grade_entry
    type: normal
  - id: ogeprep_check
    type: normal
  - id: course_mismatch
    type: normal
  - id: consent_gate
    type: normal
  - id: gate_grade8
    type: normal
  - id: registered
    type: end
    # registered — end данного под-FSM; в v4 это normal-state, точка стыковки (далее daily_start / первый урок)

events:
  - id: evt_open_pwa
  - id: evt_name_submitted
  - id: evt_grade_selected
  - id: evt_ogeprep_yes
  - id: evt_ogeprep_no
  - id: evt_mismatch_continue
  - id: evt_mismatch_leave
  - id: evt_submit_registration
  - id: evt_back
  - id: evt_cancel_registration
  - id: evt_gate_dismiss

transitions:
  # --- Вход ---
  - from: unregistered
    event: evt_open_pwa
    to: name_entry
    guard: "первый вход в PWA; создаётся RegistrationDraft (с уникальным onboarding_session_id) в памяти/сессии онбординга (не БД)"

  # --- Имя ---
  - from: name_entry
    event: evt_name_submitted
    to: grade_entry
    guard: "name непустое после trim (>=1 непробельный символ); сохраняется в RegistrationDraft.name_input"

  - from: name_entry
    event: evt_cancel_registration
    to: unregistered
    guard: "RegistrationDraft уничтожен; ПД не записаны"

  # --- Класс / ветка по классу ---
  - from: grade_entry
    event: evt_grade_selected
    to: gate_grade8
    guard: "grade==8 AND env==production — ЖЁСТКИЙ ГЕЙТ; User НЕ создаётся; D-6 закрыта"

  - from: grade_entry
    event: evt_grade_selected
    to: consent_gate
    guard: "grade==9 — прямой вход (enrollment_reason=grade9_direct); ogeprep_answer остаётся null by design; самооценка grade=9 — UI-информер вне FSM"

  - from: grade_entry
    event: evt_grade_selected
    to: ogeprep_check
    guard: "grade IN (10,11) — требуется уточнение про ОГЭ/пересдачу"

  - from: grade_entry
    event: evt_back
    to: name_entry
    guard: "вернуться к вводу имени; RegistrationDraft.name_input сохранён в сессии онбординга"

  - from: grade_entry
    event: evt_cancel_registration
    to: unregistered
    guard: "RegistrationDraft уничтожен"

  # --- Уточнение ОГЭ (grade 10+) ---
  - from: ogeprep_check
    event: evt_ogeprep_yes
    to: consent_gate
    guard: "готовится к ОГЭ / пересдаёт — впуск как пересдача (enrollment_reason=grade10plus_retake); ogeprep_answer=yes"

  - from: ogeprep_check
    event: evt_ogeprep_no
    to: course_mismatch
    guard: "не готовится к ОГЭ — показать экран «курс не подходит» (Methodology §1.4), БЕЗ блокировки; ogeprep_answer=no. ЕДИНСТВЕННЫЙ вход в course_mismatch (grade 10+)"

  - from: ogeprep_check
    event: evt_back
    to: grade_entry
    guard: "вернуться к выбору класса"

  - from: ogeprep_check
    event: evt_cancel_registration
    to: unregistered
    guard: "RegistrationDraft уничтожен"

  # --- Экран «курс не подходит» (информирующий, не блокирующий) ---
  - from: course_mismatch
    event: evt_mismatch_continue
    to: consent_gate
    guard: "ученик решил всё равно начать — Methodology §1.4 запрещает блокировку (кроме grade=8 гейта); enrollment_reason=grade10plus_retake"

  - from: course_mismatch
    event: evt_mismatch_leave
    to: unregistered
    guard: "ученик ушёл по своему решению; RegistrationDraft уничтожен; User не создан"

  - from: course_mismatch
    event: evt_cancel_registration
    to: unregistered
    guard: "RegistrationDraft уничтожен"

  # --- Согласие ПД + создание аккаунта ---
  - from: consent_gate
    event: evt_submit_registration
    to: registered
    guard: "name непустое AND grade IN (9,10,11) AND pd_consent_checked==true; идемпотентность по onboarding_session_id (повторный submit того же ключа не создаёт второй аккаунт). При входе в consent_gate policy_version_shown перечитывается заново. side-effect (одна транзакция): создать User(role=student, name, grade, pd_consent_at=now, pd_consent_version=policy_version_shown, consent_cohort_flag установлен если grade==9 AND Z-1 не закрыта), StudentProfile(fsm_state=registered, current_lesson_id=первый урок, course_started_at=now, last_active_at=now, enrollment_reason), Session(httpOnly cookie, 30 дней); установить cookie; в v4 далее daily_start → первый урок"

  - from: consent_gate
    event: evt_back
    to: grade_entry
    guard: "вернуться к выбору класса (например, передумал про класс); согласие сбрасывается в draft; при повторном входе в consent_gate policy_version_shown перечитывается заново (правка №6)"

  - from: consent_gate
    event: evt_cancel_registration
    to: unregistered
    guard: "RegistrationDraft уничтожен; User не создан"

  # --- Жёсткий гейт grade=8 ---
  - from: gate_grade8
    event: evt_gate_dismiss
    to: unregistered
    guard: "тёплый экран «возвращайся в сентябре 9-го» показан; активный аккаунт ученика курса НЕ создан; RegistrationDraft уничтожен; ПД не записаны"

# Комментарии по необработанным / невозможным событиям:
# evt_open_pwa в любом состоянии кроме unregistered: невозможно — онбординг уже начат (draft существует)
# evt_submit_registration вне consent_gate: невозможно — pd_consent не подтверждён без прохождения consent_gate (guard 152-ФЗ); регистрация без согласия запрещена инвариантом
# evt_ogeprep_yes/evt_ogeprep_no вне ogeprep_check: невозможно — уточнение ОГЭ задаётся только для grade IN (10,11); для grade=9 ogeprep_answer=null by design
# evt_grade_selected вне grade_entry: невозможно — класс выбирается ровно на одном экране
# evt_gate_dismiss вне gate_grade8: невозможно — гейт-экран существует только в gate_grade8
# evt_mismatch_continue/evt_mismatch_leave вне course_mismatch: невозможно — экран «не подходит» только в course_mismatch (достижим лишь из ogeprep_check, grade 10+)
# evt_back из name_entry: невозможно — это первый шаг формы; отступ назад = evt_cancel_registration → unregistered
# Согласие законного представителя (<14, Z-1) в FSM НЕ моделируется — отложенная зависимость (юр-проверка); когорта grade=9 помечается consent_cohort_flag для обратимости (RF-08)
```

---

## 3. Матрица прав

Deny by default. Покрыты ресурсы, релевантные регистрации. Роли parent/teacher/tutor в фазе регистрации ученика не участвуют (контакты/привязки — отдельная задача), для них всё — deny. Прочие ресурсы ученика (progress, streak, review_queue и т.д.) определены в v4 и здесь не дублируются.

> **Правка №1:** ресурс `user_account` v1 приведён к имени v4 — `user_account_own` (тот же объект: собственный аккаунт/профиль ученика). См. маппинг в §1. read маппится на v4 `user_profile_own/read`, delete — на v4 `user_account_own/delete`, write — на v4 `user_profile_own/write` (deny, D-1). Чужой аккаунт ученика для взрослых ролей — `user_profile_other` (v4), всё deny в фазе регистрации.

### 3а. Markdown-таблица

| Роль | Ресурс | Операция | Allow | Условие |
|------|--------|----------|-------|---------|
| anonymous | registration_draft | read | true | только своя сессия онбординга (in-memory/cookie онбординга), по onboarding_session_id |
| anonymous | registration_draft | write | true | ввод имени/класса/чекбокса до отправки; не персистентные ПД |
| anonymous | registration_draft | create | true | при evt_open_pwa; генерируется onboarding_session_id |
| anonymous | registration_draft | delete | true | при cancel/гейте/отправке |
| anonymous | pd_policy | read | true | публичная политика обработки ПД (ссылка на экране) |
| anonymous | pd_policy | write | false | — |
| anonymous | pd_policy | create | false | — |
| anonymous | pd_policy | delete | false | — |
| anonymous | user_account_own | create | true | только через evt_submit_registration с pd_consent_checked==true AND grade IN (9,10,11); идемпотентно по onboarding_session_id |
| anonymous | user_account_own | read | false | — |
| anonymous | user_account_own | write | false | — |
| anonymous | user_account_own | delete | false | — |
| anonymous | session | create | true | только как side-effect успешной регистрации |
| anonymous | session | read | false | httpOnly cookie, недоступен JS |
| anonymous | session | write | false | — |
| anonymous | session | delete | false | — |
| anonymous | lesson_content | read | false | контент урока недоступен до завершения регистрации |
| anonymous | lesson_content | write | false | — |
| anonymous | lesson_content | create | false | — |
| anonymous | lesson_content | delete | false | — |
| student | registration_draft | read | false | после регистрации draft не существует |
| student | registration_draft | write | false | — |
| student | registration_draft | create | false | повторная регистрация не поддерживается |
| student | registration_draft | delete | false | — |
| student | user_account_own | create | false | аккаунт уже создан; повторная регистрация запрещена |
| student | user_account_own | read | true | только свой профиль (v4 user_profile_own/read) |
| student | user_account_own | write | false | развилка D-1 не решена (v4 user_profile_own/write deny) |
| student | user_account_own | delete | true | каскадное удаление ПД (152-ФЗ, v4 user_account_own/delete) |
| student | pd_policy | read | true | доступ к политике из настроек |
| student | pd_policy | write | false | — |
| student | pd_policy | create | false | — |
| student | pd_policy | delete | false | — |
| parent/teacher/tutor | registration_draft | read | false | взрослые роли не участвуют в регистрации ученика |
| parent/teacher/tutor | registration_draft | write | false | — |
| parent/teacher/tutor | registration_draft | create | false | — |
| parent/teacher/tutor | registration_draft | delete | false | — |
| parent/teacher/tutor | user_profile_other | create | false | взрослый не создаёт аккаунт ученика (привязка — отдельная задача) |
| parent/teacher/tutor | user_profile_other | read | false | — |
| parent/teacher/tutor | user_profile_other | write | false | — |
| parent/teacher/tutor | user_profile_other | delete | false | — |

### 3б. YAML-блок

```yaml
permissions:
  # --- anonymous: registration_draft ---
  - role: anonymous
    resource: registration_draft
    operation: read
    allow: true
    guard: "только своя сессия онбординга по onboarding_session_id (in-memory / cookie онбординга)"
  - role: anonymous
    resource: registration_draft
    operation: write
    allow: true
    guard: "ввод имени/класса/чекбокса до отправки; не персистентные ПД"
  - role: anonymous
    resource: registration_draft
    operation: create
    allow: true
    guard: "при evt_open_pwa; генерируется уникальный onboarding_session_id"
  - role: anonymous
    resource: registration_draft
    operation: delete
    allow: true
    guard: "при cancel / гейте / успешной отправке"

  # --- anonymous: pd_policy ---
  - role: anonymous
    resource: pd_policy
    operation: read
    allow: true
    guard: "публичная политика обработки ПД (ссылка на экране регистрации)"
  - role: anonymous
    resource: pd_policy
    operation: write
    allow: false
    guard: null
  - role: anonymous
    resource: pd_policy
    operation: create
    allow: false
    guard: null
  - role: anonymous
    resource: pd_policy
    operation: delete
    allow: false
    guard: null

  # --- anonymous: user_account_own ---
  - role: anonymous
    resource: user_account_own
    operation: create
    allow: true
    guard: "только через evt_submit_registration: pd_consent_checked==true AND grade IN (9,10,11) AND name непустое; идемпотентно по onboarding_session_id"
  - role: anonymous
    resource: user_account_own
    operation: read
    allow: false
    guard: null
  - role: anonymous
    resource: user_account_own
    operation: write
    allow: false
    guard: null
  - role: anonymous
    resource: user_account_own
    operation: delete
    allow: false
    guard: null

  # --- anonymous: session ---
  - role: anonymous
    resource: session
    operation: create
    allow: true
    guard: "только как side-effect успешной регистрации"
  - role: anonymous
    resource: session
    operation: read
    allow: false
    guard: "httpOnly cookie, недоступен JS"
  - role: anonymous
    resource: session
    operation: write
    allow: false
    guard: null
  - role: anonymous
    resource: session
    operation: delete
    allow: false
    guard: null

  # --- anonymous: lesson_content ---
  - role: anonymous
    resource: lesson_content
    operation: read
    allow: false
    guard: "контент урока недоступен до завершения регистрации"
  - role: anonymous
    resource: lesson_content
    operation: write
    allow: false
    guard: null
  - role: anonymous
    resource: lesson_content
    operation: create
    allow: false
    guard: null
  - role: anonymous
    resource: lesson_content
    operation: delete
    allow: false
    guard: null

  # --- student: registration_draft ---
  - role: student
    resource: registration_draft
    operation: read
    allow: false
    guard: "после регистрации draft не существует"
  - role: student
    resource: registration_draft
    operation: write
    allow: false
    guard: null
  - role: student
    resource: registration_draft
    operation: create
    allow: false
    guard: "повторная регистрация не поддерживается"
  - role: student
    resource: registration_draft
    operation: delete
    allow: false
    guard: null

  # --- student: user_account_own ---
  - role: student
    resource: user_account_own
    operation: create
    allow: false
    guard: "аккаунт уже создан; повторная регистрация запрещена"
  - role: student
    resource: user_account_own
    operation: read
    allow: true
    guard: "только свой профиль (v4 user_profile_own/read)"
  - role: student
    resource: user_account_own
    operation: write
    allow: false
    guard: "развилка D-1 не решена (v4 user_profile_own/write deny)"
  - role: student
    resource: user_account_own
    operation: delete
    allow: true
    guard: "каскадное удаление всех ПД (152-ФЗ, v4 user_account_own/delete)"

  # --- student: pd_policy ---
  - role: student
    resource: pd_policy
    operation: read
    allow: true
    guard: "доступ к политике из настроек"
  - role: student
    resource: pd_policy
    operation: write
    allow: false
    guard: null
  - role: student
    resource: pd_policy
    operation: create
    allow: false
    guard: null
  - role: student
    resource: pd_policy
    operation: delete
    allow: false
    guard: null

  # --- parent/teacher/tutor: registration_draft ---
  - role: parent
    resource: registration_draft
    operation: read
    allow: false
    guard: "взрослые роли не участвуют в регистрации ученика"
  - role: parent
    resource: registration_draft
    operation: write
    allow: false
    guard: null
  - role: parent
    resource: registration_draft
    operation: create
    allow: false
    guard: null
  - role: parent
    resource: registration_draft
    operation: delete
    allow: false
    guard: null
  - role: teacher
    resource: registration_draft
    operation: read
    allow: false
    guard: "взрослые роли не участвуют в регистрации ученика"
  - role: teacher
    resource: registration_draft
    operation: write
    allow: false
    guard: null
  - role: teacher
    resource: registration_draft
    operation: create
    allow: false
    guard: null
  - role: teacher
    resource: registration_draft
    operation: delete
    allow: false
    guard: null
  - role: tutor
    resource: registration_draft
    operation: read
    allow: false
    guard: "взрослые роли не участвуют в регистрации ученика"
  - role: tutor
    resource: registration_draft
    operation: write
    allow: false
    guard: null
  - role: tutor
    resource: registration_draft
    operation: create
    allow: false
    guard: null
  - role: tutor
    resource: registration_draft
    operation: delete
    allow: false
    guard: null

  # --- parent/teacher/tutor: user_profile_other (аккаунт ученика) ---
  - role: parent
    resource: user_profile_other
    operation: create
    allow: false
    guard: "взрослый не создаёт аккаунт ученика; привязка — отдельная задача"
  - role: parent
    resource: user_profile_other
    operation: read
    allow: false
    guard: null
  - role: parent
    resource: user_profile_other
    operation: write
    allow: false
    guard: null
  - role: parent
    resource: user_profile_other
    operation: delete
    allow: false
    guard: null
  - role: teacher
    resource: user_profile_other
    operation: create
    allow: false
    guard: "взрослый не создаёт аккаунт ученика; привязка — отдельная задача"
  - role: teacher
    resource: user_profile_other
    operation: read
    allow: false
    guard: null
  - role: teacher
    resource: user_profile_other
    operation: write
    allow: false
    guard: null
  - role: teacher
    resource: user_profile_other
    operation: delete
    allow: false
    guard: null
  - role: tutor
    resource: user_profile_other
    operation: create
    allow: false
    guard: "взрослый не создаёт аккаунт ученика; привязка — отдельная задача"
  - role: tutor
    resource: user_profile_other
    operation: read
    allow: false
    guard: null
  - role: tutor
    resource: user_profile_other
    operation: write
    allow: false
    guard: null
  - role: tutor
    resource: user_profile_other
    operation: delete
    allow: false
    guard: null
```

---

## 4. Межролевые сценарии

> Охват: только роль «ученик» (+ анонимный посетитель до создания аккаунта). Взрослые роли в регистрации не участвуют.

### Сценарий R-01: grade=9 — прямой вход (happy path)

**Участники:** анонимный посетитель → ученик
**Предусловие:** PWA открыта впервые, аккаунта нет

| Шаг | Актор | Действие | Результат |
|-----|-------|----------|-----------|
| 1 | Посетитель | Открывает PWA | `evt_open_pwa` → `name_entry`; создан RegistrationDraft с onboarding_session_id (не БД) |
| 2 | Система | Показывает поле «Как тебя зовут?» | Экран имени |
| 3 | Посетитель | Вводит «Иван», далее | `evt_name_submitted` (name непустое) → `grade_entry` |
| 4 | Посетитель | Выбирает класс «9» | `evt_grade_selected` (grade==9) → `consent_gate`; enrollment_reason=grade9_direct; ogeprep_answer=null by design |
| 5 | Система | Показывает ссылку на Политику ПД + обязательный чекбокс согласия; перечитывает policy_version_shown | Экран согласия |
| 6 | Посетитель | Ставит галочку, нажимает «Начать» | `evt_submit_registration` (name+grade+consent OK; idempotency-key=onboarding_session_id) |
| 7 | Система | В одной транзакции: создаёт User(name=Иван, grade=9, pd_consent_at=now, pd_consent_version, consent_cohort_flag если Z-1 не закрыта), StudentProfile(fsm_state=registered, current_lesson_id=первый урок), Session(cookie 30д) | `registered`; стык в v4 → daily_start → первый урок |

**Постусловие:** аккаунт создан; ПД = только ник + класс; согласие зафиксировано с timestamp и версией; grade=9-аккаунт помечен для аудита когорты Z-1; первый дофамин = старт урока.

---

### Сценарий R-02: grade=10 — пересдача (уточнение ОГЭ «да»)

**Предусловие:** как R-01, ученик выбирает класс 10

| Шаг | Актор | Действие | Результат |
|-----|-------|----------|-----------|
| 1–3 | — | Как R-01 (имя введено) | `grade_entry` |
| 4 | Посетитель | Выбирает «10» | `evt_grade_selected` (grade IN 10,11) → `ogeprep_check` |
| 5 | Система | Спрашивает «Готовишься к ОГЭ / пересдаёшь?» | Экран уточнения |
| 6 | Посетитель | «Да» | `evt_ogeprep_yes` (ogeprep_answer=yes) → `consent_gate`; enrollment_reason=grade10plus_retake |
| 7 | Посетитель | Согласие ПД + «Начать» | `evt_submit_registration` → `registered` → первый урок |

**Постусловие:** аккаунт создан как пересдача; grade=10; consent_cohort_flag не ставится (grade≠9).

---

### Сценарий R-03: grade=11 — «не готовлюсь к ОГЭ» → курс не подходит → всё равно начинает

**Предусловие:** ученик выбрал класс 11

| Шаг | Актор | Действие | Результат |
|-----|-------|----------|-----------|
| 1 | Посетитель | Выбирает «11», на уточнении отвечает «Нет» | `evt_ogeprep_no` (ogeprep_answer=no) → `course_mismatch` (единственный вход, grade 10+) |
| 2 | Система | Показывает честный экран «курс не подходит» (§1.4), БЕЗ блокировки, с кнопками «Всё равно начать» / «Выйти» | Экран информера |
| 3 | Посетитель | «Всё равно начать» | `evt_mismatch_continue` → `consent_gate` |
| 4 | Посетитель | Согласие ПД + «Начать» | `evt_submit_registration` → `registered` |

**Постусловие:** ученик впущен по своему решению (Методология запрещает блокировать, кроме grade=8).

---

### Сценарий R-04: grade=8 — жёсткий гейт (production)

**Предусловие:** production-среда, посетитель выбирает класс 8

| Шаг | Актор | Действие | Результат |
|-----|-------|----------|-----------|
| 1 | Посетитель | Выбирает «8» | `evt_grade_selected` (grade==8, env=prod) → `gate_grade8` |
| 2 | Система | Показывает тёплый экран «Курс для 9 класса — возвращайся в сентябре!»; вход в курс закрыт | Гейт-экран; User НЕ создан |
| 3 | Посетитель | Закрывает / «Понятно» | `evt_gate_dismiss` → `unregistered`; RegistrationDraft уничтожен |

**Постусловие:** активный аккаунт ученика курса не создан; ПД не записаны (D-6 закрыта продуктово).

---

### Сценарий R-05: отмена на любом шаге

**Предусловие:** посетитель в любом из `name_entry`/`grade_entry`/`ogeprep_check`/`course_mismatch`/`consent_gate`

| Шаг | Актор | Действие | Результат |
|-----|-------|----------|-----------|
| 1 | Посетитель | Закрывает форму / «Отмена» | `evt_cancel_registration` → `unregistered` |
| 2 | Система | Уничтожает RegistrationDraft; ПД в БД не пишет | Чистое состояние, повтор возможен заново |

**Постусловие:** ничего не сохранено; повторный вход начинает онбординг заново (новый onboarding_session_id).

---

## 5. Edge Cases

| id | Условие | Ожидаемое поведение системы |
|----|---------|-----------------------------|
| RC-01 | Дабл-клик на «Начать» в consent_gate | Фронтенд блокирует кнопку после первого нажатия; бэкенд использует idempotency-key = onboarding_session_id; дублирующий User не создаётся (правка №2) |
| RC-02 | Пустое имя или только пробелы | `evt_name_submitted` не генерируется (guard «непустое после trim»); кнопка «Далее» неактивна; остаёмся в `name_entry` |
| RC-03 | Отправка `evt_submit_registration` с pd_consent_checked=false (обход фронтенда) | Бэкенд-guard отклоняет (403/422); User не создаётся; 152-ФЗ — без согласия регистрации нет |
| RC-04 | Подмена grade=8 в запросе в production (минуя UI) | Бэкенд-guard `grade IN (9,10,11)` отклоняет (422); аккаунт не создаётся; жёсткий гейт on backend, не только UI |
| RC-05 | grade вне 8–11 (например 7 или 12) | Бэкенд-guard отклоняет (422); UI предлагает только допустимые классы |
| RC-06 | Закрытие браузера в середине онбординга (до submit) | RegistrationDraft не персистентен → теряется; повторный вход = онбординг с нуля (новый onboarding_session_id); ПД не записаны (минимизация) |
| RC-07 | Гонка: два запроса submit из двух вкладок (одна сессия онбординга) | Бэкенд: транзакция + unique constraint на onboarding_session_id (idempotency-key); второй запрос получает 409 Conflict ЛИБО возвращает уже созданный аккаунт; один аккаунт. **Опора на (name, created_at) убрана** — два «Ивана» в одну секунду НЕ дают ложной коллизии, т.к. у них разные onboarding_session_id (правка №2) |
| RC-08 | Версия политики ПД изменилась между показом и submit | В User записывается `policy_version_shown` (та версия, что видел ученик), не текущая; при повторном входе в consent_gate policy_version_shown перечитывается заново (правка №6); если на момент submit версия разошлась — бэкенд может потребовать переподтверждение (защита целостности согласия) |
| RC-09 | Ученик нажимает «Назад» из consent_gate, меняет класс с 9 на 8 (prod) | `evt_back` → `grade_entry`; затем `evt_grade_selected` (grade==8) → `gate_grade8`; согласие сброшено; аккаунт не создаётся |
| RC-10 | Анонимный посетитель пытается прочитать lesson_content до регистрации | Deny by default (матрица прав, anonymous/lesson_content/read=false); 403 |
| RC-11 | Уже зарегистрированный ученик (валидный cookie) открывает PWA-ссылку онбординга | Не попадает в `name_entry`: бэкенд по сессии распознаёт существующий аккаунт → v4 `registered` (re-auth), регистрация повторно не запускается |
| RC-12 | На экране course_mismatch ученик «Выйти» | `evt_mismatch_leave` → `unregistered`; draft уничтожен; уход по своему выбору, без принуждения (§1.3 «не удерживаем») |
| RC-13 | [Z-1] grade=9, но фактический возраст <14 | Не детектируется в момент регистрации (дату рождения не собираем — минимизация ПД). Аккаунт помечается `consent_cohort_flag` для возможности точечно идентифицировать когорту grade=9 до юр-заключения (правка №4). Зафиксировано как незакрытая юр-зависимость Z-1; обратимость — см. RF-08; ветки согласия представителя в FSM нет |
| RC-14 | Повторный вход в consent_gate через evt_back при изменившейся версии политики | policy_version_shown перечитывается заново на каждом входе в consent_gate (правка №6); ученик видит и принимает актуальную версию; в pd_consent_version пишется именно она |

---

## 6. Режимы отказа

| id | Триггер отказа | Поведение системы | Обратимо? |
|----|---------------|-------------------|-----------|
| RF-01 | Бэкенд недоступен в момент `evt_submit_registration` | Фронтенд показывает «Не удалось завершить регистрацию, попробуй ещё раз»; RegistrationDraft в памяти клиента сохранён для повтора (тот же onboarding_session_id → идемпотентный повтор); User не создан | Да — повтор при восстановлении связи; без частичного аккаунта |
| RF-02 | Транзакция создания User/StudentProfile/Session частично упала | Полный откат транзакции (atomicity): ничего не создаётся; никаких «висячих» User без профиля/сессии; ученик остаётся в consent_gate с сообщением об ошибке | Да — повторить submit (тот же idempotency-key) |
| RF-03 | Нет соединения при открытии PWA (service worker) | SW отдаёт кэшированную оболочку онбординга (статичные экраны name/grade); submit откладывается до сети; ПД не отправляются офлайн | Да — submit при появлении сети |
| RF-04 | Политика ПД (pd_policy) не загрузилась (битая ссылка) | Чекбокс согласия остаётся неактивным до доступности политики; регистрацию нельзя завершить, пока ученик не имел возможности ознакомиться (152-ФЗ — информированность согласия) | Да — при восстановлении доступа к политике |
| RF-05 | Утечка: создание аккаунта на чужой grade/name через подмену запроса | Все поля валидируются на бэкенде (name, grade IN 9..11, consent); матрица прав deny by default; анонимный может только create через корректный submit | Нет (не должно случаться); при обнаружении — аудит, уведомление фаундера |
| RF-06 | Scheduler/первый урок недоступен сразу после registered (current_lesson_id не определился) | Аккаунт уже создан корректно (transaction committed); v4-слой показывает safe fallback (D-5 v4: «нет соединения» без потери прогресса); регистрация НЕ откатывается | Да — урок подгрузится при следующем входе; аккаунт сохранён |
| RF-07 | Дубль submit / гонка / повтор после сбоя сети | Идемпотентность по `onboarding_session_id`: повторный submit с тем же ключом возвращает уже созданный аккаунт ИЛИ 409, второй User НЕ создаётся. **Опора на `unique(name, created_at)` убрана (правка №2)** — неуникальный ник не используется как ключ идемпотентности; два «Ивана» в одну секунду имеют разные onboarding_session_id и оба регистрируются корректно | Да — повтор идемпотентен; ровно один аккаунт на сессию онбординга |
| RF-08 | **[Z-1, правка №4] Юр-заключение по Z-1 негативно: часть grade=9-аккаунтов создана БЕЗ валидного согласия (субъект <14, нужно согласие представителя)** | Аккаунты grade=9, созданные ДО даты юр-заключения, идентифицируются точечно по `consent_cohort_flag` (+ `pd_consent_version` + `created_at`). По этой когорте бэкенд может: (а) запросить согласие законного представителя через отдельную ветку (вне текущей FSM, новая задача), либо (б) каскадно удалить ПД (152-ФЗ право на удаление). Когорта не теряется и не смешивается с валидными аккаунтами | **Да — обратимо (это и есть цель правки №4):** негативное заключение НЕ необратимо задним числом; когорта grade=9-до-заключения выделяется флагом и обрабатывается (согласие представителя ИЛИ удаление). После закрытия Z-1 `consent_cohort_flag` перестаёт ставиться |

---

*Спека v2 детализирует фазу onboarding из specs/student_lesson_fsm_v4.md, не нарушая её контракт. Исправлено по ревью А4 v1 (правки №1, 2, 3, 4, 6, 7; №5 без изменений). Закрывает D-6 продуктовым жёстким гейтом grade=8. Незакрытые зависимости: Z-1 (согласие законного представителя <14 — юр-проверка, теперь с механизмом обратимости RF-08), Z-2 (текст/версия политики ПД), D-1 (смена имени/класса — наследие v4). Роли parent/teacher/tutor и привязки взрослых — отдельная задача «после первого урока».*
