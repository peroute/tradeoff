import type { CompareRequest } from '../../types'
import type { FormErrors } from './ProfileForm'

interface PrioritiesInputProps {
  value: string
  errors: FormErrors
  onChange: (field: keyof CompareRequest, value: string) => void
}

const labelClass = 'block text-sm font-medium text-gray-700'
const textareaClass =
  'mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500'
const errorClass = 'mt-1 text-sm text-red-600'

export default function PrioritiesInput({ value, errors, onChange }: PrioritiesInputProps) {
  return (
    <div>
      <label htmlFor="user_context" className={labelClass}>
        What matters most to you?
      </label>
      <textarea
        id="user_context"
        rows={4}
        className={textareaClass}
        placeholder="e.g. I care most about long-term residency stability and keeping my options open."
        value={value}
        onChange={(e) => onChange('user_context', e.target.value)}
        aria-invalid={Boolean(errors.user_context)}
      />
      {errors.user_context && <p className={errorClass}>{errors.user_context}</p>}
    </div>
  )
}
