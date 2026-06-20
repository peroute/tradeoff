// Shared Recharts styling tokens, kept in lock-step with tailwind.config.ts so
// charts read from the same palette as the rest of the dark "instrument" theme.
// Recharts takes raw color strings (SVG fills/strokes), not Tailwind classes,
// so the values are mirrored here as constants.

import type { CSSProperties } from 'react'

/** Country A identity — teal (`path-a`). */
export const COLOR_A = '#3CAEBD'
/** Country B identity — amber (`path-b`). */
export const COLOR_B = '#E0A24A'
/** Muted/secondary series (e.g. the tax slice of a gross bar). */
export const COLOR_MUTED = '#92A2AE' // ink-muted
/** Accent for warnings / the human-boundary signal. */
export const COLOR_SIGNAL = '#E3756F' // signal

export const AXIS_TICK = '#92A2AE' // ink-muted
export const GRID_STROKE = '#2A3949' // line

/** Inline style for custom tooltip containers — matches `surface-raised`. */
export const TOOLTIP_STYLE: CSSProperties = {
  background: '#1D2A39', // surface-raised
  border: '1px solid #2A3949', // line
  borderRadius: 8,
  color: '#E9EEF2', // ink
  fontSize: 12,
  padding: '8px 10px',
}
