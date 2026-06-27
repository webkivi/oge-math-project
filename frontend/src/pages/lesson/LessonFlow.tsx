// Оркестратор дневного потока и урока (раскладка v4 §7: pages/lesson/LessonFlow.tsx).
// Держит один useLesson и рендерит экран по `view` последнего render-payload сервера
// (api v1 §4.1/§4.9) — не по своей FSM-таблице (источник истины — backend, §1.1).
import { ConnectionStub } from '../../components/ConnectionStub'
import { useLesson } from '../../hooks/useLesson'
import { CourseComplete } from './CourseComplete'
import { DailyBlocked } from './DailyBlocked'
import { DailyDone } from './DailyDone'
import { DailyStart } from './DailyStart'
import { LessonPlayer } from './LessonPlayer'
import { MorningWarmup } from './MorningWarmup'
import { RepeatActive } from './RepeatActive'
import { RepeatPending } from './RepeatPending'

export function LessonFlow() {
  const lesson = useLesson()

  if (lesson.offline) return <ConnectionStub variant="offline" />
  if (lesson.contentMissing) return <ConnectionStub variant="content-missing" />
  if (lesson.loading || lesson.render === null) {
    return <p className="py-8 text-center text-body text-ink-secondary">Загрузка…</p>
  }

  switch (lesson.render.view) {
    case 'day_hub':
      return <DailyStart lesson={lesson} />
    case 'lesson_message':
    case 'lesson_question':
    case 'lesson_feedback':
    case 'lesson_final':
    case 'lesson_failed':
      return <LessonPlayer lesson={lesson} />
    case 'warmup':
      return <MorningWarmup lesson={lesson} />
    case 'repeat_pending':
      return <RepeatPending />
    case 'repeat_question':
      return <RepeatActive lesson={lesson} />
    case 'day_done':
      return <DailyDone />
    case 'day_blocked':
      return <DailyBlocked />
    case 'course_complete':
      return <CourseComplete />
    default:
      return null
  }
}
