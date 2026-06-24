// Склонение числительных (RU) для строк с {N} — А8 v1.1 §0 «плюрализацию {N} разводит
// код». Используется DayCounterBadge («N дней подряд») и PendingNotice (R1 «через N минут»).
function pluralRu(n: number, forms: readonly [string, string, string]): string {
  const abs = Math.abs(n) % 100
  const last = abs % 10
  if (abs > 10 && abs < 20) return forms[2]
  if (last === 1) return forms[0]
  if (last >= 2 && last <= 4) return forms[1]
  return forms[2]
}

export function daysLabel(n: number): string {
  return `${n} ${pluralRu(n, ['день', 'дня', 'дней'])} подряд`
}

export function minutesLabel(n: number): string {
  return `${n} ${pluralRu(n, ['минуту', 'минуты', 'минут'])}`
}
