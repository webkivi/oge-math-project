import type { Config } from 'tailwindcss'

// Дизайн-токены ученической поверхности — А6 §1. Источник истины ЗНАЧЕНИЙ —
// CSS-переменные в src/index.css (имена как в А6: --bg-canvas, --text-primary и т.д.);
// здесь — маппинг на Tailwind-утилиты. Контраст проверен по WCAG 2.1 AA (А6 §1.1).
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // §1.1 Цвет
        canvas: 'var(--bg-canvas)', // фон приложения
        surface: 'var(--bg-surface)', // карточки/поля/диалоги
        sunken: 'var(--bg-sunken)', // утопленные зоны (разбор, цитаты)
        ink: {
          DEFAULT: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
        },
        primary: {
          DEFAULT: 'var(--primary)', // главное действие
          hover: 'var(--primary-hover)',
          active: 'var(--primary-active)',
        },
        correct: {
          DEFAULT: 'var(--correct)',
          bg: 'var(--correct-bg)',
          text: 'var(--correct-text)',
        },
        trap: {
          // «типичная ловушка» — тёплая охра, НЕ красный (А6 §1.1, антипринцип §1.3)
          DEFAULT: 'var(--trap)',
          bg: 'var(--trap-bg)',
          text: 'var(--trap-text)',
        },
        line: {
          DEFAULT: 'var(--border-interactive)', // границы полей/выбираемых карточек
          subtle: 'var(--border-subtle)', // декоративные разделители
        },
        disabled: {
          DEFAULT: 'var(--disabled-bg)',
          text: 'var(--disabled-text)',
        },
        focusring: 'var(--focus-ring)',
        destructive: 'var(--destructive)', // только «Удалить аккаунт»
      },
      fontFamily: {
        // §1.2 — системный санс-стек (без веб-шрифта: PWA-офлайн, мгновенный рендер)
        sans: 'var(--font-sans)',
        mono: 'var(--font-mono)', // числа/единицы в условии задачи
      },
      fontSize: {
        // §1.2 [размер, { межстрочный, вес }]
        title: ['24px', { lineHeight: '1.3', fontWeight: '700' }],
        lead: ['19px', { lineHeight: '1.4', fontWeight: '600' }],
        body: ['17px', { lineHeight: '1.6', fontWeight: '400' }],
        option: ['17px', { lineHeight: '1.4', fontWeight: '500' }],
        caption: ['14px', { lineHeight: '1.4', fontWeight: '500' }],
      },
      borderRadius: {
        // §1.4
        card: '16px',
        control: '12px',
        pill: '9999px',
      },
      maxWidth: {
        // §1.3 — контент остаётся «телефонным» даже на широком экране
        content: '440px',
      },
    },
  },
  plugins: [],
} satisfies Config
