import type { Config } from 'tailwindcss';

// Colour tokens are CSS variables holding space-separated RGB channels (see src/styles/index.css),
// so Tailwind opacity modifiers (bg-accent/10) keep working.
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        canvas: token('canvas'),
        sidebar: token('sidebar'),
        surface: {
          DEFAULT: token('surface-1'),
          raised: token('surface-2'),
          overlay: token('surface-3'),
        },
        line: { DEFAULT: token('line'), strong: token('line-strong') },
        ink: { DEFAULT: token('ink'), muted: token('ink-muted'), faint: token('ink-faint') },
        accent: { DEFAULT: token('accent'), strong: token('accent-strong') },
        brand: token('brand'),
        success: token('success'),
        warning: token('warning'),
        danger: token('danger'),
        simulation: token('simulation'),
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0.04em' }],
        xs: ['0.75rem', { lineHeight: '1.125rem' }],
        sm: ['0.8125rem', { lineHeight: '1.25rem' }],
        base: ['0.875rem', { lineHeight: '1.375rem' }],
      },
      borderRadius: { DEFAULT: '4px', md: '6px', lg: '8px' },
      boxShadow: {
        raised: '0 1px 0 0 rgb(255 255 255 / 0.03) inset, 0 1px 2px 0 rgb(0 0 0 / 0.4)',
        overlay: '0 12px 32px -8px rgb(0 0 0 / 0.6), 0 0 0 1px rgb(var(--line) / 1)',
      },
    },
  },
  plugins: [],
} satisfies Config;
