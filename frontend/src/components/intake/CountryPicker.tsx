import type { CompareRequest, SupportedCountry } from '../../types'
import { SUPPORTED_COUNTRIES } from '../../types'
import type { FormErrors } from './ProfileForm'

interface CountryPickerProps {
  countryA: SupportedCountry
  countryB: SupportedCountry
  errors: FormErrors
  onChange: (field: keyof CompareRequest, value: string) => void
}

const labelClass = 'block text-sm font-medium text-gray-700'
const selectClass =
  'mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500'
const errorClass = 'mt-1 text-sm text-red-600'

export default function CountryPicker({
  countryA,
  countryB,
  errors,
  onChange,
}: CountryPickerProps) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div>
        <label htmlFor="country_a" className={labelClass}>
          Country A
        </label>
        <select
          id="country_a"
          className={selectClass}
          value={countryA}
          onChange={(e) => onChange('country_a', e.target.value)}
        >
          {SUPPORTED_COUNTRIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="country_b" className={labelClass}>
          Country B
        </label>
        <select
          id="country_b"
          className={selectClass}
          value={countryB}
          onChange={(e) => onChange('country_b', e.target.value)}
          aria-invalid={Boolean(errors.country_b)}
        >
          {SUPPORTED_COUNTRIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        {errors.country_b && <p className={errorClass}>{errors.country_b}</p>}
      </div>
    </div>
  )
}
