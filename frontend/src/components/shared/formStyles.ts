// Single source of truth for intake form field styling.
// Shared across ProfileForm, CountryPicker, and PrioritiesInput so the look stays consistent.

export const labelClass = 'block text-sm font-medium text-ink'

export const fieldBase =
  'mt-1.5 block w-full rounded-lg border border-line bg-surface/80 px-3.5 py-2.5 text-ink shadow-inner shadow-black/20 transition duration-200 placeholder:text-ink-muted/60 hover:border-line/80 focus:border-path-a focus:bg-surface focus:outline-none focus:ring-2 focus:ring-path-a/30'

export const inputClass = fieldBase
export const selectClass = fieldBase
export const textareaClass = `${fieldBase} resize-y`

export const errorClass = 'mt-1.5 text-sm text-signal'

// Mono eyebrow used for section headers ("YOU", "THE CHOICE", "WHAT MATTERS").
export const sectionEyebrowClass =
  'font-mono text-xs font-medium uppercase tracking-[0.18em] text-ink-muted'
