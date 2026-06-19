import type { CompareRequest } from '../../types'
import { errorClass, labelClass, textareaClass } from '../shared/formStyles'
import type { FormErrors } from './ProfileForm'

interface PrioritiesInputProps {
  value: string
  errors: FormErrors
  onChange: (field: keyof CompareRequest, value: string) => void
}

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
