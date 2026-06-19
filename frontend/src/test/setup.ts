// Матчеры @testing-library/jest-dom для vitest (toBeInTheDocument, toBeDisabled, …).
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Без globals:true авто-cleanup testing-library не срабатывает — чистим DOM сами,
// иначе рендеры накапливаются между тестами (дубли по роли/подписи).
afterEach(() => {
  cleanup()
})
