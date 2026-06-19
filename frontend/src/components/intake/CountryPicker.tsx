import type { CompareRequest, SupportedCountry } from '../../types'
import { COUNTRY_META, SUPPORTED_COUNTRIES } from '../../types'
import { errorClass } from '../shared/formStyles'
import type { FormErrors } from './ProfileForm'

interface CountryPickerProps {
  countryA: SupportedCountry
  countryB: SupportedCountry
  errors: FormErrors
  onChange: (field: keyof CompareRequest, value: string) => void
}

type Path = 'a' | 'b'

interface LaneProps {
  path: Path
  field: 'country_a' | 'country_b'
  label: string
  value: SupportedCountry
  invalid?: boolean
  onChange: (field: keyof CompareRequest, value: string) => void
}

// Per-path accent classes. Spelled out so Tailwind keeps them in the build.
const accent: Record<Path, { tab: string; ring: string; border: string; code: string; chip: string }> = {
  a: {
    tab: 'bg-path-a text-white',
    ring: 'focus-within:border-path-a focus-within:ring-path-a',
    border: 'border-path-a/30',
    code: 'text-path-a',
    chip: 'bg-path-a/10 text-path-a',
  },
  b: {
    tab: 'bg-path-b text-white',
    ring: 'focus-within:border-path-b focus-within:ring-path-b',
    border: 'border-path-b/30',
    code: 'text-path-b',
    chip: 'bg-path-b/10 text-path-b',
  },
}

function Lane({ path, field, label, value, invalid, onChange }: LaneProps) {
  const a = accent[path]
  const meta = COUNTRY_META[value]
  return (
    <div
      className={`flex-1 rounded-xl border bg-surface-raised shadow-lg shadow-black/20 transition-colors focus-within:ring-1 ${a.border} ${a.ring}`}
    >
      <div className="flex items-center justify-between px-4 pt-3">
        <span
          className={`rounded-md px-2 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-[0.16em] ${a.chip}`}
        >
          Path {path.toUpperCase()}
        </span>
        <span className={`font-mono text-2xl font-semibold ${a.code}`}>{meta.code}</span>
      </div>
      <div className="px-4 pb-4">
        {/* Accessible name kept as "Country A" / "Country B" for the form contract. */}
        <label htmlFor={field} className="sr-only">
          {label}
        </label>
        <select
          id={field}
          aria-invalid={invalid}
          value={value}
          onChange={(e) => onChange(field, e.target.value)}
          className="mt-1 block w-full rounded-lg border border-line bg-surface px-3 py-2.5 text-base font-medium text-ink focus:border-transparent focus:outline-none focus:ring-0"
        >
          {SUPPORTED_COUNTRIES.map((c) => (
            <option key={c} value={c}>
              {COUNTRY_META[c].name}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}

export default function CountryPicker({ countryA, countryB, errors, onChange }: CountryPickerProps) {
  return (
    <div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-stretch sm:gap-4">
        <Lane path="a" field="country_a" label="Country A" value={countryA} onChange={onChange} />
        <div className="flex items-center justify-center">
          <span className="font-mono text-xs font-semibold uppercase tracking-[0.2em] text-ink-muted">
            vs
          </span>
        </div>
        <Lane
          path="b"
          field="country_b"
          label="Country B"
          value={countryB}
          invalid={Boolean(errors.country_b)}
          onChange={onChange}
        />
      </div>
      {errors.country_b && <p className={errorClass}>{errors.country_b}</p>}
    </div>
  )
}
