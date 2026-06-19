import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Deep blue-slate, not pure black — reads as an instrument, not a void.
        paper: '#0E151E',
        surface: '#172230',
        'surface-raised': '#1D2A39',
        ink: {
          DEFAULT: '#E9EEF2',
          muted: '#92A2AE',
        },
        line: '#2A3949',
        'path-a': '#3CAEBD',
        'path-b': '#E0A24A',
        signal: '#E3756F',
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        sans: ['"IBM Plex Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config
